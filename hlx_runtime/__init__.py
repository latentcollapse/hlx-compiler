"""
HLX Runtime - Python implementation of the HLX Latent Space system.
"""

from .lc_codec import (
    encode_lcb, decode_lcb, encode_lct,
    compute_hash, canonical_hash, verify_bijection,
    wrap_contract, unwrap_contract,
    LCCodecError, LCEncodeError, LCDecodeError,
)

from .errors import (
    E_LC_PARSE, E_CONTRACT_STRUCTURE, E_HANDLE_UNRESOLVED,
    E_ENV_PAYLOAD_HASH_MISMATCH, E_VALIDATION_FAIL, E_INVALID_INPUT,
    E_CAS_READ_FAIL, E_CAS_WRITE_FAIL,
    HLXError,
)

from .contracts import (
    CONTRACT_IDS, is_contract_wrapped,
    wrap_literal, unwrap_literal, validate_contract,
)

from .cas import CASStore, get_cas_store

from .tables import MerkleTree, StateTable

from .ls_ops import (
    LSContext, ls_collapse, ls_resolve,
    ls_encode, ls_decode, ls_hash,
    ls_validate, ls_wrap, ls_unwrap,
)

__version__ = '1.0.1'
