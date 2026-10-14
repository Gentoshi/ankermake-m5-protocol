import unittest
from unittest import mock
import click


class TestFileSizeType(unittest.TestCase):

    def _convert(self, value):
        from cli.util import FileSizeType
        ft = FileSizeType()
        with mock.patch.object(ft, 'fail', side_effect=click.ClickException("fail")):
            return ft.convert(value, None, None)

    def test_bare_bytes(self):
        self.assertEqual(self._convert("1024"), 1024)

    def test_kb(self):
        self.assertEqual(self._convert("1kb"), 1024)

    def test_mb(self):
        self.assertEqual(self._convert("42mb"), 42 * 1024**2)

    def test_gb(self):
        self.assertEqual(self._convert("17gb"), 17 * 1024**3)

    def test_invalid(self):
        with self.assertRaises(click.ClickException):
            self._convert("abc")


if __name__ == "__main__":
    unittest.main()
