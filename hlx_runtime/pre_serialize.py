"""
Pre-Serialize Validator
Reference: CONTRACT_804
"""
import unicodedata
import math
from typing import Any
from .errors import E_FLOAT_SPECIAL, E_KEY_ORDER, E_TRAILING_COMMA, E_VALIDATION_FAIL, HLXError

class ValidationError(HLXError):
    def __init__(self, message: str):
        super().__init__(E_VALIDATION_FAIL, message)

def pre_serialize(value: Any) -> Any:
    """
    Apply normalization rules before serialization.
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            # Using ValueError or custom error?
            # LC encoder raises LCEncodeError with E_FLOAT_SPECIAL
            # Here we can raise ValidationError with code?
            raise ValueError(f"{E_FLOAT_SPECIAL}: NaN/Inf not allowed")
        if value == 0.0:
            return 0.0 # Normalize -0.0 to 0.0
        return value
    
    if isinstance(value, str):
        # UTF-8 NFC
        norm = unicodedata.normalize('NFC', value)
        # Whitespace cleanup
        norm = norm.replace('\r\n', '\n')
        norm = norm.rstrip()
        return norm

    if isinstance(value, dict):
        # Key ordering: return dict with sorted keys
        sorted_keys = sorted(value.keys())
        return {k: pre_serialize(value[k]) for k in sorted_keys}

    if isinstance(value, list):
        return [pre_serialize(v) for v in value]

    return value
