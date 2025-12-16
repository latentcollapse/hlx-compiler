# HLX+Vulkan Compute Engine
## Deterministic GPU Compute with Content-Addressed Storage

[![Status](https://img.shields.io/badge/status-experimental-orange)]()
[![Tests](https://img.shields.io/badge/tests-106%2F106-brightgreen)]()

HLX+Vulkan integrates HLX's deterministic execution model with Vulkan compute shaders.

## Current Status

**Phase 1 (Starting):** Vulkan runtime integration
- ✅ Contract schemas (CONTRACT_900-902) implemented
- ✅ SPIR-V packaging tool working
- ⏳ VulkanContext initialization (next)
- ⏳ Shader loading (planned)
- ⏳ Pipeline creation (planned)
- ⏳ Kernel execution (planned)

See [docs/VULKAN_ROADMAP.md](docs/VULKAN_ROADMAP.md) for full 9-13 week roadmap.

## Why HLX+Vulkan?

**Problem:** CUDA requires kernel recompilation for each input variation, wasting power and latency.

**Solution:** HLX's content-addressed storage enables perfect memoization. Same input → instant cache hit.

**Goal:** Demonstrate 3× faster warm-start latency vs CUDA on repeated inference workloads.

## Architecture

```
HLX Handle → LC-B Encoding → SPIR-V Shader → Vulkan Pipeline → GPU Compute → HLX Handle
      ↓                                                                ↓
Content-Addressed                                              Deterministic
   Storage                                                      (bit-identical)
```

## Quick Start (When Ready)

```bash
# Run benchmark (Docker)
docker-compose up benchmark

# Or run locally
pip install -r requirements.txt
python benchmarks/gemm_comparison.py
```

## Roadmap

See [docs/VULKAN_ROADMAP.md](docs/VULKAN_ROADMAP.md) for detailed 9-13 week plan.

**Target Milestones:**
- ✅ Week 0: Corpus complete, runtime verified
- 🔄 Week 1-2: Vulkan runtime foundation (CURRENT)
- ⏳ Week 3-5: GEMM benchmark (parity with CUDA)
- ⏳ Week 6-9: Warm-start optimization (beat CUDA)
- ⏳ Week 10-12: Production polish + Docker
- ⏳ Week 13: Public benchmarks + outreach

## Related Projects

- [HLX v1.1.0 Corpus](https://github.com/latentcollapse/HLXv1.1.0) - Language specification
- [HLX Studio](https://github.com/latentcollapse/hlx-studio) - Development environment

## Contributing

**Current Status:** Early experimental phase. Not accepting external contributions yet.

Once Phase 1 is complete and benchmarks are reproducible, contribution guidelines will be added.

## License

MIT OR Apache-2.0
