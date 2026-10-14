import json
import logging as log
import time

from queue import Empty
from multiprocessing import Queue

from ..lib.service import Service, ServiceRestartSignal
from .. import app

from libflagship.pppp import P2PSubCmdType, Xzyh

# Restart the service if no video frames received within this many seconds
FRAME_TIMEOUT = 10
# Log a heartbeat at this interval (seconds)
HEARTBEAT_INTERVAL = 60


class VideoQueue(Service):

    def api_start_live(self):
        self.pppp.api_command(P2PSubCmdType.START_LIVE, data={
            "encryptkey": "x",
            "accountId": "y",
        })

    def api_stop_live(self):
        self.pppp.api_command(P2PSubCmdType.CLOSE_LIVE)

    def api_light_state(self, light):
        self.saved_light_state = light
        self.pppp.api_command(P2PSubCmdType.LIGHT_STATE_SWITCH, data={
            "open": light,
        })

    def api_video_mode(self, mode):
        self.saved_video_mode = mode
        self.pppp.api_command(P2PSubCmdType.LIVE_MODE_SET, data={
            "mode": mode
        })

    def _handler(self, data):
        chan, msg = data

        if chan != 1:
            return

        if not isinstance(msg, Xzyh):
            return

        self._last_frame_time = time.monotonic()
        self.notify(msg)

    def worker_init(self):
        self.saved_light_state = None
        self.saved_video_mode = None
        self._last_frame_time = None
        self._connected_since = None
        self._last_heartbeat = None

    def worker_start(self):
        self.pppp = app.svc.get("pppp")

        self.api_id = id(self.pppp._api)

        self.pppp.handlers.append(self._handler)

        self.api_start_live()

        if self.saved_light_state is not None:
            self.api_light_state(self.saved_light_state)

        if self.saved_video_mode is not None:
            self.api_video_mode(self.saved_video_mode)

        self._last_frame_time = time.monotonic()
        self._connected_since = time.monotonic()
        self._last_heartbeat = time.monotonic()
        log.info(f"{self.name}: Video stream started")

    def worker_run(self, timeout):
        self.idle(timeout=timeout)

        if not self.pppp.connected:
            log.warning(f"{self.name}: No PPPP connection, restarting video")
            raise ServiceRestartSignal("No pppp connection")

        if id(self.pppp._api) != self.api_id:
            log.info(f"{self.name}: New PPPP connection detected, restarting video feed")
            raise ServiceRestartSignal("New pppp connection detected, restarting video feed")

        now = time.monotonic()

        # Frame timeout check
        if self._last_frame_time and (now - self._last_frame_time) > FRAME_TIMEOUT:
            log.warning(f"{self.name}: No video frames for {FRAME_TIMEOUT}s, restarting")
            raise ServiceRestartSignal("Video frame timeout")

        # Heartbeat log
        if self._last_heartbeat and (now - self._last_heartbeat) >= HEARTBEAT_INTERVAL:
            self._last_heartbeat = now
            uptime = now - self._connected_since if self._connected_since else 0
            frame_age = now - self._last_frame_time if self._last_frame_time else -1
            log.info(f"{self.name}: Stream active for {uptime:.0f}s, last frame {frame_age:.1f}s ago")

    def worker_stop(self):
        log.info(f"{self.name}: Stopping video stream")
        try:
            self.api_stop_live()
        except Exception as E:
            log.warning(f"{self.name}: Failed to send stop command ({E})")

        self.pppp.handlers.remove(self._handler)

        app.svc.put("pppp")
        self._last_frame_time = None
        self._connected_since = None
        self._last_heartbeat = None

    @property
    def health(self):
        now = time.monotonic()
        return {
            "connected": self.pppp.connected if hasattr(self, "pppp") else False,
            "last_frame_age": (now - self._last_frame_time) if self._last_frame_time else None,
            "uptime": (now - self._connected_since) if self._connected_since else None,
        }
