# Tests

Test suite, examples, and utilities for HLX Vulkan integration.

## Structure

- **examples/** - Complete example applications
- **python/** - Python bindings and utilities
- **tools/** - Development and testing tools
- **hlx_runtime/** - HLX runtime integration tests

## Examples

Complete working examples demonstrating:
- GPU initialization
- Shader compilation
- Pipeline creation
- Compute operations
- Data transfer

See individual example directories for documentation.

## Python Utilities

Python bindings and utilities for testing and integration:

```bash
# Install
pip install -r python/requirements.txt

# Run tests
pytest python/tests/
```

## Tools

Development tools for benchmarking, profiling, and debugging GPU operations.

## Running Tests

```bash
# Run Rust tests
cargo test

# Run integration tests
cargo test --release
```
