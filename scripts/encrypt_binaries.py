#!/usr/bin/env python3
"""
Binary encryption script for VPS-based streaming license system.

This script encrypts binary files using AES-256-CBC encryption.
It can encrypt single files or batch process multiple binaries.

Usage:
    # Single file encryption
    python encrypt_binaries.py input.exe output.enc
    
    # Batch encryption
    python encrypt_binaries.py --batch file1.exe file2.sys file3.exe
    
    # Batch encryption with custom output directory
    python encrypt_binaries.py --batch --output-dir ./encrypted file1.exe file2.sys

Requirements:
    - AES_ENCRYPTION_KEY environment variable must be set (64 hex characters = 32 bytes)
    - Input files must exist and be readable
"""

import sys
import os
import argparse
from pathlib import Path
from typing import List, Tuple

# Direct imports to avoid Flask app initialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding


def encrypt_binary(data: bytes, key: bytes) -> bytes:
    """
    Encrypt binary data using AES-256-CBC.
    
    Generates a random 16-byte IV for each encryption operation,
    applies PKCS7 padding to the plaintext, encrypts with AES-256-CBC,
    and prepends the IV to the ciphertext for storage.
    
    Args:
        data: Binary data to encrypt
        key: 32-byte AES encryption key
    
    Returns:
        IV (16 bytes) + encrypted data
        
    Raises:
        ValueError: If key is not 32 bytes
    """
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    
    # Generate random 16-byte IV
    iv = os.urandom(16)
    
    # Apply PKCS7 padding to plaintext
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    
    # Encrypt with AES-256-CBC
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    # Prepend IV to ciphertext
    return iv + ciphertext


def load_aes_key() -> bytes:
    """
    Load AES encryption key from environment configuration.
    
    Returns:
        32-byte AES key
        
    Raises:
        ValueError: If AES_ENCRYPTION_KEY is not set or invalid
    """
    key_hex = os.environ.get('AES_ENCRYPTION_KEY')
    
    if not key_hex:
        raise ValueError(
            "AES_ENCRYPTION_KEY environment variable is not set.\n"
            "Generate a key with: python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            "Then set it: export AES_ENCRYPTION_KEY=<generated_key>"
        )
    
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as e:
        raise ValueError(
            f"AES_ENCRYPTION_KEY must be a valid hex string (64 characters): {e}"
        )
    
    if len(key) != 32:
        raise ValueError(
            f"AES_ENCRYPTION_KEY must be 32 bytes (64 hex characters), got {len(key)} bytes"
        )
    
    return key


def encrypt_file(input_path: Path, output_path: Path, key: bytes) -> None:
    """
    Encrypt a single binary file.
    
    Args:
        input_path: Path to input binary file
        output_path: Path to output encrypted file
        key: 32-byte AES encryption key
        
    Raises:
        FileNotFoundError: If input file doesn't exist
        IOError: If file read/write fails
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")
    
    # Read input binary
    print(f"Reading {input_path}...")
    with open(input_path, 'rb') as f:
        plaintext = f.read()
    
    file_size = len(plaintext)
    print(f"  Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    
    # Encrypt
    print(f"Encrypting with AES-256-CBC...")
    encrypted_data = encrypt_binary(plaintext, key)
    
    encrypted_size = len(encrypted_data)
    print(f"  Encrypted size: {encrypted_size:,} bytes ({encrypted_size / 1024:.2f} KB)")
    print(f"  IV + ciphertext format: 16 bytes IV + {encrypted_size - 16:,} bytes ciphertext")
    
    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing to {output_path}...")
    with open(output_path, 'wb') as f:
        f.write(encrypted_data)
    
    print(f"✓ Successfully encrypted {input_path.name} -> {output_path.name}\n")


def encrypt_batch(input_files: List[Path], output_dir: Path, key: bytes) -> Tuple[int, int]:
    """
    Encrypt multiple binary files.
    
    Args:
        input_files: List of input file paths
        output_dir: Directory for encrypted output files
        key: 32-byte AES encryption key
        
    Returns:
        Tuple of (successful_count, failed_count)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    failed = 0
    
    for input_path in input_files:
        # Generate output filename: input.exe -> input.enc
        output_filename = input_path.stem + '.enc'
        output_path = output_dir / output_filename
        
        try:
            encrypt_file(input_path, output_path, key)
            successful += 1
        except Exception as e:
            print(f"✗ Failed to encrypt {input_path.name}: {e}\n")
            failed += 1
    
    return successful, failed


def main():
    """Main entry point for the encryption script."""
    parser = argparse.ArgumentParser(
        description='Encrypt binary files using AES-256-CBC',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Encrypt single file
  python encrypt_binaries.py GDRVLoader.exe loader.enc
  
  # Batch encrypt multiple files to current directory
  python encrypt_binaries.py --batch GDRVLoader.exe driver.sys Cipher.exe
  
  # Batch encrypt with custom output directory
  python encrypt_binaries.py --batch --output-dir ./binaries GDRVLoader.exe driver.sys Cipher.exe

Environment:
  AES_ENCRYPTION_KEY    32-byte key as 64 hex characters (required)
  
  Generate a key with:
    python -c "import secrets; print(secrets.token_hex(32))"
        """
    )
    
    parser.add_argument(
        'input',
        nargs='+',
        type=Path,
        help='Input binary file(s) to encrypt'
    )
    
    parser.add_argument(
        'output',
        nargs='?',
        type=Path,
        help='Output encrypted file path (required for single file mode)'
    )
    
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Batch mode: encrypt multiple files'
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('.'),
        help='Output directory for batch mode (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.batch:
        if args.output:
            parser.error("Cannot specify output file in batch mode. Use --output-dir instead.")
        input_files = args.input
        output_dir = args.output_dir
    else:
        # Single file mode
        if len(args.input) == 1 and args.output:
            # Correct usage: one input, one output
            input_files = args.input
            output_file = args.output
        elif len(args.input) == 2 and not args.output:
            # Alternative usage: two positional args (input output)
            input_files = [args.input[0]]
            output_file = args.input[1]
        else:
            parser.error("Single file mode requires exactly one input file and one output file")
    
    try:
        # Load AES key from environment
        print("Loading AES encryption key from environment...")
        key = load_aes_key()
        print("✓ AES key loaded successfully\n")
        
        if args.batch:
            # Batch encryption
            print(f"Batch encrypting {len(input_files)} file(s)...\n")
            successful, failed = encrypt_batch(input_files, output_dir, key)
            
            print("=" * 60)
            print(f"Batch encryption complete:")
            print(f"  Successful: {successful}")
            print(f"  Failed: {failed}")
            print(f"  Output directory: {output_dir.absolute()}")
            
            sys.exit(0 if failed == 0 else 1)
        else:
            # Single file encryption
            encrypt_file(input_files[0], output_file, key)
            sys.exit(0)
            
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"I/O Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
