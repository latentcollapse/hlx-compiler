//! LC-B Binary Parser
//!
//! Parses LC-B instruction batches into structured data for contract execution.
//! Implements LEB128 variable-length integer encoding for compact representation.

use std::io::{Cursor, Read};
use std::collections::HashMap;

use super::{LCB_MAGIC, LCB_VERSION};

/// Parsed LC-B instruction batch
#[derive(Debug, Clone)]
pub struct LCBBatch {
    pub version: u8,
    pub batch_id: [u8; 32],
    pub instructions: Vec<Instruction>,
    pub signature: [u8; 32],
}

/// Single instruction within a batch
#[derive(Debug, Clone)]
pub struct Instruction {
    pub contract_id: u16,
    pub params: HashMap<String, Param>,
    pub chain_from: Option<usize>,  // Index of instruction to chain result from
}

/// Parameter value types
#[derive(Debug, Clone)]
pub enum Param {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Text(String),
    Bytes(Vec<u8>),
    Array(Vec<Param>),
    Object(HashMap<String, Param>),
    Handle([u8; 32]),  // CAS handle reference
    ChainPrevious,     // Use result from previous instruction
    ChainFrom(usize),  // Use result from specific instruction index
}

/// Parse error types
#[derive(Debug)]
pub enum ParseError {
    InvalidMagic(u32),
    UnsupportedVersion(u8),
    UnexpectedEOF,
    InvalidUtf8,
    InvalidSignature,
    MalformedInstruction(String),
}

impl std::fmt::Display for ParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ParseError::InvalidMagic(m) => write!(f, "Invalid magic: 0x{:08X}", m),
            ParseError::UnsupportedVersion(v) => write!(f, "Unsupported version: {}", v),
            ParseError::UnexpectedEOF => write!(f, "Unexpected end of input"),
            ParseError::InvalidUtf8 => write!(f, "Invalid UTF-8 string"),
            ParseError::InvalidSignature => write!(f, "Signature verification failed"),
            ParseError::MalformedInstruction(msg) => write!(f, "Malformed instruction: {}", msg),
        }
    }
}

impl std::error::Error for ParseError {}

/// Parse a complete LC-B instruction batch
pub fn parse_batch(data: &[u8]) -> Result<LCBBatch, ParseError> {
    let mut cursor = Cursor::new(data);

    // Parse header
    let magic = read_u32_le(&mut cursor)?;
    if magic != LCB_MAGIC {
        return Err(ParseError::InvalidMagic(magic));
    }

    let version = read_u8(&mut cursor)?;
    if version != LCB_VERSION {
        return Err(ParseError::UnsupportedVersion(version));
    }

    let mut batch_id = [0u8; 32];
    cursor.read_exact(&mut batch_id).map_err(|_| ParseError::UnexpectedEOF)?;

    let instruction_count = read_leb128_u32(&mut cursor)? as usize;

    // Parse instructions
    let mut instructions = Vec::with_capacity(instruction_count);
    for _ in 0..instruction_count {
        let instr = parse_instruction(&mut cursor)?;
        instructions.push(instr);
    }

    // Parse signature
    let mut signature = [0u8; 32];
    cursor.read_exact(&mut signature).map_err(|_| ParseError::UnexpectedEOF)?;

    // Verify signature (SHA256 of everything before signature)
    let data_len = data.len() - 32;
    let computed_sig = sha256_hash(&data[..data_len]);
    if computed_sig != signature {
        return Err(ParseError::InvalidSignature);
    }

    Ok(LCBBatch {
        version,
        batch_id,
        instructions,
        signature,
    })
}

/// Parse a single instruction
fn parse_instruction(cursor: &mut Cursor<&[u8]>) -> Result<Instruction, ParseError> {
    let contract_id = read_leb128_u32(cursor)? as u16;
    let param_count = read_leb128_u32(cursor)? as usize;

    let mut params = HashMap::new();
    let mut chain_from = None;

    for _ in 0..param_count {
        // Read param name (length-prefixed string)
        let name_len = read_leb128_u32(cursor)? as usize;
        let name = read_string(cursor, name_len)?;

        // Read param value
        let value = parse_param(cursor)?;

        // Check for chaining directives
        match &value {
            Param::ChainPrevious => {
                // Mark this instruction to receive previous result
            }
            Param::ChainFrom(idx) => {
                chain_from = Some(*idx);
            }
            _ => {}
        }

        params.insert(name, value);
    }

    Ok(Instruction {
        contract_id,
        params,
        chain_from,
    })
}

/// Parse a single parameter value
fn parse_param(cursor: &mut Cursor<&[u8]>) -> Result<Param, ParseError> {
    let type_tag = read_u8(cursor)?;

    match type_tag {
        0 => Ok(Param::Null),
        1 => Ok(Param::Bool(read_u8(cursor)? != 0)),
        2 => Ok(Param::Int(read_leb128_i64(cursor)?)),
        3 => Ok(Param::Float(read_f64_le(cursor)?)),
        4 => {
            // Text: length-prefixed UTF-8 string
            let len = read_leb128_u32(cursor)? as usize;
            let text = read_string(cursor, len)?;
            Ok(Param::Text(text))
        }
        5 => {
            // Bytes: length-prefixed raw bytes
            let len = read_leb128_u32(cursor)? as usize;
            let mut bytes = vec![0u8; len];
            cursor.read_exact(&mut bytes).map_err(|_| ParseError::UnexpectedEOF)?;
            Ok(Param::Bytes(bytes))
        }
        6 => {
            // Array
            let len = read_leb128_u32(cursor)? as usize;
            let mut arr = Vec::with_capacity(len);
            for _ in 0..len {
                arr.push(parse_param(cursor)?);
            }
            Ok(Param::Array(arr))
        }
        7 => {
            // Object
            let len = read_leb128_u32(cursor)? as usize;
            let mut obj = HashMap::new();
            for _ in 0..len {
                let key_len = read_leb128_u32(cursor)? as usize;
                let key = read_string(cursor, key_len)?;
                let value = parse_param(cursor)?;
                obj.insert(key, value);
            }
            Ok(Param::Object(obj))
        }
        8 => {
            // Handle (32-byte CAS reference)
            let mut handle = [0u8; 32];
            cursor.read_exact(&mut handle).map_err(|_| ParseError::UnexpectedEOF)?;
            Ok(Param::Handle(handle))
        }
        9 => Ok(Param::ChainPrevious),
        10 => {
            let idx = read_leb128_u32(cursor)? as usize;
            Ok(Param::ChainFrom(idx))
        }
        _ => Err(ParseError::MalformedInstruction(format!("Unknown type tag: {}", type_tag))),
    }
}

// Helper functions for reading binary data

fn read_u8(cursor: &mut Cursor<&[u8]>) -> Result<u8, ParseError> {
    let mut buf = [0u8; 1];
    cursor.read_exact(&mut buf).map_err(|_| ParseError::UnexpectedEOF)?;
    Ok(buf[0])
}

fn read_u32_le(cursor: &mut Cursor<&[u8]>) -> Result<u32, ParseError> {
    let mut buf = [0u8; 4];
    cursor.read_exact(&mut buf).map_err(|_| ParseError::UnexpectedEOF)?;
    Ok(u32::from_le_bytes(buf))
}

fn read_f64_le(cursor: &mut Cursor<&[u8]>) -> Result<f64, ParseError> {
    let mut buf = [0u8; 8];
    cursor.read_exact(&mut buf).map_err(|_| ParseError::UnexpectedEOF)?;
    Ok(f64::from_le_bytes(buf))
}

fn read_string(cursor: &mut Cursor<&[u8]>, len: usize) -> Result<String, ParseError> {
    let mut buf = vec![0u8; len];
    cursor.read_exact(&mut buf).map_err(|_| ParseError::UnexpectedEOF)?;
    String::from_utf8(buf).map_err(|_| ParseError::InvalidUtf8)
}

/// Read unsigned LEB128 encoded integer
fn read_leb128_u32(cursor: &mut Cursor<&[u8]>) -> Result<u32, ParseError> {
    let mut result = 0u32;
    let mut shift = 0;

    loop {
        let byte = read_u8(cursor)?;
        result |= ((byte & 0x7F) as u32) << shift;

        if byte & 0x80 == 0 {
            break;
        }

        shift += 7;
        if shift >= 35 {
            return Err(ParseError::MalformedInstruction("LEB128 overflow".to_string()));
        }
    }

    Ok(result)
}

/// Read signed LEB128 encoded integer
fn read_leb128_i64(cursor: &mut Cursor<&[u8]>) -> Result<i64, ParseError> {
    let mut result = 0i64;
    let mut shift = 0;
    let mut byte;

    loop {
        byte = read_u8(cursor)?;
        result |= ((byte & 0x7F) as i64) << shift;
        shift += 7;

        if byte & 0x80 == 0 {
            break;
        }

        if shift >= 70 {
            return Err(ParseError::MalformedInstruction("LEB128 overflow".to_string()));
        }
    }

    // Sign extend if negative
    if shift < 64 && (byte & 0x40) != 0 {
        result |= !0i64 << shift;
    }

    Ok(result)
}

/// Compute SHA256 hash (cross-platform compatible with Python)
fn sha256_hash(data: &[u8]) -> [u8; 32] {
    use sha2::{Sha256, Digest};

    let mut hasher = Sha256::new();
    hasher.update(data);
    let result = hasher.finalize();

    let mut output = [0u8; 32];
    output.copy_from_slice(&result);
    output
}

// Builder functions for creating LC-B batches (for testing)

/// Build an LC-B batch from instructions
pub struct LCBBuilder {
    instructions: Vec<Instruction>,
}

impl LCBBuilder {
    pub fn new() -> Self {
        LCBBuilder {
            instructions: Vec::new(),
        }
    }

    pub fn add_instruction(mut self, contract_id: u16, params: HashMap<String, Param>) -> Self {
        self.instructions.push(Instruction {
            contract_id,
            params,
            chain_from: None,
        });
        self
    }

    pub fn build(self) -> Vec<u8> {
        let mut data = Vec::new();

        // Header
        data.extend_from_slice(&LCB_MAGIC.to_le_bytes());
        data.push(LCB_VERSION);

        // Batch ID (generate deterministically from instructions)
        let batch_id = sha256_hash(&self.instructions.len().to_le_bytes());
        data.extend_from_slice(&batch_id);

        // Instruction count
        write_leb128_u32(&mut data, self.instructions.len() as u32);

        // Instructions
        for instr in &self.instructions {
            write_instruction(&mut data, instr);
        }

        // Compute and append signature
        let signature = sha256_hash(&data);
        data.extend_from_slice(&signature);

        data
    }
}

fn write_leb128_u32(data: &mut Vec<u8>, mut value: u32) {
    loop {
        let mut byte = (value & 0x7F) as u8;
        value >>= 7;
        if value != 0 {
            byte |= 0x80;
        }
        data.push(byte);
        if value == 0 {
            break;
        }
    }
}

fn write_instruction(data: &mut Vec<u8>, instr: &Instruction) {
    write_leb128_u32(data, instr.contract_id as u32);
    write_leb128_u32(data, instr.params.len() as u32);

    for (name, value) in &instr.params {
        // Write param name
        write_leb128_u32(data, name.len() as u32);
        data.extend_from_slice(name.as_bytes());

        // Write param value
        write_param(data, value);
    }
}

fn write_param(data: &mut Vec<u8>, param: &Param) {
    match param {
        Param::Null => data.push(0),
        Param::Bool(b) => {
            data.push(1);
            data.push(if *b { 1 } else { 0 });
        }
        Param::Int(i) => {
            data.push(2);
            write_leb128_i64(data, *i);
        }
        Param::Float(f) => {
            data.push(3);
            data.extend_from_slice(&f.to_le_bytes());
        }
        Param::Text(s) => {
            data.push(4);
            write_leb128_u32(data, s.len() as u32);
            data.extend_from_slice(s.as_bytes());
        }
        Param::Bytes(b) => {
            data.push(5);
            write_leb128_u32(data, b.len() as u32);
            data.extend_from_slice(b);
        }
        Param::Array(arr) => {
            data.push(6);
            write_leb128_u32(data, arr.len() as u32);
            for item in arr {
                write_param(data, item);
            }
        }
        Param::Object(obj) => {
            data.push(7);
            write_leb128_u32(data, obj.len() as u32);
            for (key, value) in obj {
                write_leb128_u32(data, key.len() as u32);
                data.extend_from_slice(key.as_bytes());
                write_param(data, value);
            }
        }
        Param::Handle(h) => {
            data.push(8);
            data.extend_from_slice(h);
        }
        Param::ChainPrevious => data.push(9),
        Param::ChainFrom(idx) => {
            data.push(10);
            write_leb128_u32(data, *idx as u32);
        }
    }
}

fn write_leb128_i64(data: &mut Vec<u8>, mut value: i64) {
    let negative = value < 0;
    loop {
        let mut byte = (value & 0x7F) as u8;
        value >>= 7;

        let more = if negative {
            value != -1 || (byte & 0x40) == 0
        } else {
            value != 0 || (byte & 0x40) != 0
        };

        if more {
            byte |= 0x80;
        }
        data.push(byte);
        if !more {
            break;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_leb128_roundtrip() {
        let values = [0u32, 1, 127, 128, 16383, 16384, u32::MAX];
        for val in values {
            let mut data = Vec::new();
            write_leb128_u32(&mut data, val);

            let mut cursor = Cursor::new(data.as_slice());
            let decoded = read_leb128_u32(&mut cursor).unwrap();
            assert_eq!(val, decoded);
        }
    }

    #[test]
    fn test_batch_roundtrip() {
        let mut params = HashMap::new();
        params.insert("count".to_string(), Param::Int(42));
        params.insert("name".to_string(), Param::Text("test".to_string()));

        let batch_bytes = LCBBuilder::new()
            .add_instruction(906, params)
            .build();

        let batch = parse_batch(&batch_bytes).unwrap();
        assert_eq!(batch.instructions.len(), 1);
        assert_eq!(batch.instructions[0].contract_id, 906);
    }
}
