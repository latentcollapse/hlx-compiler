#!/bin/bash
# HLX Compiler - One-Command Installer
# Usage: ./install.sh

set -e

echo "╔══════════════════════════════════════════════════════╗"
echo "║     HLX Compiler Installation                        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check Vulkan
if ! command -v vulkaninfo &> /dev/null; then
    echo "❌ Vulkan not found. Please install Vulkan SDK:"
    echo "   Arch: sudo pacman -S vulkan-tools vulkan-validation-layers"
    echo "   Ubuntu: sudo apt install vulkan-tools vulkan-validationlayers-dev"
    exit 1
fi
echo "✅ Vulkan found"

# Check Rust
if ! command -v cargo &> /dev/null; then
    echo "❌ Rust not found. Installing..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
fi
echo "✅ Rust found ($(rustc --version))"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi
echo "✅ Python found ($(python3 --version))"

echo ""
echo "Building HLX compiler (release mode)..."
echo "This may take 2-3 minutes..."
echo ""

cargo build --release

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     Installation Complete! ✨                        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Run the benchmark:"
echo "   ./target/release/train_transformer_full"
echo ""
echo "2. Verify determinism (run 3 times):"
echo "   for i in 1 2 3; do ./target/release/train_transformer_full | grep 'Epoch 100'; done"
echo ""
echo "3. Compare to CUDA baseline:"
echo "   cat benchmarks/results/cuda_results.json | grep best_loss"
echo "   # HLX: 0.4783 vs CUDA: 0.5128 (6.7% better)"
echo ""
echo "4. Read the docs:"
echo "   cat README_AMD.md"
echo "   cat QUICKSTART.md"
echo ""
echo "Happy hacking! 🚀"
echo ""
