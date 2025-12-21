# Phase 9: HLX-Vulkan Integration Architecture

**Date**: December 21, 2025
**Status**: ARCHITECTURE DESIGN
**Goal**: Connect HLX Contract System to working Vulkan GPU trainer

---

## Executive Summary

We have two working systems:

1. **HLX Contract Runtime (Python)**: Contract definitions, LC-B serialization, determinism verification
2. **HLX-Vulkan (Rust)**: Full GPU transformer training with backward pass, checkpointing

Phase 9 connects them via **LC-B instruction batches** — binary instruction sequences that the Python runtime generates and the Rust executor processes on GPU.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Python HLX Contract System                       │
│                                                                       │
│   LCBInstructionBatch.to_lcb() → binary instruction sequence         │
│                                                                       │
│   Contracts:                                                         │
│     800-806: Parser tier (encode/decode/validate LC-B)               │
│     900-902: GPU compute definitions (schemas only)                   │
│     150-199: Algorithmic primitives (Bayesian, Markov, etc.)         │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ LC-B Binary (IPC/Socket/File)
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      Rust HLX-Vulkan Executor                         │
│                                                                       │
│   lcb_executor::execute_batch(bytes) → Result<bytes, Error>          │
│                                                                       │
│   NEW GPU Contracts (903-909):                                       │
│     903: TRANSFORMER_FORWARD  - Full 4-layer forward pass            │
│     904: TRANSFORMER_BACKWARD - Full backward pass + gradients       │
│     905: ADAM_OPTIMIZER       - Adam weight updates                  │
│     906: TENSOR_GEMM          - GPU matrix multiply                  │
│     907: TENSOR_LAYERNORM     - GPU layer normalization              │
│     908: TENSOR_GELU          - GPU GELU activation                  │
│     909: TENSOR_SOFTMAX       - GPU softmax                          │
│                                                                       │
│   Working Infrastructure:                                            │
│     - VulkanContext (device, queues, memory)                         │
│     - 18 compute shaders (GEMM, attention, etc.)                     │
│     - Full backward pass (loss 5.33 → 0.54)                          │
│     - Checkpoint save/load (13MB binary format)                      │
│     - 4.8k tok/sec throughput                                        │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                           Vulkan GPU                                  │
│                                                                       │
│   NVIDIA RTX 5060 - Compute Shaders                                  │
│   SPIR-V bytecode execution, shared memory, barriers                 │
└──────────────────────────────────────────────────────────────────────┘
```

---

## New GPU Contracts (903-909)

### CONTRACT_903: TRANSFORMER_FORWARD

```rust
contract_903 {
    @name: "Transformer_Forward_Pass"
    @purpose: "Execute full transformer forward pass on GPU"

    @input: {
        "input_tokens": [u32; seq_len],     // Token IDs
        "model_handle": Handle,              // CAS handle to model weights
        "config": TransformerConfig,         // Architecture params
    }

    @output: {
        "logits": [f32; seq_len * vocab_size],
        "activations_handle": Handle,        // For backward pass
    }

    @determinism: "Same tokens + weights → identical logits (bit-exact)"
    @axioms: [A1_DETERMINISM, A4_UNIVERSAL]

    @implementation: "src/bin/train_transformer_full.rs:forward_pass()"
}
```

### CONTRACT_904: TRANSFORMER_BACKWARD

```rust
contract_904 {
    @name: "Transformer_Backward_Pass"
    @purpose: "Compute gradients through all 4 transformer layers"

    @input: {
        "logits_grad": [f32; seq_len * vocab_size],  // dL/d_logits
        "activations_handle": Handle,                 // From forward pass
        "model_handle": Handle,                       // Current weights
    }

    @output: {
        "weight_grads_handle": Handle,  // All weight gradients
        "embedding_grad": [f32; ...],   // Optional: for fine-tuning embeddings
    }

    @gradient_flow: [
        "d_logits → output_proj_backward",
        "→ final_layernorm_backward",
        "→ [layer 4→1]: FFN_W2 → GELU → FFN_W1 → LN2 → O_proj → V_proj → LN1",
        "→ embedding_backward (optional)"
    ]

    @determinism: "Same inputs → identical gradients"
    @axioms: [A1_DETERMINISM, A2_REVERSIBILITY]
}
```

### CONTRACT_905: ADAM_OPTIMIZER

```rust
contract_905 {
    @name: "Adam_Optimizer_Step"
    @purpose: "Apply Adam updates to all model weights"

    @input: {
        "model_handle": Handle,           // Current weights
        "weight_grads_handle": Handle,    // From backward pass
        "optimizer_state_handle": Handle, // m, v momentum/variance
        "learning_rate": f32,
        "beta1": f32,  // default 0.9
        "beta2": f32,  // default 0.999
        "epsilon": f32, // default 1e-8
        "step": u32,    // For bias correction
    }

    @output: {
        "updated_model_handle": Handle,
        "updated_optimizer_state_handle": Handle,
    }

    @determinism: "Same grads + state + hyperparams → identical weights"
    @axioms: [A1_DETERMINISM]
}
```

### CONTRACT_906: TENSOR_GEMM

```rust
contract_906 {
    @name: "GPU_Matrix_Multiply"
    @purpose: "Deterministic GEMM on GPU (validated bit-perfect)"

    @input: {
        "A": [f32; M * K],
        "B": [f32; K * N],
        "transpose_A": bool,
        "transpose_B": bool,
    }

    @output: {
        "C": [f32; M * N],  // C = A @ B
    }

    @validation: "CPU reference comparison, bit-exact match"
    @implementation: "shader/gemm.glsl (VALIDATED ✓)"
}
```

### CONTRACT_907-909: TENSOR_LAYERNORM, TENSOR_GELU, TENSOR_SOFTMAX

Similar structure — wrap our validated GLSL shaders as contracts.

---

## LC-B Instruction Format

### Instruction Batch Structure

```
INSTRUCTION_BATCH {
    header: {
        magic: 0x4C434231,      // "LCB1"
        version: 1,
        batch_id: [u8; 32],     // BLAKE2b hash
        instruction_count: u16,
        total_size: u32,
    },
    instructions: [
        {
            contract_id: u16,   // 903, 904, 905, etc.
            param_count: u8,
            params: [Param],    // LC-B encoded parameters
        },
        ...
    ],
    signature: [u8; 32],        // BLAKE2b of batch for verification
}
```

### Example: Training Step Batch

```python
# Python side: Build training step instruction batch
batch = LCBInstructionBatch()

# Step 1: Forward pass
batch.add_instruction(903, {
    'input_tokens': token_ids,
    'model_handle': model_handle,
    'config': transformer_config,
})

# Step 2: Compute loss (cross-entropy)
batch.add_instruction(910, {
    'logits': CHAIN_PREVIOUS,
    'targets': target_tokens,
})

# Step 3: Backward pass
batch.add_instruction(904, {
    'logits_grad': CHAIN_PREVIOUS,
    'activations_handle': CHAIN_FROM_STEP(1),
    'model_handle': model_handle,
})

# Step 4: Adam update
batch.add_instruction(905, {
    'model_handle': model_handle,
    'weight_grads_handle': CHAIN_PREVIOUS,
    'optimizer_state_handle': optimizer_handle,
    'learning_rate': 3e-4,
    'step': epoch_num,
})

# Serialize and send to Rust executor
lcb_bytes = batch.to_lcb()
result = rust_executor.execute(lcb_bytes)
```

---

## Rust Executor Implementation

### Module Structure

```
hlx-vulkan/
  src/
    lcb/
      mod.rs           # LC-B parsing and execution
      parser.rs        # Parse LC-B instruction batches
      executor.rs      # Contract dispatch
      contracts/
        mod.rs
        transformer.rs # 903-905
        tensor_ops.rs  # 906-909
```

### Core Executor

```rust
// src/lcb/executor.rs

pub struct LCBExecutor {
    vulkan_ctx: VulkanContext,
    model_cache: HashMap<Handle, ModelWeights>,
    result_cache: Vec<ContractResult>,
}

impl LCBExecutor {
    pub fn execute_batch(&mut self, batch: &[u8]) -> Result<Vec<u8>, LCBError> {
        let batch = parse_lcb_batch(batch)?;
        verify_batch_signature(&batch)?;

        let mut results = Vec::new();

        for (idx, instr) in batch.instructions.iter().enumerate() {
            let result = match instr.contract_id {
                903 => self.execute_transformer_forward(instr)?,
                904 => self.execute_transformer_backward(instr)?,
                905 => self.execute_adam_optimizer(instr)?,
                906 => self.execute_gemm(instr)?,
                907 => self.execute_layernorm(instr)?,
                908 => self.execute_gelu(instr)?,
                909 => self.execute_softmax(instr)?,
                _ => return Err(LCBError::UnknownContract(instr.contract_id)),
            };

            // Store result for chaining
            self.result_cache.push(result.clone());
            results.push(result);
        }

        // Serialize results back to LC-B
        Ok(serialize_results(&results))
    }

    fn execute_transformer_forward(&mut self, instr: &Instruction)
        -> Result<ContractResult, LCBError>
    {
        // Extract params
        let tokens = instr.get_param::<Vec<u32>>("input_tokens")?;
        let model = self.load_model(instr.get_param::<Handle>("model_handle")?)?;

        // Execute forward pass using existing train_transformer_full.rs logic
        let logits = forward_pass(&self.vulkan_ctx, &model, &tokens)?;

        Ok(ContractResult::Tensor(logits))
    }
}
```

---

## Integration Steps

### Phase 9.1: LC-B Parser in Rust (Week 1)

1. Create `src/lcb/parser.rs` — parse LC-B binary format
2. Create `src/lcb/executor.rs` — contract dispatch framework
3. Test with simple contract (CONTRACT_906: GEMM)
4. Verify determinism: same LC-B → identical GPU output

### Phase 9.2: Transformer Contracts (Week 2)

1. Wrap forward pass as CONTRACT_903
2. Wrap backward pass as CONTRACT_904
3. Wrap Adam optimizer as CONTRACT_905
4. Test full training loop via LC-B batches

### Phase 9.3: Python Integration (Week 3)

1. Create Python bindings (PyO3 or socket IPC)
2. Update `hlx_runtime/core/contracts.py` with 903-909
3. Create `LCBInstructionBatch` builder for GPU contracts
4. Test end-to-end: Python → LC-B → Rust → GPU → result

### Phase 9.4: Verification & Production (Week 4)

1. Determinism verification (1000× runs)
2. Performance benchmarks
3. Error handling and recovery
4. Documentation and examples

---

## Success Criteria

- [ ] LC-B parser correctly decodes instruction batches
- [ ] CONTRACT_903 (forward) produces identical logits for same input
- [ ] CONTRACT_904 (backward) produces identical gradients
- [ ] CONTRACT_905 (Adam) produces identical weight updates
- [ ] Full training loop via LC-B achieves same loss curve as direct Rust
- [ ] Python can build and execute LC-B batches on GPU
- [ ] 1000× determinism verification passes for all contracts
- [ ] Integration tests with real HLX corpus

---

## Why This Architecture

1. **Clean Separation**: Python handles contract definitions, Rust handles GPU execution
2. **Determinism**: LC-B binary format ensures identical instruction encoding
3. **Verification**: Both sides can independently verify results
4. **Extensibility**: New contracts just add dispatch cases
5. **Performance**: Zero-copy where possible, binary protocol minimizes overhead
6. **Existing Investment**: Leverages our working 4-layer transformer trainer

---

## Next Step

Start with LC-B parser in Rust: `src/lcb/parser.rs`

The parser needs to handle:
- LEB128 variable-length integers
- Contract ID extraction
- Parameter deserialization
- Batch verification (signature check)

Once parsing works, we can wire up the existing forward/backward pass as contracts.
