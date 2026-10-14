import logging as log
import re

from ..lib.service import Service
from .. import app

from libflagship.util import enhex

import cli.mqtt

class MqttQueue(Service):
    
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
        self.client = cli.mqtt.mqtt_open(
            app.config["config"],
            app.config["printer_index"],
            app.config["insecure"]
        )

    def worker_run(self, timeout):
        for msg, body in self.client.fetch(timeout=timeout):
            log.info(f"TOPIC [{msg.topic}]")
            log.debug(enhex(msg.payload[:]))

            for obj in body:
                self.notify(obj)

    def worker_stop(self):
        del self.client
