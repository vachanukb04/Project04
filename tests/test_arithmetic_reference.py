import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from arithmetic_reference import dot4, requantize


class ArithmeticContractTests(unittest.TestCase):
    def test_dot4_signed_bytes_and_packing(self):
        self.assertEqual(dot4(0x04030201, 0x08070605), (70, False))
        self.assertEqual(dot4(0x80808080, 0x80808080), (65536, False))
        self.assertEqual(dot4(0x80808080, 0x7F7F7F7F), (-65024, False))
        self.assertEqual(dot4(0xFFFFFFFF, 0x01010101, 7), (3, False))

    def test_dot4_wrap_and_overflow(self):
        self.assertEqual(dot4(1, 1, 2147483647), (-2147483648, True))
        self.assertEqual(dot4(255, 1, -2147483648), (2147483647, True))
        self.assertEqual(dot4(0, 0, -2147483648), (-2147483648, False))

    def test_rounding_ties_and_neighbors(self):
        for value, expected in [(1, 1), (-1, -1), (3, 2), (-3, -2), (0, 0)]:
            with self.subTest(value=value):
                self.assertEqual(requantize(value, 1, 1), (expected, False))
        self.assertEqual(requantize(1, 1, 2), (0, False))
        self.assertEqual(requantize(-1, 1, 2), (0, False))

    def test_saturation_extremes_and_zero(self):
        self.assertEqual(requantize(2147483647, 2147483647, 0), (127, False))
        self.assertEqual(requantize(-2147483648, 2147483647, 0), (-128, False))
        self.assertEqual(requantize(-2147483648, 2147483647, 63), (0, False))
        self.assertEqual(requantize(-2147483648, 0, 0, 127), (127, False))

    def test_activation_clamps_and_config_error(self):
        self.assertEqual(requantize(-5, 1, 0, clamp_min=0), (0, False))
        self.assertEqual(requantize(0, 1, 0, clamp_min=4, clamp_max=4), (4, False))
        self.assertEqual(requantize(1, 1, 0, clamp_min=12, clamp_max=-12), (0, True))

    def test_all_shift_values(self):
        for shift in range(64):
            with self.subTest(shift=shift):
                self.assertEqual(requantize(0, 2147483647, shift, -3), (-3, False))

    def test_invalid_python_inputs(self):
        for call in [lambda: dot4(-1, 0), lambda: dot4(0, 0, 1 << 31),
                     lambda: requantize(0, -1, 0), lambda: requantize(0, 0, 64)]:
            with self.assertRaises(ValueError):
                call()


if __name__ == "__main__":
    unittest.main()
