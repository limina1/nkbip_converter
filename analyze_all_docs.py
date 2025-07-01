#!/usr/bin/env python3

import sys
import os
import argparse
import subprocess
from typing import List

def find_adoc_files(folder_path: str) -> List[str]:
    """Find all .adoc files in the given directory and its subdirectories"""
    adoc_files = []
    
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.adoc'):
                full_path = os.path.join(root, file)
                adoc_files.append(full_path)
    
    return sorted(adoc_files)  # Sort for consistent ordering

def analyze_file(file_path: str, header: str) -> bool:
    """Run analyze_docs.py on a single file"""
    print(f"\nAnalyzing: {file_path}")
    
    cmd = [
        './analyze_docs.py',
        file_path,
        '--header', header
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error analyzing {file_path}:")
        print(e.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description='Run analyze_docs.py on all .adoc files')
    parser.add_argument('--docs-dir', required=True, help='Directory containing .adoc files')
    parser.add_argument('--header', default='Documentation', help='Header section to analyze (default: Documentation)')
    parser.add_argument('--anthropic-key', help='Anthropic API key')
    parser.add_argument('--skip-existing', action='store_true', help='Skip files that already have documentation')
    
    args = parser.parse_args()
    
    # Handle API key
    if args.anthropic_key:
        os.environ["ANTHROPIC_API_KEY"] = args.anthropic_key
    elif "ANTHROPIC_API_KEY" not in os.environ:
        print(
            "Error: Anthropic API key not provided. Use --anthropic-key or set ANTHROPIC_API_KEY environment variable"
        )
        sys.exit(1)
    
    # Find all .adoc files
    print(f"Scanning {args.docs_dir} for .adoc files...")
    adoc_files = find_adoc_files(args.docs_dir)
    print(f"Found {len(adoc_files)} .adoc files")
    
    # Process each file
    success_count = 0
    failure_count = 0
    skipped_count = 0
    
    for file_path in adoc_files:
        if args.skip_existing:
            # Quick check for existing documentation
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    if f"== {args.header}" in content and "TODO" not in content:
                        print(f"\nSkipping {file_path} - already has documentation")
                        skipped_count += 1
                        continue
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                failure_count += 1
                continue
        
        if analyze_file(file_path, args.header):
            success_count += 1
        else:
            failure_count += 1
    
    # Print summary
    print("\n=== Analysis Summary ===")
    print(f"Total files found: {len(adoc_files)}")
    print(f"Successfully analyzed: {success_count}")
    print(f"Failed to analyze: {failure_count}")
    if args.skip_existing:
        print(f"Skipped (existing docs): {skipped_count}")
    
    if failure_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()