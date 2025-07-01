import os
import getpass

def read_encrypted_key(key_path: str) -> str:
    """Read and validate the encrypted key file"""
    if not os.path.isfile(key_path):
        raise ValueError(f"Key file not found: {key_path}")
        
    with open(key_path, 'r') as f:
        return f.read().strip()