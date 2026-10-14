import unittest
from unittest import mock


def make_mqtt_service():
    from web.service.mqtt import MqttQueue
    with mock.patch.object(MqttQueue, "__init__", lambda self: None):
        svc = MqttQueue()
    return svc


class TestGcodeSafety(unittest.TestCase):

    def setUp(self):
        self.svc = make_mqtt_service()

    def test_m104_clamps_to_260(self):
        msg = {"cmdData": "M104 S300", "cmdLen": 9}
        result = self.svc.validate_gcode_payload(msg)
        self.assertEqual(result["cmdData"], "M104 S260")

    def test_m140_clamps_to_100(self):
        msg = {"cmdData": "M140 S150", "cmdLen": 9}
        result = self.svc.validate_gcode_payload(msg)
        self.assertEqual(result["cmdData"], "M140 S100")

    def test_g1_e_only_clamps(self):
        msg = {"cmdData": "G1 E150 F300", "cmdLen": 11}
        result = self.svc.validate_gcode_payload(msg)
        self.assertEqual(result["cmdData"], "G1 E100 F300")

    def test_g1_with_xyz_and_e_clamps(self):
        msg = {"cmdData": "G1 X10 Y20 E150 F300", "cmdLen": 20}
        result = self.svc.validate_gcode_payload(msg)
        self.assertIn("E100", result["cmdData"])
        self.assertNotIn("E150", result["cmdData"])

    def test_g1_negative_e_clamps(self):
        msg = {"cmdData": "G1 E-150 F300", "cmdLen": 13}
        result = self.svc.validate_gcode_payload(msg)
        self.assertIn("E-100", result["cmdData"])

    def test_g1_with_xyz_negative_e_clamps(self):
        msg = {"cmdData": "G1 X10 Y20 E-150 F300", "cmdLen": 22}
        result = self.svc.validate_gcode_payload(msg)
        self.assertIn("E-100", result["cmdData"])
        self.assertNotIn("E-150", result["cmdData"])

    def test_safe_gcode_passes_through(self):
        msg = {"cmdData": "G1 X10 Y20 E5 F300", "cmdLen": 19}
        result = self.svc.validate_gcode_payload(msg)
        self.assertEqual(result["cmdData"], "G1 X10 Y20 E5 F300")

    def test_non_gcode_passes_through(self):
        msg = {"cmdData": "M105", "cmdLen": 4}
        result = self.svc.validate_gcode_payload(msg)
        self.assertEqual(result["cmdData"], "M105")


if __name__ == "__main__":
    unittest.main()
