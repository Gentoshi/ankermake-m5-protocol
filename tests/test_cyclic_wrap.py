import unittest


class TestCyclicU16WrapDefault(unittest.TestCase):

    def test_default_wrap_is_16bit_half_range(self):
        from libflagship.cyclic import CyclicU16

        c = CyclicU16(0)
        self.assertEqual(c.wrap, 0x8000)

    def test_wraparound_comparison_with_default(self):
        from libflagship.cyclic import CyclicU16

        x = CyclicU16(0xFFFE)
        y = CyclicU16(0x0001)
        self.assertTrue(x < y)

        x = CyclicU16(0x0001)
        y = CyclicU16(0xFFFE)
        self.assertFalse(x < y)


if __name__ == "__main__":
    unittest.main()
