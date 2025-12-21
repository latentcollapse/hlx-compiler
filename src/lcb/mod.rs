//! LC-B (Latent Collapse Binary) Instruction Protocol
//!
//! This module implements the binary instruction format for deterministic
//! contract execution on Vulkan GPU.
//!
//! Reference: Phase 9 Contract System Architecture

pub mod parser;
pub mod executor;
pub mod contracts;
pub mod service;

pub use parser::{LCBBatch, Instruction, Param, parse_batch};
pub use executor::{LCBExecutor, ContractResult, LCBError};
pub use service::{LCBService, ServiceConfig, DEFAULT_SOCKET_PATH};

/// LC-B magic number: "LCB1" in little-endian
pub const LCB_MAGIC: u32 = 0x3142434C; // "LCB1"

/// Current protocol version
pub const LCB_VERSION: u8 = 1;

/// Contract ID ranges
pub mod contract_ids {
    // Parser tier (existing)
    pub const BINARY_SERIALIZER: u16 = 800;
    pub const INSTRUCTION_PARSER: u16 = 801;
    pub const TYPE_VALIDATOR: u16 = 802;
    pub const DETERMINISM_VERIFIER: u16 = 803;
    pub const CONTRACT_VALIDATOR: u16 = 805;
    pub const ERROR_HANDLER: u16 = 806;

    // GPU tier (existing Python definitions)
    pub const VULKAN_SHADER: u16 = 900;
    pub const COMPUTE_KERNEL: u16 = 901;
    pub const PIPELINE_CONFIG: u16 = 902;

    // NEW: Transformer operations (GPU-native)
    pub const TRANSFORMER_FORWARD: u16 = 903;
    pub const TRANSFORMER_BACKWARD: u16 = 904;
    pub const ADAM_OPTIMIZER: u16 = 905;

    // NEW: Tensor operations (GPU-native)
    pub const TENSOR_GEMM: u16 = 906;
    pub const TENSOR_LAYERNORM: u16 = 907;
    pub const TENSOR_GELU: u16 = 908;
    pub const TENSOR_SOFTMAX: u16 = 909;
    pub const TENSOR_CROSS_ENTROPY: u16 = 910;
}
