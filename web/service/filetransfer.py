import uuid
import logging as log

from multiprocessing import Queue

from ..lib.service import Service
from .. import app

from libflagship.pppp import P2PCmdType, Aabb, FileTransfer, FileTransferReply
from libflagship.ppppapi import FileUploadInfo, PPPPError

import cli.mqtt
import cli.util


class FileTransferService(Service):

    def api_aabb(self, api, frametype, msg=b"", pos=0):
        api.send_aabb(msg, frametype=frametype, pos=pos)

    def api_aabb_request(self, api, frametype, msg=b"", pos=0):
        self.api_aabb(api, frametype, msg, pos)
        try:
            resp = self._tap.get(timeout=30)
        except Exception:
            raise TimeoutError(f"Aabb request timed out (type={frametype}, pos={pos})")
        reply_code = resp.data[0] if resp.data else -1
        try:
            reply = FileTransferReply(reply_code)
            reply_str = reply.name
        except ValueError:
            reply_str = f"UNKNOWN(0x{reply_code:02x})"
        if reply_code != 0:
            log.warning(f"{self.name}: Aabb REPLY type={resp.frametype} pos={resp.pos} "
                        f"len={resp.len} reply={reply_str}(0x{reply_code:02x}) data={resp.data.hex()}")
        else:
            log.debug(f"{self.name}: Aabb OK type={resp.frametype} pos={resp.pos} len={resp.len}")

    def send_file(self, fd, user_name):
        try:
            api = self.pppp._api
        except AttributeError:
            raise ConnectionError("No pppp connection to printer")

        data = fd.read()
        fui = FileUploadInfo.from_data(data, fd.filename, user_name=user_name, user_id="-", machine_id="-")
        log.info(f"Going to upload {fui.size} bytes as {fui.name!r} (md5={fui.md5})")
        try:
            log.info("Requesting file transfer..")
            api.send_xzyh(str(uuid.uuid4())[:16].encode(), cmd=P2PCmdType.P2P_SEND_FILE)

            log.info(f"Sending file metadata.. ({len(bytes(fui)) + 1} bytes)")
            self.api_aabb_request(api, FileTransfer.BEGIN, bytes(fui) + b"\x00")
            log.info(f"{self.name}: BEGIN acknowledged")

            log.info("Sending file contents..")
            blocksize = 1024 * 32
            chunk_count = 0
            for pos, chunk in cli.util.split_chunks(data, blocksize):
                self.api_aabb_request(api, FileTransfer.DATA, chunk, pos)
                chunk_count += 1
                if chunk_count % 10 == 0:
                    log.info(f"{self.name}: Sent {chunk_count} chunks ({pos + len(chunk)}/{fui.size} bytes)")

            log.info(f"File upload complete ({chunk_count} chunks). Requesting print start of job.")

            self.api_aabb_request(api, FileTransfer.END)
        except PPPPError as E:
            log.error(f"Could not send print job: {E}")
            raise ConnectionError(f"Could not send print job: {E}") from E
        else:
            log.info("Successfully sent print job")

    def handler(self, data):
        chan, msg = data
        if isinstance(msg, Aabb):
            self._tap.put(msg)

    def worker_start(self):
        self.pppp = app.svc.get("pppp")
        self._tap = Queue()

        self.pppp.handlers.append(self.handler)

    def worker_run(self, timeout):
        self.idle(timeout=timeout)

    def worker_stop(self):
        self.pppp.handlers.remove(self.handler)
        del self._tap

        app.svc.put("pppp")
