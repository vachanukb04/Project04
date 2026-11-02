"""Integer reference contract for the first Project04 arithmetic blocks.

These functions define numerical results, not cycle or timing behavior.
"""


def _signed_byte(value):
    return value - 256 if value & 128 else value


def dot4(a, b, accumulator=0):
    """Return (wrapped signed INT32 result, overflow) from packed byte operands."""
    if not 0 <= a < (1 << 32) or not 0 <= b < (1 << 32):
        raise ValueError("packed operands must be unsigned 32-bit words")
    if not -(1 << 31) <= accumulator < (1 << 31):
        raise ValueError("accumulator must be signed INT32")
    total = accumulator + sum(
        _signed_byte((a >> (8 * k)) & 255) * _signed_byte((b >> (8 * k)) & 255)
        for k in range(4)
    )
    wrapped = (total + (1 << 31)) % (1 << 32) - (1 << 31)
    return wrapped, not -(1 << 31) <= total < (1 << 31)


def requantize(accumulator, multiplier, shift, zero_point=0, clamp_min=-128, clamp_max=127):
    """Return (INT8 result, config_error); halfway cases round away from zero."""
    if not -(1 << 31) <= accumulator < (1 << 31):
        raise ValueError("accumulator must be signed INT32")
    if not 0 <= multiplier < (1 << 31) or not 0 <= shift <= 63:
        raise ValueError("invalid multiplier or shift")
    if any(not -128 <= x <= 127 for x in (zero_point, clamp_min, clamp_max)):
        raise ValueError("zero point and clamps must be signed INT8")
    if clamp_min > clamp_max:
        return 0, True
    product = accumulator * multiplier
    quotient, remainder = divmod(abs(product), 1 << shift)
    if remainder * 2 >= (1 << shift):
        quotient += 1
    rounded = -quotient if product < 0 else quotient
    return min(clamp_max, max(clamp_min, rounded + zero_point)), False
