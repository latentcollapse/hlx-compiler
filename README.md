# HLX Compiler

**Deterministic GPU execution via Vulkan/SPIR-V**

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)]()
[![Status](https://img.shields.io/badge/status-production%20ready-green)]()

---

## Quick Start

```bash
# Install (one command)
./install.sh

# Run benchmark
./target/release/train_transformer_full

# Expected: 0.4783 final loss (6.7% better than CUDA's 0.5128)
```

**Full instructions:** [QUICKSTART.md](QUICKSTART.md)

---

## What Is This?

HLX is an open-source language and compiler that achieves **deterministic, high-performance GPU execution** using Vulkan/SPIR-V.

**Key Results:**
- ✅ **6.7% better than CUDA** on transformer training (0.4783 vs 0.5128 loss)
- ✅ **100% reproducible** (bit-exact across runs and hardware)
- ✅ **Cross-vendor** (works on AMD, NVIDIA, Intel via pure Vulkan)
- ✅ **Open standards** (no vendor lock-in, no proprietary APIs)

---

## For AMD

See **[README_AMD.md](README_AMD.md)** for:
- Complete technical overview
- Benchmark methodology
- Architecture deep-dive
- Collaboration opportunities
- Integration strategies

**TL;DR:** HLX proves deterministic GPU compute is viable today using open standards (Vulkan/SPIR-V). Built on AMD's strategic investments (ROCm, MLIR, Vulkan).

---

## Documentation

| Document | Description |
|----------|-------------|
| **[QUICKSTART.md](QUICKSTART.md)** | 5-minute getting started guide |
| **[README_AMD.md](README_AMD.md)** | Complete technical overview for AMD |
| **[benchmarks/BENCHMARK_RESULTS.md](benchmarks/BENCHMARK_RESULTS.md)** | Detailed benchmark analysis |
| **[examples/](examples/)** | Example programs (hello world, matrix multiply) |
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | System architecture |
| **[docs/CONTRACTS.md](docs/CONTRACTS.md)** | Contract specifications |

---

## Repository Structure

```
hlx-compiler/
├── install.sh              # One-command installer
├── QUICKSTART.md           # 5-minute setup
├── README_AMD.md           # Technical overview for AMD
│
├── runtime/                # HLX language runtimes
│   └── hlx_runtime/        # 4 runtimes, 3 wire formats, 433 tests
│
├── src/                    # Rust compiler source
│   ├── lib.rs              # Vulkan context
│   └── bin/                # Training binaries
│       └── train_transformer_full.rs
│
├── shader/                 # GLSL compute shaders
│   ├── gemm.glsl
│   ├── layernorm.glsl
│   └── ...
│
├── benchmarks/             # Benchmark data
│   ├── BENCHMARK_RESULTS.md
│   └── results/
│       ├── cuda_results.json    # CUDA baseline
│       └── training_curve.csv   # HLX results
│
└── examples/               # Example programs
    ├── hello_world.hlxl
    └── matrix_multiply.hlxl
```

---

## Benchmark Summary

| Metric | HLX (Vulkan) | PyTorch (CUDA) | Winner |
|--------|--------------|----------------|--------|
| **Final Loss** | **0.4783** | 0.5128 | **HLX (6.7% better)** |
| **Reproducibility** | **100% (bit-exact)** | ~95% | **HLX** |
| **Hardware Support** | AMD + NVIDIA + Intel | NVIDIA only | **HLX** |

Full analysis: [benchmarks/BENCHMARK_RESULTS.md](benchmarks/BENCHMARK_RESULTS.md)

---

## Why It Matters

**For Developers:**
- Write once, run on any GPU (AMD, NVIDIA, Intel)
- Guaranteed reproducible results
- No kernel programming required

**For AMD:**
- Validates Vulkan/SPIR-V for ML workloads
- Enables "reproducible AI on AMD" narrative
- Provides reference implementation for ROCm integration

**For Science:**
- Reproducible ML experiments
- Auditable computation
- Cross-platform validation

---

## Quick Links

- 🚀 **[Get Started](QUICKSTART.md)** - Install and run in 5 minutes
- 📊 **[Benchmarks](benchmarks/BENCHMARK_RESULTS.md)** - Detailed performance analysis
- 🏢 **[For AMD](README_AMD.md)** - Technical overview and collaboration
- 📝 **[Examples](examples/)** - Sample programs
- 💬 **[Contact](mailto:latentcollapse@gmail.com)** - Questions or feedback

---

## License

Apache 2.0 - Open Source

## Author

Matt Cohn ([@latentcollapse](https://github.com/latentcollapse))

Independent developer committed to open, reproducible, cross-vendor GPU compute.

---

**Built with ❤️ for deterministic computation**
