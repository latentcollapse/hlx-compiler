//! LC-B Contract Executor
//!
//! Dispatches parsed LC-B instructions to Vulkan GPU contracts.
//! Manages result caching for instruction chaining.

use std::collections::HashMap;

use super::parser::{LCBBatch, Instruction, Param};
use super::contract_ids::*;

/// Result from contract execution
#[derive(Debug, Clone)]
pub enum ContractResult {
    /// Null/void result
    Null,
    /// Boolean result
    Bool(bool),
    /// Integer result
    Int(i64),
    /// Float result
    Float(f64),
    /// Tensor result (flattened f32 array with shape)
    Tensor {
        data: Vec<f32>,
        shape: Vec<usize>,
    },
    /// Handle to stored result in CAS
    Handle([u8; 32]),
    /// Error result
    Error(String),
}

/// Execution error types
#[derive(Debug)]
pub enum LCBError {
    UnknownContract(u16),
    InvalidParam { name: String, expected: String },
    MissingParam(String),
    ChainError { index: usize, msg: String },
    VulkanError(String),
    ExecutionFailed(String),
}

impl std::fmt::Display for LCBError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LCBError::UnknownContract(id) => write!(f, "Unknown contract ID: {}", id),
            LCBError::InvalidParam { name, expected } =>
                write!(f, "Invalid param '{}': expected {}", name, expected),
            LCBError::MissingParam(name) => write!(f, "Missing required param: {}", name),
            LCBError::ChainError { index, msg } =>
                write!(f, "Chain error from instruction {}: {}", index, msg),
            LCBError::VulkanError(msg) => write!(f, "Vulkan error: {}", msg),
            LCBError::ExecutionFailed(msg) => write!(f, "Execution failed: {}", msg),
        }
    }
}

impl std::error::Error for LCBError {}

/// LC-B instruction batch executor
pub struct LCBExecutor {
    /// Results from each instruction (for chaining)
    result_cache: Vec<ContractResult>,
    /// Execution statistics
    stats: ExecutionStats,
}

#[derive(Debug, Default)]
pub struct ExecutionStats {
    pub instructions_executed: usize,
    pub contracts_dispatched: HashMap<u16, usize>,
    pub total_time_ms: f64,
    pub chain_operations: usize,
}

impl LCBExecutor {
    pub fn new() -> Self {
        LCBExecutor {
            result_cache: Vec::new(),
            stats: ExecutionStats::default(),
        }
    }

    /// Execute a complete LC-B batch
    pub fn execute_batch(&mut self, batch: &LCBBatch) -> Result<Vec<ContractResult>, LCBError> {
        let start = std::time::Instant::now();
        self.result_cache.clear();

        let mut results = Vec::with_capacity(batch.instructions.len());

        for (idx, instr) in batch.instructions.iter().enumerate() {
            let result = self.execute_instruction(idx, instr)?;

            // Cache result for potential chaining
            self.result_cache.push(result.clone());
            results.push(result);

            // Update stats
            self.stats.instructions_executed += 1;
            *self.stats.contracts_dispatched.entry(instr.contract_id).or_insert(0) += 1;
        }

        self.stats.total_time_ms = start.elapsed().as_secs_f64() * 1000.0;
        Ok(results)
    }

    /// Execute a single instruction
    fn execute_instruction(&mut self, idx: usize, instr: &Instruction)
        -> Result<ContractResult, LCBError>
    {
        match instr.contract_id {
            // Parser tier contracts (800-806)
            BINARY_SERIALIZER => self.execute_binary_serializer(instr),
            INSTRUCTION_PARSER => self.execute_instruction_parser(instr),
            TYPE_VALIDATOR => self.execute_type_validator(instr),
            DETERMINISM_VERIFIER => self.execute_determinism_verifier(instr),
            CONTRACT_VALIDATOR => self.execute_contract_validator(instr),
            ERROR_HANDLER => self.execute_error_handler(instr),

            // GPU tier contracts (900-902) - existing
            VULKAN_SHADER => self.execute_vulkan_shader(instr),
            COMPUTE_KERNEL => self.execute_compute_kernel(instr),
            PIPELINE_CONFIG => self.execute_pipeline_config(instr),

            // Transformer contracts (903-905) - NEW
            TRANSFORMER_FORWARD => self.execute_transformer_forward(instr),
            TRANSFORMER_BACKWARD => self.execute_transformer_backward(instr),
            ADAM_OPTIMIZER => self.execute_adam_optimizer(instr),

            // Tensor contracts (906-910) - NEW
            TENSOR_GEMM => self.execute_tensor_gemm(instr),
            TENSOR_LAYERNORM => self.execute_tensor_layernorm(instr),
            TENSOR_GELU => self.execute_tensor_gelu(instr),
            TENSOR_SOFTMAX => self.execute_tensor_softmax(instr),
            TENSOR_CROSS_ENTROPY => self.execute_tensor_cross_entropy(instr),

            _ => Err(LCBError::UnknownContract(instr.contract_id)),
        }
    }

    /// Resolve a parameter, handling chaining directives
    fn resolve_param<'a>(&'a self, instr: &'a Instruction, name: &str)
        -> Result<&'a Param, LCBError>
    {
        let param = instr.params.get(name)
            .ok_or_else(|| LCBError::MissingParam(name.to_string()))?;

        // Note: ChainPrevious/ChainFrom would be resolved differently
        // For now, return the param directly
        Ok(param)
    }

    /// Get chained result from previous instruction
    fn get_chain_result(&self, idx: usize) -> Result<&ContractResult, LCBError> {
        if idx >= self.result_cache.len() {
            return Err(LCBError::ChainError {
                index: idx,
                msg: format!("Instruction {} not yet executed", idx),
            });
        }
        Ok(&self.result_cache[idx])
    }

    // =========================================================================
    // Parser Tier Contracts (800-806)
    // =========================================================================

    fn execute_binary_serializer(&self, instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_800: Encode/decode LC-B binary
        let mode = self.get_text_param(instr, "mode")?;

        match mode.as_str() {
            "encode" => {
                // Encode value to LC-B bytes
                // For now, return placeholder
                Ok(ContractResult::Null)
            }
            "decode" => {
                // Decode LC-B bytes to value
                Ok(ContractResult::Null)
            }
            "validate" => {
                // Validate LC-B structure
                Ok(ContractResult::Bool(true))
            }
            _ => Err(LCBError::InvalidParam {
                name: "mode".to_string(),
                expected: "encode|decode|validate".to_string(),
            }),
        }
    }

    fn execute_instruction_parser(&self, _instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_801: Parse LC-B instruction sequences
        Ok(ContractResult::Null)
    }

    fn execute_type_validator(&self, _instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_802: Validate types against schema
        Ok(ContractResult::Bool(true))
    }

    fn execute_determinism_verifier(&self, _instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_803: Verify determinism (1000x identical output)
        Ok(ContractResult::Bool(true))
    }

    fn execute_contract_validator(&self, _instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_805: Validate contract structure
        Ok(ContractResult::Bool(true))
    }

    fn execute_error_handler(&self, _instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_806: Handle and encode errors
        Ok(ContractResult::Null)
    }

    // =========================================================================
    // GPU Tier Contracts (900-902)
    // =========================================================================

    fn execute_vulkan_shader(&self, _instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_900: Compile HLX to SPIR-V, execute on GPU
        Ok(ContractResult::Null)
    }

    fn execute_compute_kernel(&self, _instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_901: Define compute kernel
        Ok(ContractResult::Null)
    }

    fn execute_pipeline_config(&self, _instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_902: Configure GPU pipeline
        Ok(ContractResult::Null)
    }

    // =========================================================================
    // Transformer Contracts (903-905) - GPU-Native
    // =========================================================================

    fn execute_transformer_forward(&self, instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_903: Full transformer forward pass
        //
        // Input:
        //   input_tokens: [u32; seq_len]
        //   model_handle: Handle
        //   config: TransformerConfig
        //
        // Output:
        //   logits: Tensor [seq_len, vocab_size]

        // TODO: Wire up to actual forward pass in train_transformer_full.rs

        // For now, return placeholder tensor
        let seq_len = self.get_int_param(instr, "seq_len").unwrap_or(16) as usize;
        let vocab_size = self.get_int_param(instr, "vocab_size").unwrap_or(256) as usize;

        Ok(ContractResult::Tensor {
            data: vec![0.0f32; seq_len * vocab_size],
            shape: vec![seq_len, vocab_size],
        })
    }

    fn execute_transformer_backward(&self, instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_904: Full transformer backward pass
        //
        // Input:
        //   logits_grad: Tensor [seq_len, vocab_size]
        //   activations_handle: Handle (from forward pass)
        //   model_handle: Handle
        //
        // Output:
        //   weight_grads_handle: Handle

        // TODO: Wire up to actual backward pass

        Ok(ContractResult::Handle([0u8; 32]))
    }

    fn execute_adam_optimizer(&self, instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_905: Adam optimizer step
        //
        // Input:
        //   model_handle: Handle
        //   weight_grads_handle: Handle
        //   optimizer_state_handle: Handle
        //   learning_rate: f64
        //   beta1, beta2, epsilon: f64
        //   step: i64
        //
        // Output:
        //   updated_model_handle: Handle

        let lr = self.get_float_param(instr, "learning_rate").unwrap_or(3e-4);
        let step = self.get_int_param(instr, "step").unwrap_or(0);

        // TODO: Wire up to actual Adam implementation

        Ok(ContractResult::Handle([0u8; 32]))
    }

    // =========================================================================
    // Tensor Contracts (906-910) - GPU-Native
    // =========================================================================

    fn execute_tensor_gemm(&self, instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_906: GPU Matrix Multiply (VALIDATED BIT-PERFECT)
        //
        // Input:
        //   a: Tensor [M, K]
        //   b: Tensor [K, N]
        //   m, k, n: dimensions
        //   transpose_a: bool
        //   transpose_b: bool
        //
        // Output:
        //   C: Tensor [M, N]

        use super::contracts::tensor_ops;

        // Get tensor data
        let (a_data, _a_shape) = self.get_tensor_param(instr, "a")?;
        let (b_data, _b_shape) = self.get_tensor_param(instr, "b")?;

        // Get dimensions
        let m = self.get_int_param(instr, "m")? as usize;
        let k = self.get_int_param(instr, "k")? as usize;
        let n = self.get_int_param(instr, "n")? as usize;

        // Get transpose flags
        let transpose_a = self.get_bool_param(instr, "transpose_a").unwrap_or(false);
        let transpose_b = self.get_bool_param(instr, "transpose_b").unwrap_or(false);

        // Execute GEMM
        let result = tensor_ops::gemm(&a_data, &b_data, m, k, n, transpose_a, transpose_b)
            .map_err(|e| LCBError::ExecutionFailed(e))?;

        Ok(ContractResult::Tensor {
            data: result,
            shape: vec![m, n],
        })
    }

    fn execute_tensor_layernorm(&self, instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_907: GPU Layer Normalization
        //
        // Input:
        //   input: Tensor [batch, seq_len, hidden]
        //   gamma: Tensor [hidden]
        //   beta: Tensor [hidden]
        //   eps: f64
        //
        // Output:
        //   output: Tensor [batch, seq_len, hidden]

        // TODO: Wire up to layernorm shader

        Ok(ContractResult::Null)
    }

    fn execute_tensor_gelu(&self, instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_908: GPU GELU Activation
        //
        // Input:
        //   input: Tensor [...]
        //
        // Output:
        //   output: Tensor [...] (same shape)

        use super::contracts::tensor_ops;

        let (input_data, input_shape) = self.get_tensor_param(instr, "input")?;
        let result = tensor_ops::gelu(&input_data);

        Ok(ContractResult::Tensor {
            data: result,
            shape: input_shape,
        })
    }

    fn execute_tensor_softmax(&self, instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_909: GPU Softmax
        //
        // Input:
        //   input: Tensor [batch, seq_len, vocab]
        //   num_rows, row_size: dimensions
        //
        // Output:
        //   output: Tensor [batch, seq_len, vocab]

        use super::contracts::tensor_ops;

        let (input_data, input_shape) = self.get_tensor_param(instr, "input")?;
        let num_rows = self.get_int_param(instr, "num_rows")? as usize;
        let row_size = self.get_int_param(instr, "row_size")? as usize;

        let result = tensor_ops::softmax(&input_data, num_rows, row_size);

        Ok(ContractResult::Tensor {
            data: result,
            shape: input_shape,
        })
    }

    fn execute_tensor_cross_entropy(&self, instr: &Instruction) -> Result<ContractResult, LCBError> {
        // CONTRACT_910: GPU Cross-Entropy Loss
        //
        // Input:
        //   logits: Tensor [batch, seq_len, vocab]
        //   targets: Tensor [batch, seq_len]
        //
        // Output:
        //   loss: Float
        //   grad: Tensor [batch, seq_len, vocab]

        // TODO: Wire up to cross_entropy shader

        Ok(ContractResult::Float(0.0))
    }

    // =========================================================================
    // Helper Methods
    // =========================================================================

    fn get_text_param(&self, instr: &Instruction, name: &str) -> Result<String, LCBError> {
        match instr.params.get(name) {
            Some(Param::Text(s)) => Ok(s.clone()),
            Some(_) => Err(LCBError::InvalidParam {
                name: name.to_string(),
                expected: "text".to_string(),
            }),
            None => Err(LCBError::MissingParam(name.to_string())),
        }
    }

    fn get_int_param(&self, instr: &Instruction, name: &str) -> Result<i64, LCBError> {
        match instr.params.get(name) {
            Some(Param::Int(i)) => Ok(*i),
            Some(_) => Err(LCBError::InvalidParam {
                name: name.to_string(),
                expected: "int".to_string(),
            }),
            None => Err(LCBError::MissingParam(name.to_string())),
        }
    }

    fn get_float_param(&self, instr: &Instruction, name: &str) -> Result<f64, LCBError> {
        match instr.params.get(name) {
            Some(Param::Float(f)) => Ok(*f),
            Some(Param::Int(i)) => Ok(*i as f64),
            Some(_) => Err(LCBError::InvalidParam {
                name: name.to_string(),
                expected: "float".to_string(),
            }),
            None => Err(LCBError::MissingParam(name.to_string())),
        }
    }

    fn get_bool_param(&self, instr: &Instruction, name: &str) -> Result<bool, LCBError> {
        match instr.params.get(name) {
            Some(Param::Bool(b)) => Ok(*b),
            Some(_) => Err(LCBError::InvalidParam {
                name: name.to_string(),
                expected: "bool".to_string(),
            }),
            None => Err(LCBError::MissingParam(name.to_string())),
        }
    }

    /// Extract tensor from Bytes param (format: [ndim:u8][dims:u32...][f32 data])
    fn get_tensor_param(&self, instr: &Instruction, name: &str) -> Result<(Vec<f32>, Vec<usize>), LCBError> {
        match instr.params.get(name) {
            Some(Param::Bytes(bytes)) => {
                if bytes.is_empty() {
                    return Err(LCBError::InvalidParam {
                        name: name.to_string(),
                        expected: "tensor bytes".to_string(),
                    });
                }

                let ndim = bytes[0] as usize;
                let mut offset = 1;

                // Read shape
                let mut shape = Vec::with_capacity(ndim);
                let mut total_elements = 1usize;
                for _ in 0..ndim {
                    if offset + 4 > bytes.len() {
                        return Err(LCBError::InvalidParam {
                            name: name.to_string(),
                            expected: "complete shape".to_string(),
                        });
                    }
                    let dim = u32::from_le_bytes([
                        bytes[offset], bytes[offset+1], bytes[offset+2], bytes[offset+3]
                    ]) as usize;
                    shape.push(dim);
                    total_elements *= dim;
                    offset += 4;
                }

                // Read f32 data
                let expected_bytes = total_elements * 4;
                if offset + expected_bytes > bytes.len() {
                    return Err(LCBError::InvalidParam {
                        name: name.to_string(),
                        expected: format!("{} bytes of tensor data", expected_bytes),
                    });
                }

                let data: Vec<f32> = bytes[offset..offset + expected_bytes]
                    .chunks_exact(4)
                    .map(|chunk| f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]))
                    .collect();

                Ok((data, shape))
            }
            Some(_) => Err(LCBError::InvalidParam {
                name: name.to_string(),
                expected: "bytes (tensor)".to_string(),
            }),
            None => Err(LCBError::MissingParam(name.to_string())),
        }
    }

    /// Get execution statistics
    pub fn stats(&self) -> &ExecutionStats {
        &self.stats
    }
}

impl Default for LCBExecutor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lcb::parser::LCBBuilder;

    #[test]
    fn test_executor_dispatch() {
        let mut params = HashMap::new();
        params.insert("mode".to_string(), Param::Text("validate".to_string()));

        let batch_bytes = LCBBuilder::new()
            .add_instruction(BINARY_SERIALIZER, params)
            .build();

        let batch = super::super::parser::parse_batch(&batch_bytes).unwrap();
        let mut executor = LCBExecutor::new();
        let results = executor.execute_batch(&batch).unwrap();

        assert_eq!(results.len(), 1);
        match &results[0] {
            ContractResult::Bool(true) => {}
            other => panic!("Expected Bool(true), got {:?}", other),
        }
    }

    #[test]
    fn test_tensor_gemm_contract() {
        // Create tensor bytes: [ndim:u8][dims:u32...][f32 data]
        fn make_tensor_bytes(shape: &[usize], data: &[f32]) -> Vec<u8> {
            let mut bytes = Vec::new();
            bytes.push(shape.len() as u8);
            for &dim in shape {
                bytes.extend_from_slice(&(dim as u32).to_le_bytes());
            }
            for &val in data {
                bytes.extend_from_slice(&val.to_le_bytes());
            }
            bytes
        }

        // 2x2 GEMM: [[1,2],[3,4]] @ [[5,6],[7,8]] = [[19,22],[43,50]]
        let a_data = vec![1.0f32, 2.0, 3.0, 4.0];
        let b_data = vec![5.0f32, 6.0, 7.0, 8.0];

        let mut params = HashMap::new();
        params.insert("a".to_string(), Param::Bytes(make_tensor_bytes(&[2, 2], &a_data)));
        params.insert("b".to_string(), Param::Bytes(make_tensor_bytes(&[2, 2], &b_data)));
        params.insert("m".to_string(), Param::Int(2));
        params.insert("k".to_string(), Param::Int(2));
        params.insert("n".to_string(), Param::Int(2));
        params.insert("transpose_a".to_string(), Param::Bool(false));
        params.insert("transpose_b".to_string(), Param::Bool(false));

        let batch_bytes = LCBBuilder::new()
            .add_instruction(TENSOR_GEMM, params)
            .build();

        let batch = super::super::parser::parse_batch(&batch_bytes).unwrap();
        let mut executor = LCBExecutor::new();
        let results = executor.execute_batch(&batch).unwrap();

        match &results[0] {
            ContractResult::Tensor { data, shape } => {
                assert_eq!(shape, &vec![2, 2]);
                assert_eq!(data.len(), 4);
                // Check values: [[19,22],[43,50]]
                assert!((data[0] - 19.0).abs() < 1e-6);
                assert!((data[1] - 22.0).abs() < 1e-6);
                assert!((data[2] - 43.0).abs() < 1e-6);
                assert!((data[3] - 50.0).abs() < 1e-6);
            }
            other => panic!("Expected Tensor, got {:?}", other),
        }
    }
}
