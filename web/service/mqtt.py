import logging as log
import re
import time

from ..lib.service import Service, ServiceRestartSignal
from .. import app

from libflagship.util import enhex

import cli.mqtt

# Restart the service if disconnected for this many seconds
MQTT_DISCONNECT_TIMEOUT = 10
# Log a heartbeat at this interval (seconds)
HEARTBEAT_INTERVAL = 60


class MqttQueue(Service):

    def worker_init(self):
        self._connected_since = None
        self._disconnected_since = None
        self._last_heartbeat = None

    def validate_gcode_payload(self, msg_dict):
        """Sanitize outbound G-Code commands against physical printer maximums."""
        if not isinstance(msg_dict, dict) or "cmdData" not in msg_dict:
            return msg_dict

        cmd = msg_dict["cmdData"]

        # M104 S<temp> - Set Hotend Temperature (Max 260)
        if cmd.startswith("M104 S"):
            try:
                temp = int(re.search(r'S(\d+)', cmd).group(1))
                if temp > 260:
                    log.warning(f"Blocked dangerous nozzle temp request: {temp}°C")
                    msg_dict["cmdData"] = "M104 S260"
                    msg_dict["cmdLen"] = len(msg_dict["cmdData"])
            except Exception:
                pass

        # M140 S<temp> - Set Bed Temperature (Max 100)
        elif cmd.startswith("M140 S"):
            try:
                temp = int(re.search(r'S(\d+)', cmd).group(1))
                if temp > 100:
                    log.warning(f"Blocked dangerous bed temp request: {temp}°C")
                    msg_dict["cmdData"] = "M140 S100"
                    msg_dict["cmdLen"] = len(msg_dict["cmdData"])
            except Exception:
                pass

        # G1 ... E<len> - Extrusion Limits (Max 100mm per command)
        elif re.match(r'^G1\s', cmd):
            try:
                match = re.search(r'E(-?\d+)', cmd)
                if match:
                    length = int(match.group(1))
                    if length > 100:
                        log.warning(f"Blocked excessive extrusion length: {length}mm")
                        msg_dict["cmdData"] = cmd.replace(f"E{length}", "E100")
                        msg_dict["cmdLen"] = len(msg_dict["cmdData"])
                    elif length < -100:
                        log.warning(f"Blocked excessive retraction length: {length}mm")
                        msg_dict["cmdData"] = cmd.replace(f"E{length}", "E-100")
                        msg_dict["cmdLen"] = len(msg_dict["cmdData"])
            except Exception:
                pass

        return msg_dict

    def worker_start(self):
        self._connected_since = time.monotonic()
        self._disconnected_since = None
        self._last_heartbeat = time.monotonic()
        self.client = cli.mqtt.mqtt_open(
            app.config["config"],
            app.config["printer_index"],
            app.config["insecure"]
        )
        log.info(f"{self.name}: Connected to MQTT broker")

    def worker_run(self, timeout):
        now = time.monotonic()

        for msg, body in self.client.fetch(timeout=timeout):
            log.info(f"TOPIC [{msg.topic}]")
            log.debug(enhex(msg.payload[:]))

            for obj in body:
                self.notify(obj)

        # Check connection state
        if not self.client._connected:
            if self._disconnected_since is None:
                self._disconnected_since = now
                log.warning(f"{self.name}: MQTT connection lost")
            elif (now - self._disconnected_since) > MQTT_DISCONNECT_TIMEOUT:
                log.warning(f"{self.name}: MQTT disconnected for {MQTT_DISCONNECT_TIMEOUT}s, restarting")
                raise ServiceRestartSignal()
        else:
            if self._disconnected_since is not None:
                log.info(f"{self.name}: MQTT reconnected after {now - self._disconnected_since:.1f}s")
                self._disconnected_since = None
                self._connected_since = now

        # Heartbeat log
        if self._last_heartbeat and (now - self._last_heartbeat) >= HEARTBEAT_INTERVAL:
            self._last_heartbeat = now
            uptime = now - self._connected_since if self._connected_since else 0
            state = "connected" if self.client._connected else f"disconnected for {now - self._disconnected_since:.0f}s"
            log.info(f"{self.name}: {state} (uptime {uptime:.0f}s)")

    def worker_stop(self):
        log.info(f"{self.name}: Disconnecting from MQTT broker")
        try:
            self.client._mqtt.disconnect()
        except Exception:
            pass
        del self.client
        self._connected_since = None
        self._disconnected_since = None
        self._last_heartbeat = None

    @property
    def health(self):
        now = time.monotonic()
        connected = self.client._connected if hasattr(self, "client") else False
        return {
            "connected": connected,
            "uptime": (now - self._connected_since) if self._connected_since else None,
            "disconnected_for": (now - self._disconnected_since) if self._disconnected_since else None,
        }
