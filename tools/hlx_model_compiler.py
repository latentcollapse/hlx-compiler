import argparse
import json
import hashlib
import os
import sys
import numpy as np
import onnx
from onnx import numpy_helper

def serialize_weights_deterministically(model: onnx.ModelProto) -> bytes:
    """
    Serializes all model weights (initializers) from an ONNX model into a single
    deterministic byte stream. Weights are sorted by name, converted to float64,
    and then their raw byte representations are concatenated.
    """
    if not model.graph.initializer:
        return b"" 

    # 1. Sort initializers by name for deterministic order
    sorted_initializers = sorted(model.graph.initializer, key=lambda init: init.name)

    serialized_parts = []
    for initializer in sorted_initializers:
        # 2. Convert TensorProto to a NumPy array
        np_array = numpy_helper.to_array(initializer)

        # 3. Ensure float64 data type for deterministic serialization
        if np_array.dtype != np.float64:
            np_array = np_array.astype(np.float64)

        # 4. Get the raw bytes (standardized endianness implicit in tobytes if on same arch)
        serialized_parts.append(np_array.tobytes())

    return b"".join(serialized_parts)

def main():
    parser = argparse.ArgumentParser(description="Compile ONNX model for HLX Contract.")
    parser.add_argument("onnx_path", type=str, help="Path to the ONNX model file.")
    args = parser.parse_args()

    if not os.path.exists(args.onnx_path):
        print(f"Error: File '{args.onnx_path}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        # Load Model
        model = onnx.load(args.onnx_path)
        
        # Serialize & Hash
        serialized_weights = serialize_weights_deterministically(model)
        blake2b = hashlib.blake2b()
        blake2b.update(serialized_weights)
        model_hash = blake2b.hexdigest()

        # Generate Metadata
        output_data = {
            "model_hash": model_hash,
            "metadata": {
                "model_name": os.path.basename(args.onnx_path),
                "num_initializers": len(model.graph.initializer),
                "total_weight_bytes": len(serialized_weights),
                "strategy": "sorted_by_name_float64_blake2b"
            }
        }

        print(json.dumps(output_data, indent=4))

    except Exception as e:
        print(f"Compilation failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
