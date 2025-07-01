#!/usr/bin/env python3
import os
import sys
import argparse
import pathlib


def create_adoc_content(file_path):
    # Get relative path from project root by first getting absolute path
    abs_path = os.path.abspath(file_path)
    rel_path = os.path.relpath(abs_path, os.path.dirname(os.path.dirname(abs_path)))

    # Get filename and extension
    filename = os.path.basename(file_path)
    name_without_ext, ext = os.path.splitext(filename)
    ext = ext.lstrip(".")  # Remove the leading dot from extension

    # Read the Python file content
    with open(file_path, "r") as f:
        code_content = f.read()

    # Create AsciiDoc content
    content = f"""= {name_without_ext}.{ext}


== Documentation

TODO: Add documentation for this module

== Location
[source]
----
./{rel_path}
----
== Code

[source]
----
{code_content}
----
"""
    return content


def main():
    parser = argparse.ArgumentParser(
        description="Generate AsciiDoc files from a directory files."
    )
    parser.add_argument("--input-dir", required=True, help="Input directory to process")
    parser.add_argument(
        "--output-dir", required=True, help="Output directory for AsciiDoc files"
    )
    parser.add_argument(
        "--exts", nargs="*", default=["*"], help="File extensions to process"
    )
    args = parser.parse_args()

    if not os.path.exists(args.input_dir):
        os.makedirs(args.input_dir)

    # Find all Python files
    print(f"Processing files in {args.input_dir}...")
    # Convert ~/to absolute path
    print(f"Converting {args.input_dir} to absolute path...")
    abs_input_dir = os.path.abspath(os.path.expanduser(args.input_dir))
    print(f"Absolute path: {abs_input_dir}")
    print(f"List of extensions: {args.exts}")

    for root, dirs, files in os.walk(abs_input_dir):
        # Skip hidden directories (starting with .)
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for file in files:
            if not any(file.endswith(ext) if ext != "*" else True for ext in args.exts):
                print(f"Skipping file: {file}")
            else:
                print(f"Processing file: {file}")
                # Get full path to file
                file_path = os.path.join(root, file)
                # Create corresponding docs directory structure
                doc_dir = os.path.join(
                    args.output_dir, os.path.relpath(root, abs_input_dir)
                )
                if not os.path.exists(doc_dir):
                    os.makedirs(doc_dir)

                # Create .adoc file path
                name_without_ext, ext = os.path.splitext(file)
                ext = ext.lstrip(".")  # Remove the leading dot
                adoc_file = os.path.join(doc_dir, f"{name_without_ext}_{ext}.adoc")

                # Generate and write content
                content = create_adoc_content(file_path)
                with open(adoc_file, "w") as f:
                    f.write(content)

                print(f"Created: {adoc_file}")


if __name__ == "__main__":
    print("Generating AsciiDoc files...")
    main()
