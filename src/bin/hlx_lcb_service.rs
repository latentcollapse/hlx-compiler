//! HLX LC-B Execution Service
//!
//! Unix domain socket server for executing LC-B instruction batches on GPU.
//!
//! Usage:
//!   hlx_lcb_service [OPTIONS]
//!
//! Options:
//!   --socket PATH    Socket path (default: /tmp/hlx_vulkan.sock)
//!   --quiet          Suppress output
//!   --help           Show this help

use std::sync::atomic::Ordering;

use hlx_vulkan::lcb::{LCBService, ServiceConfig, DEFAULT_SOCKET_PATH};

fn print_help() {
    println!("HLX LC-B Execution Service");
    println!();
    println!("Usage: hlx_lcb_service [OPTIONS]");
    println!();
    println!("Options:");
    println!("  --socket PATH    Socket path (default: {})", DEFAULT_SOCKET_PATH);
    println!("  --quiet          Suppress output");
    println!("  --help           Show this help");
    println!();
    println!("Examples:");
    println!("  hlx_lcb_service");
    println!("  hlx_lcb_service --socket /tmp/my_hlx.sock");
    println!("  hlx_lcb_service --quiet");
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    let mut config = ServiceConfig::default();

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--help" | "-h" => {
                print_help();
                return;
            }
            "--socket" => {
                i += 1;
                if i >= args.len() {
                    eprintln!("Error: --socket requires a path argument");
                    std::process::exit(1);
                }
                config.socket_path = args[i].clone();
            }
            "--quiet" | "-q" => {
                config.verbose = false;
            }
            arg => {
                eprintln!("Unknown argument: {}", arg);
                eprintln!("Use --help for usage information");
                std::process::exit(1);
            }
        }
        i += 1;
    }

    // Set up Ctrl+C handler
    let mut service = LCBService::new(config);
    let stop_handle = service.stop_handle();

    ctrlc::set_handler(move || {
        println!("\nShutting down...");
        stop_handle.store(false, Ordering::SeqCst);
    }).expect("Failed to set Ctrl+C handler");

    // Run service
    if let Err(e) = service.run() {
        eprintln!("Service error: {}", e);
        std::process::exit(1);
    }
}
