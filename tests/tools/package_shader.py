#!/usr/bin/env python3
"""
HLX Shader Packager (Contract 900)
Wraps SPIR-V binaries into HLX transport contracts.
"""

import sys
import os
import argparse
import json

# Ensure we can import hlx_runtime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hlx_runtime.ls_ops import collapse, resolve
from hlx_runtime.contracts import CONTRACT_IDS, validate_contract

def package_shader(spv_path: str, entry_point: str, stage: str, descriptors: list):
    try:
        with open(spv_path, 'rb') as f:
            spv_bytes = f.read()
            
        print(f"Read {len(spv_bytes)} bytes from {spv_path}")
        
        # Construct Payload
        payload = {
            'spirv_binary': spv_bytes,
            'entry_point': entry_point,
            'shader_stage': stage,
            'descriptor_bindings': descriptors
        }
        
        # Wrap
        contract_id = CONTRACT_IDS.get('VULKAN_SHADER', 900)
        wrapped = { str(contract_id): payload }
        
        # Validate
        print("Validating contract...")
        # Note: validate_contract returns normalized inputs or raises
        validate_contract(wrapped)
        print("Validation successful.")
        
        # Collapse
        print("Collapsing to Latent Space...")
        handle = collapse(wrapped)
        
        print(f"\nSUCCESS: Shader packaged.")
        print(f"Handle: {handle}")
        
        # Verify resolution
        resolved = resolve(handle)
        if resolved == wrapped:
            print("Verification: Resolved matches original.")
        else:
            print("Verification: FAILED!")
            
        return handle

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Package SPIR-V shader into HLX Contract 900")
    parser.add_argument('spv_file', help="Path to SPIR-V binary")
    parser.add_argument('--entry', default="main", help="Entry point function name")
    parser.add_argument('--stage', required=True, choices=['compute', 'vertex', 'fragment'], help="Shader stage")
    parser.add_argument('--descriptors', nargs='*', default=[], help="List of descriptor binding handles")
    
    args = parser.parse_args()
    
    package_shader(args.spv_file, args.entry, args.stage, args.descriptors)

if __name__ == '__main__':
    main()
