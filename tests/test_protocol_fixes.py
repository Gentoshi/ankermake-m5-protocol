import unittest
from unittest import mock


class TestFileUploadInfoFromFile(unittest.TestCase):

    def test_from_file_passes_type(self):
        from libflagship.ppppapi import FileUploadInfo

        with mock.patch("builtins.open", mock.mock_open(read_data=b"test data")):
            fui = FileUploadInfo.from_file("test.gcode", "user", "uid", "mid", type=1)

        self.assertEqual(fui.type, 1)
        self.assertEqual(fui.size, 9)
        self.assertEqual(fui.name, "test.gcode")


class TestMakeMqttPkt(unittest.TestCase):

    def test_packet_num_is_respected(self):
        from libflagship.mqttapi import AnkerMQTTBaseClient

        pkt = AnkerMQTTBaseClient.make_mqtt_pkt("guid-1234", b'{"test":1}', packet_num=42)
        self.assertEqual(pkt.packet_num, 42)

    def test_packet_num_defaults_to_zero(self):
        from libflagship.mqttapi import AnkerMQTTBaseClient

        pkt = AnkerMQTTBaseClient.make_mqtt_pkt("guid-1234", b'{"test":1}')
        self.assertEqual(pkt.packet_num, 0)


class TestFileTransferNoDoubleNull(unittest.TestCase):

    def test_bytes_fui_ends_with_single_null(self):
        from libflagship.ppppapi import FileUploadInfo

        fui = FileUploadInfo(
            name="test.gcode", size="9", md5="abc123",
            user_name="user", user_id="uid", machine_id="mid",
        )
        raw = bytes(fui)
        self.assertTrue(raw.endswith(b"\x00"))
        self.assertFalse(raw.endswith(b"\x00\x00"))


if __name__ == "__main__":
    unittest.main()
