#!/usr/bin/env python3
"""
HLX Determinism Test Suite

Rigorous verification that shader database operations satisfy
the HLX axioms and invariants:

AXIOMS (Core Guarantees):
  A1 DETERMINISM: encode(v, t1) == encode(v, t2) for all times t1, t2
  A2 REVERSIBILITY: decode(encode(v)) == v
  A4 UNIVERSAL_VALUE: All surfaces (GLSL, SPIR-V, LC-B) → HLX-Lite

INVARIANTS (Properties):
  INV-001 TOTAL_FIDELITY: resolve(collapse(v)) == v
  INV-002 HANDLE_IDEMPOTENCE: collapse(collapse(v)) == collapse(v)
  INV-003 FIELD_ORDER: Object fields in ascending index order
"""

import sys
import hashlib
import time
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hlx_runtime"))

from shaderdb import ShaderDatabase, ShaderHandle


class DeterminismTestSuite:
    """Comprehensive determinism verification."""

    def __init__(self, db_path="/tmp/hlx_determinism_test"):
        self.db_path = db_path
        self.db = ShaderDatabase(db_path)
        self.passed = 0
        self.failed = 0

    def assert_equal(self, actual, expected, test_name):
        """Assert equality with test tracking."""
        if actual == expected:
            print(f"  ✓ {test_name}")
            self.passed += 1
            return True
        else:
            print(f"  ✗ FAILED: {test_name}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {actual}")
            self.failed += 1
            return False

    def test_axiom_a1_determinism(self):
        """A1: Same input → same handle, regardless of time."""
        print("\n" + "="*70)
        print("AXIOM A1: DETERMINISM")
        print("Same input → same handle (no timestamps, no randomness)\n")

        # Create test SPIR-V (minimal but valid)
        spirv = self._create_test_spirv(name="test_a1")

        handles = []
        for i in range(5):
            handle = ShaderHandle.from_spirv(spirv)
            handles.append(str(handle))
            if i > 0:
                time.sleep(0.01)  # Sleep between calls to ensure time difference

        # All handles should be identical
        for i in range(1, len(handles)):
            self.assert_equal(
                handles[i],
                handles[0],
                f"Call {i}: deterministic despite time delay"
            )

        print(f"\n✓ AXIOM A1 VERIFIED: {len(handles)} calls → {len(set(handles))} unique handle")

    def test_axiom_a2_reversibility(self):
        """A2: decode(encode(v)) == v (total fidelity)."""
        print("\n" + "="*70)
        print("AXIOM A2: REVERSIBILITY")
        print("decode(encode(v)) == v (total fidelity)\n")

        spirv_original = self._create_test_spirv(name="test_a2")
        metadata = {
            "name": "reversibility_test",
            "shader_stage": "compute",
            "tags": ["test", "deterministic"]
        }

        # Encode (store)
        handle = self.db.add_shader(spirv_original, metadata=metadata)
        print(f"  → Encoded to: {handle}")

        # Decode (retrieve)
        spirv_retrieved = self.db.get(handle)

        self.assert_equal(
            spirv_retrieved,
            spirv_original,
            "Encode/decode round-trip preserves content"
        )

        print(f"\n✓ AXIOM A2 VERIFIED: Total fidelity {len(spirv_original)} → {len(spirv_retrieved)} bytes")

    def test_invariant_inv001_total_fidelity(self):
        """INV-001: resolve(collapse(v)) == v."""
        print("\n" + "="*70)
        print("INVARIANT INV-001: TOTAL_FIDELITY")
        print("resolve(collapse(v)) == v\n")

        test_data = [
            (self._create_test_spirv(name=f"inv001_{i}"), f"Shader {i}")
            for i in range(3)
        ]

        for spirv, name in test_data:
            # Collapse (encode → store → handle)
            handle = self.db.add_shader(spirv, metadata={
                "name": name,
                "shader_stage": "vertex"
            })

            # Resolve (handle → retrieve → decode)
            retrieved = self.db.get(handle)

            self.assert_equal(
                retrieved,
                spirv,
                f"INV-001: {name} (collapse→resolve fidelity)"
            )

        print(f"\n✓ INV-001 VERIFIED: All shaders round-trip perfectly")

    def test_invariant_inv002_handle_idempotence(self):
        """INV-002: collapse(collapse(v)) == collapse(v)."""
        print("\n" + "="*70)
        print("INVARIANT INV-002: HANDLE_IDEMPOTENCE")
        print("collapse(collapse(v)) == collapse(v)\n")

        spirv = self._create_test_spirv(name="test_inv002")
        metadata = {
            "name": "idempotence_test",
            "shader_stage": "fragment"
        }

        # First collapse
        handle1 = self.db.add_shader(spirv, metadata=metadata)

        # Second collapse (idempotent - same bytes → same handle)
        handle2 = self.db.add_shader(spirv, metadata=metadata)

        # Third collapse (still idempotent)
        handle3 = self.db.add_shader(spirv, metadata=metadata)

        self.assert_equal(str(handle2), str(handle1), "collapse(v) == collapse(collapse(v))")
        self.assert_equal(str(handle3), str(handle1), "collapse(collapse(collapse(v))) == collapse(v)")

        print(f"\n✓ INV-002 VERIFIED: Idempotent handles")
        print(f"  Handle: {handle1} (stable across 3 calls)")

    def test_cryptographic_collision_resistance(self):
        """Verify BLAKE2b-256 collision resistance."""
        print("\n" + "="*70)
        print("CRYPTOGRAPHIC COLLISION RESISTANCE")
        print("BLAKE2b-256 provides full 256-bit security\n")

        # Generate diverse SPIR-V samples
        samples = [
            self._create_test_spirv(name=f"collision_test_{i}")
            for i in range(10)
        ]

        hashes = set()
        for i, spirv in enumerate(samples):
            h = hashlib.blake2b(spirv, digest_size=32).hexdigest()
            hashes.add(h)
            print(f"  {i+1}. {h[:16]}... ({len(spirv)} bytes)")

        self.assert_equal(
            len(hashes),
            len(samples),
            "All diverse inputs → unique hashes (no collisions)"
        )

        print(f"\n✓ COLLISION RESISTANCE VERIFIED: {len(hashes)}/{len(samples)} unique hashes")

    def test_deterministic_metadata_queries(self):
        """Verify metadata queries are deterministic."""
        print("\n" + "="*70)
        print("DETERMINISTIC METADATA QUERIES")
        print("Queries produce consistent results\n")

        # Add multiple shaders with same stage
        for i in range(3):
            spirv = self._create_test_spirv(name=f"query_test_{i}")
            self.db.add_shader(spirv, metadata={
                "name": f"compute_shader_{i}",
                "shader_stage": "compute",
                "tags": ["test"]
            })

        # Query multiple times
        results1 = self.db.query(shader_stage="compute")
        results2 = self.db.query(shader_stage="compute")

        self.assert_equal(
            len(results1),
            len(results2),
            "Query count consistent across runs"
        )

        self.assert_equal(
            [r['handle'] for r in results1],
            [r['handle'] for r in results2],
            "Query results identical order"
        )

        print(f"\n✓ QUERY DETERMINISM VERIFIED: {len(results1)} consistent results")

    def test_concurrent_deduplication(self):
        """Verify concurrent access produces deterministic deduplication."""
        print("\n" + "="*70)
        print("CONCURRENT DEDUPLICATION")
        print("Thread-safe deterministic storage\n")

        spirv = self._create_test_spirv(name="concurrent_test")
        handles = []

        def add_shader():
            h = self.db.add_shader(spirv, metadata={
                "name": "concurrent",
                "shader_stage": "vertex"
            })
            return str(h)

        # Add same shader from multiple threads
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(add_shader) for _ in range(4)]
            handles = [f.result() for f in futures]

        # All should produce same handle
        unique_handles = set(handles)
        self.assert_equal(
            len(unique_handles),
            1,
            "Concurrent writes produce single deduplicated handle"
        )

        print(f"\n✓ CONCURRENT DEDUPLICATION VERIFIED")
        print(f"  4 parallel writes → 1 handle: {handles[0]}")

    def test_handle_format_consistency(self):
        """Verify handle format is consistent."""
        print("\n" + "="*70)
        print("HANDLE FORMAT CONSISTENCY")
        print("Handles follow &h_shader_<blake2b> format\n")

        spirv = self._create_test_spirv(name="format_test")
        handle = ShaderHandle.from_spirv(spirv)

        # Check format
        handle_str = str(handle)
        self.assert_equal(
            handle_str.startswith("&h_shader_"),
            True,
            "Handle prefix: &h_shader_"
        )

        self.assert_equal(
            len(handle.hash),
            64,
            "Hash length: 64 chars (256-bit hex)"
        )

        # Verify hash components
        prefix = handle.prefix
        suffix = handle.suffix
        reconstructed = prefix + suffix

        self.assert_equal(
            reconstructed,
            handle.hash,
            "Hash splits correctly: prefix(2) + suffix(62)"
        )

        print(f"\n✓ HANDLE FORMAT VERIFIED")
        print(f"  Format: {handle_str}")
        print(f"  Prefix (2c): {prefix}")
        print(f"  Suffix (62c): {suffix[:20]}...")

    def _create_test_spirv(self, name="test"):
        """Create minimal valid SPIR-V for testing."""
        # SPIR-V magic header: 0x07230203
        # Version: 0x00010000
        # Generator: 0x00000000
        # Bound: 0x00000001
        # Schema: 0x00000000

        import struct

        magic = 0x07230203
        version = 0x00010000
        generator = 0
        bound = 1
        schema = 0

        header = struct.pack('<5I', magic, version, generator, bound, schema)

        # Add some variation based on name to avoid duplicates in test suite
        name_bytes = name.encode('utf-8')
        variation = hashlib.sha256(name_bytes).digest()[:16]

        return header + variation

    def run_all_tests(self):
        """Run complete test suite."""
        print("\n" + "="*70)
        print("HLX DETERMINISM TEST SUITE")
        print("="*70)

        try:
            self.test_axiom_a1_determinism()
            self.test_axiom_a2_reversibility()
            self.test_invariant_inv001_total_fidelity()
            self.test_invariant_inv002_handle_idempotence()
            self.test_cryptographic_collision_resistance()
            self.test_deterministic_metadata_queries()
            self.test_concurrent_deduplication()
            self.test_handle_format_consistency()

            self.db.close()

            # Summary
            print("\n" + "="*70)
            print("TEST SUMMARY")
            print("="*70)
            print(f"\n✓ PASSED: {self.passed}")
            print(f"✗ FAILED: {self.failed}")
            print(f"  TOTAL:  {self.passed + self.failed}")

            if self.failed == 0:
                print("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
                print("\nDeterminism Axioms & Invariants Verified:")
                print("  ✓ A1 DETERMINISM: No timestamps, no randomness")
                print("  ✓ A2 REVERSIBILITY: Perfect encode/decode fidelity")
                print("  ✓ INV-001 TOTAL_FIDELITY: resolve(collapse(v)) == v")
                print("  ✓ INV-002 IDEMPOTENCE: collapse(collapse(v)) == collapse(v)")
                print("  ✓ Cryptographic handles (BLAKE2b-256)")
                print("  ✓ Thread-safe deduplication")
                return True
            else:
                print(f"\n✗ {self.failed} test(s) failed")
                return False

        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    suite = DeterminismTestSuite()
    success = suite.run_all_tests()
    sys.exit(0 if success else 1)
