"""
HLX LC-B Client - Python client for sending LC-B instruction batches to the Vulkan service.

Usage:
    from hlx_lcb_client import LCBClient, LCBBatchBuilder

    client = LCBClient()

    # Build a batch
    builder = LCBBatchBuilder()
    builder.gemm(a_data, b_data, m, k, n)
    builder.softmax(logits, num_rows, row_size)

    # Execute
    results = client.execute(builder.build())
"""

import socket
import struct
from typing import List, Tuple, Optional, Union
from dataclasses import dataclass
import numpy as np

DEFAULT_SOCKET_PATH = "/tmp/hlx_vulkan.sock"

# LC-B Magic and Version
LCB_MAGIC = 0x3142434C  # "LCB1" in little-endian
LCB_VERSION = 1

# Contract IDs
class ContractID:
    # Parser tier
    BINARY_SERIALIZER = 800
    INSTRUCTION_PARSER = 801
    TYPE_VALIDATOR = 802
    DETERMINISM_VERIFIER = 803
    CONTRACT_VALIDATOR = 805
    ERROR_HANDLER = 806

    # GPU tier
    VULKAN_SHADER = 900
    COMPUTE_KERNEL = 901
    PIPELINE_CONFIG = 902

    # Transformer operations
    TRANSFORMER_FORWARD = 903
    TRANSFORMER_BACKWARD = 904
    ADAM_OPTIMIZER = 905

    # Tensor operations
    TENSOR_GEMM = 906
    TENSOR_LAYERNORM = 907
    TENSOR_GELU = 908
    TENSOR_SOFTMAX = 909
    TENSOR_CROSS_ENTROPY = 910


# Parameter types (must match Rust parser)
class ParamType:
    NULL = 0
    BOOL = 1
    INT = 2
    FLOAT = 3
    TEXT = 4
    BYTES = 5
    ARRAY = 6
    OBJECT = 7
    HANDLE = 8
    CHAIN_PREVIOUS = 9
    CHAIN_FROM = 10


@dataclass
class ContractResult:
    """Result from executing a contract."""
    result_type: str  # "null", "bool", "int", "float", "tensor", "handle", "error"
    value: Union[None, bool, int, float, np.ndarray, bytes, str]
    shape: Optional[Tuple[int, ...]] = None


def encode_leb128_u32(value: int) -> bytes:
    """Encode unsigned 32-bit integer as LEB128."""
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value != 0:
            byte |= 0x80
        result.append(byte)
        if value == 0:
            break
    return bytes(result)


def encode_leb128_i64(value: int) -> bytes:
    """Encode signed 64-bit integer as LEB128."""
    result = bytearray()
    negative = value < 0
    while True:
        byte = value & 0x7F
        value >>= 7

        if negative:
            more = value != -1 or (byte & 0x40) == 0
        else:
            more = value != 0 or (byte & 0x40) != 0

        if more:
            byte |= 0x80
        result.append(byte)
        if not more:
            break
    return bytes(result)


def decode_leb128_u32(data: bytes, offset: int) -> Tuple[int, int]:
    """Decode LEB128-encoded unsigned 32-bit integer. Returns (value, new_offset)."""
    result = 0
    shift = 0
    while True:
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result, offset


def decode_leb128_i64(data: bytes, offset: int) -> Tuple[int, int]:
    """Decode LEB128-encoded signed 64-bit integer. Returns (value, new_offset)."""
    result = 0
    shift = 0
    while True:
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if (byte & 0x80) == 0:
            break

    # Sign extend if negative
    if shift < 64 and (byte & 0x40):
        result |= (~0 << shift)

    return result, offset


class LCBBatchBuilder:
    """Builder for LC-B instruction batches."""

    def __init__(self):
        self.instructions = []

    def _add_instruction(self, contract_id: int, params: dict):
        """Add an instruction to the batch."""
        self.instructions.append((contract_id, params))
        return len(self.instructions) - 1  # Return index for chaining

    def gemm(self, a: np.ndarray, b: np.ndarray,
             transpose_a: bool = False, transpose_b: bool = False) -> int:
        """Add GEMM (matrix multiply) operation: C = A @ B"""
        m, k1 = a.shape if not transpose_a else (a.shape[1], a.shape[0])
        k2, n = b.shape if not transpose_b else (b.shape[1], b.shape[0])

        if k1 != k2:
            raise ValueError(f"Inner dimensions must match: {k1} != {k2}")

        return self._add_instruction(ContractID.TENSOR_GEMM, {
            "a": ("tensor", a.astype(np.float32)),
            "b": ("tensor", b.astype(np.float32)),
            "m": ("int", m),
            "k": ("int", k1),
            "n": ("int", n),
            "transpose_a": ("bool", transpose_a),
            "transpose_b": ("bool", transpose_b),
        })

    def layernorm(self, input: np.ndarray, gamma: np.ndarray, beta: np.ndarray,
                  eps: float = 1e-5) -> int:
        """Add layer normalization operation."""
        if len(input.shape) < 2:
            raise ValueError("Input must have at least 2 dimensions")

        row_size = input.shape[-1]
        num_rows = input.size // row_size

        return self._add_instruction(ContractID.TENSOR_LAYERNORM, {
            "input": ("tensor", input.astype(np.float32)),
            "gamma": ("tensor", gamma.astype(np.float32)),
            "beta": ("tensor", beta.astype(np.float32)),
            "num_rows": ("int", num_rows),
            "row_size": ("int", row_size),
            "eps": ("float", eps),
        })

    def gelu(self, input: np.ndarray) -> int:
        """Add GELU activation operation."""
        return self._add_instruction(ContractID.TENSOR_GELU, {
            "input": ("tensor", input.astype(np.float32)),
        })

    def softmax(self, input: np.ndarray, dim: int = -1) -> int:
        """Add softmax operation along specified dimension."""
        if dim < 0:
            dim = len(input.shape) + dim

        row_size = input.shape[dim]
        num_rows = input.size // row_size

        return self._add_instruction(ContractID.TENSOR_SOFTMAX, {
            "input": ("tensor", input.astype(np.float32)),
            "num_rows": ("int", num_rows),
            "row_size": ("int", row_size),
        })

    def cross_entropy(self, logits: np.ndarray, targets: np.ndarray,
                      ignore_index: int = 0) -> int:
        """Add cross-entropy loss operation."""
        vocab_size = logits.shape[-1]

        return self._add_instruction(ContractID.TENSOR_CROSS_ENTROPY, {
            "logits": ("tensor", logits.astype(np.float32)),
            "targets": ("tensor", targets.astype(np.uint32)),
            "vocab_size": ("int", vocab_size),
            "ignore_index": ("int", ignore_index),
        })

    def transformer_forward(self, input_ids: np.ndarray, config_json: str) -> int:
        """Add transformer forward pass operation."""
        return self._add_instruction(ContractID.TRANSFORMER_FORWARD, {
            "input_ids": ("tensor", input_ids.astype(np.uint32)),
            "config": ("string", config_json),
        })

    def chain(self, result_idx: int) -> dict:
        """Create a chain reference to a previous result."""
        return ("chain", result_idx)

    def build(self) -> bytes:
        """Build the LC-B batch binary."""
        import hashlib

        data = bytearray()

        # Header: magic (4 bytes), version (1 byte), batch_id (32 bytes), num_instructions (LEB128)
        data.extend(struct.pack("<I", LCB_MAGIC))
        data.append(LCB_VERSION)

        # Generate batch_id (hash of instruction count for determinism)
        batch_id_hash = hashlib.sha256(struct.pack("<I", len(self.instructions))).digest()
        data.extend(batch_id_hash)

        data.extend(encode_leb128_u32(len(self.instructions)))

        # Each instruction
        for contract_id, params in self.instructions:
            # Contract ID (LEB128)
            data.extend(encode_leb128_u32(contract_id))

            # Number of params (LEB128)
            data.extend(encode_leb128_u32(len(params)))

            # Each param: name_len, name, type, value
            for name, (ptype, value) in params.items():
                # Name
                name_bytes = name.encode('utf-8')
                data.extend(encode_leb128_u32(len(name_bytes)))
                data.extend(name_bytes)

                # Type and value (matching Rust parser type tags)
                if ptype == "int":
                    data.append(ParamType.INT)  # 2
                    data.extend(encode_leb128_i64(value))
                elif ptype == "float":
                    data.append(ParamType.FLOAT)  # 3
                    # Rust expects f64 (8 bytes)
                    data.extend(struct.pack("<d", float(value)))
                elif ptype == "bool":
                    data.append(ParamType.BOOL)  # 1
                    data.append(1 if value else 0)
                elif ptype == "tensor":
                    # Encode tensor as Bytes with shape header
                    data.append(ParamType.BYTES)  # 5
                    arr = np.ascontiguousarray(value)
                    # Build tensor payload: [ndim:u8][shape...][f32 data]
                    tensor_payload = bytearray()
                    tensor_payload.append(len(arr.shape))
                    for dim in arr.shape:
                        tensor_payload.extend(struct.pack("<I", dim))
                    flat = arr.flatten().astype(np.float32)
                    tensor_payload.extend(flat.tobytes())
                    # Write payload length + payload
                    data.extend(encode_leb128_u32(len(tensor_payload)))
                    data.extend(tensor_payload)
                elif ptype == "string":
                    data.append(ParamType.TEXT)  # 4
                    value_bytes = value.encode('utf-8')
                    data.extend(encode_leb128_u32(len(value_bytes)))
                    data.extend(value_bytes)
                elif ptype == "chain":
                    data.append(ParamType.CHAIN_FROM)  # 10
                    data.extend(encode_leb128_u32(value))

        # Compute and append SHA256 signature
        signature = hashlib.sha256(bytes(data)).digest()
        data.extend(signature)

        return bytes(data)


class LCBClient:
    """Client for the HLX-Vulkan LC-B execution service."""

    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path

    def execute(self, batch: bytes) -> List[ContractResult]:
        """Execute an LC-B batch and return results."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.socket_path)

            # Send request: [4 bytes length LE] [batch data]
            sock.sendall(struct.pack("<I", len(batch)))
            sock.sendall(batch)

            # Receive response: [4 bytes length LE] [response data]
            response_len_bytes = self._recv_exact(sock, 4)
            response_len = struct.unpack("<I", response_len_bytes)[0]

            response = self._recv_exact(sock, response_len)

            return self._parse_response(response)

        finally:
            sock.close()

    def _recv_exact(self, sock: socket.socket, n: int) -> bytes:
        """Receive exactly n bytes from socket."""
        data = bytearray()
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data.extend(chunk)
        return bytes(data)

    def _parse_response(self, data: bytes) -> List[ContractResult]:
        """Parse LC-B response binary."""
        offset = 0

        # Response type: 0 = success, 1 = error
        response_type = data[offset]
        offset += 1

        if response_type == 1:
            # Error response
            msg_len, offset = decode_leb128_u32(data, offset)
            msg = data[offset:offset + msg_len].decode('utf-8')
            raise RuntimeError(f"LC-B execution error: {msg}")

        # Success: parse results
        num_results, offset = decode_leb128_u32(data, offset)
        results = []

        for _ in range(num_results):
            result, offset = self._parse_result(data, offset)
            results.append(result)

        return results

    def _parse_result(self, data: bytes, offset: int) -> Tuple[ContractResult, int]:
        """Parse a single result from response."""
        result_type = data[offset]
        offset += 1

        if result_type == 0:  # Null
            return ContractResult("null", None), offset

        elif result_type == 1:  # Bool
            value = data[offset] != 0
            offset += 1
            return ContractResult("bool", value), offset

        elif result_type == 2:  # Int
            value, offset = decode_leb128_i64(data, offset)
            return ContractResult("int", value), offset

        elif result_type == 3:  # Float
            value = struct.unpack("<f", data[offset:offset + 4])[0]
            offset += 4
            return ContractResult("float", value), offset

        elif result_type == 4:  # Tensor
            # Shape
            num_dims, offset = decode_leb128_u32(data, offset)
            shape = []
            for _ in range(num_dims):
                dim, offset = decode_leb128_u32(data, offset)
                shape.append(dim)

            # Data
            num_elements, offset = decode_leb128_u32(data, offset)
            tensor_data = np.frombuffer(
                data[offset:offset + num_elements * 4],
                dtype=np.float32
            ).copy()
            offset += num_elements * 4

            if shape:
                tensor_data = tensor_data.reshape(shape)

            return ContractResult("tensor", tensor_data, tuple(shape)), offset

        elif result_type == 5:  # Handle (32-byte)
            handle = data[offset:offset + 32]
            offset += 32
            return ContractResult("handle", handle), offset

        elif result_type == 6:  # Error
            msg_len, offset = decode_leb128_u32(data, offset)
            msg = data[offset:offset + msg_len].decode('utf-8')
            offset += msg_len
            return ContractResult("error", msg), offset

        else:
            raise ValueError(f"Unknown result type: {result_type}")


def test_gemm():
    """Test GEMM operation."""
    print("Testing GEMM...")

    # Simple 2x2 matrix multiply
    a = np.array([[1, 2], [3, 4]], dtype=np.float32)
    b = np.array([[5, 6], [7, 8]], dtype=np.float32)

    builder = LCBBatchBuilder()
    builder.gemm(a, b)

    batch = builder.build()
    print(f"  Batch size: {len(batch)} bytes")
    print(f"  Expected: [[19, 22], [43, 50]]")

    # Try to execute if service is running
    try:
        client = LCBClient()
        results = client.execute(batch)
        print(f"  Result: {results[0].value}")
    except (FileNotFoundError, ConnectionRefusedError):
        print("  (Service not running, skipping execution)")


def test_softmax():
    """Test softmax operation."""
    print("Testing Softmax...")

    logits = np.array([[1, 2, 3, 4]], dtype=np.float32)

    builder = LCBBatchBuilder()
    builder.softmax(logits)

    batch = builder.build()
    print(f"  Batch size: {len(batch)} bytes")

    # Reference computation
    exp_logits = np.exp(logits - logits.max())
    expected = exp_logits / exp_logits.sum()
    print(f"  Expected: {expected}")

    try:
        client = LCBClient()
        results = client.execute(batch)
        print(f"  Result: {results[0].value}")
    except (FileNotFoundError, ConnectionRefusedError):
        print("  (Service not running, skipping execution)")


def test_batch():
    """Test batched operations."""
    print("Testing Batch (GEMM + GELU)...")

    a = np.random.randn(4, 8).astype(np.float32)
    b = np.random.randn(8, 4).astype(np.float32)

    builder = LCBBatchBuilder()
    builder.gemm(a, b)  # idx 0
    builder.gelu(a.flatten())  # idx 1

    batch = builder.build()
    print(f"  Batch size: {len(batch)} bytes")
    print(f"  2 operations in single batch")

    try:
        client = LCBClient()
        results = client.execute(batch)
        print(f"  GEMM result shape: {results[0].value.shape}")
        print(f"  GELU result shape: {results[1].value.shape}")
    except (FileNotFoundError, ConnectionRefusedError):
        print("  (Service not running, skipping execution)")


if __name__ == "__main__":
    print("=" * 60)
    print("HLX LC-B Client Test Suite")
    print("=" * 60)
    print()

    test_gemm()
    print()
    test_softmax()
    print()
    test_batch()

    print()
    print("=" * 60)
    print("Tests complete. Start service with: ./hlx_lcb_service")
    print("=" * 60)
