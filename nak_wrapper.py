#!/usr/bin/env python3
"""
NAK Wrapper - Secure password handling for all nak commands
Allows you to enter your password once and then use any nak command
"""

import os
import sys
import subprocess
import getpass
import argparse
import tempfile
import atexit
from pathlib import Path


class NakWrapper:
    def __init__(self):
        self.temp_key_file = None
        self.decrypted_key = None
        
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_key_file and os.path.exists(self.temp_key_file):
            os.remove(self.temp_key_file)
            
    def read_encrypted_key(self, key_path):
        """Read and decrypt an encrypted key file"""
        with open(key_path, 'r') as f:
            encrypted_key = f.read().strip()
        
        # Get password
        password = getpass.getpass("Enter password to decrypt key: ")
        
        # Use nak to decrypt
        result = subprocess.run(
            ['nak', 'key', 'decrypt', encrypted_key, password],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Error decrypting key: {result.stderr}")
            sys.exit(1)
            
        return result.stdout.strip()
    
    def create_temp_env(self, key):
        """Create temporary environment with decrypted key"""
        # Create a temporary file for the decrypted key
        fd, self.temp_key_file = tempfile.mkstemp(prefix='nak_temp_', suffix='.tmp')
        os.close(fd)
        
        # Write the decrypted key
        with open(self.temp_key_file, 'w') as f:
            f.write(key)
        
        # Set restrictive permissions
        os.chmod(self.temp_key_file, 0o600)
        
        # Set environment variable
        os.environ['NOSTR_SECRET_KEY'] = key
        
        # Register cleanup
        atexit.register(self.cleanup)
        
    def run_interactive_shell(self):
        """Run an interactive shell with nak available"""
        print("\n=== NAK Interactive Shell ===")
        print("Your key is loaded. You can now use any nak command.")
        print("Type 'exit' or Ctrl+D to quit.\n")
        
        # Get user's preferred shell
        shell = os.environ.get('SHELL', '/bin/bash')
        
        # Create a custom prompt
        original_ps1 = os.environ.get('PS1', '$ ')
        os.environ['PS1'] = '(nak) ' + original_ps1
        
        # Run interactive shell
        subprocess.run([shell, '-i'])
        
    def run_nak_command(self, args):
        """Run a specific nak command"""
        cmd = ['nak'] + args
        result = subprocess.run(cmd)
        return result.returncode
        
    def run_command_loop(self):
        """Run commands in a loop"""
        print("\n=== NAK Command Mode ===")
        print("Your key is loaded. Enter nak commands without the 'nak' prefix.")
        print("Type 'exit' or 'quit' to stop.\n")
        
        while True:
            try:
                # Get command
                cmd_input = input("nak> ").strip()
                
                if cmd_input.lower() in ['exit', 'quit']:
                    break
                    
                if not cmd_input:
                    continue
                
                # Parse and run command
                args = cmd_input.split()
                self.run_nak_command(args)
                
            except KeyboardInterrupt:
                print("\nUse 'exit' or 'quit' to stop.")
            except EOFError:
                break
                
        print("\nGoodbye!")


def main():
    parser = argparse.ArgumentParser(
        description="NAK wrapper with secure password handling",
        epilog="Examples:\n"
               "  %(prog)s --nsec ~/.config/nostr/key.ncryptsec --shell\n"
               "  %(prog)s --nsec ~/.config/nostr/key.ncryptsec --command event -k 1 -c 'Hello'\n"
               "  %(prog)s --nsec ~/.config/nostr/key.ncryptsec",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--nsec',
        required=True,
        help='Path to encrypted nsec file or nsec/hex key'
    )
    
    parser.add_argument(
        '--shell',
        action='store_true',
        help='Launch interactive shell with key loaded'
    )
    
    parser.add_argument(
        '--command',
        nargs=argparse.REMAINDER,
        help='Run a specific nak command'
    )
    
    args = parser.parse_args()
    
    wrapper = NakWrapper()
    
    try:
        # Handle key
        if args.nsec.startswith('/') or os.path.exists(args.nsec):
            # It's a file path
            key = wrapper.read_encrypted_key(args.nsec)
        else:
            # It's a key string (nsec or hex)
            key = args.nsec
            
        # Set up environment
        wrapper.create_temp_env(key)
        
        # Run in appropriate mode
        if args.shell:
            wrapper.run_interactive_shell()
        elif args.command:
            sys.exit(wrapper.run_nak_command(args.command))
        else:
            wrapper.run_command_loop()
            
    finally:
        wrapper.cleanup()


if __name__ == "__main__":
    main()