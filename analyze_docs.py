#!/usr/bin/env python3
import sys
import argparse
from typing import List, Tuple, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import os


def parse_section_path(path: str) -> List[str]:
    """Convert a section path like 'Code/Functions/Helper' into list of section names"""
    return [p.strip() for p in path.split("/") if p.strip()]


def get_heading_level(line: str) -> Tuple[int, str]:
    """Get the level of an AsciiDoc heading and the heading text"""
    if line.startswith("="):
        level = len(line) - len(line.lstrip("="))
        text = line.lstrip("= ").strip()
        return level, text
    return 0, ""


def find_section_index(lines: List[str], section_name: str) -> int:
    """Find the index of a section heading in the file"""
    for i, line in enumerate(lines):
        level, heading = get_heading_level(line)
        if (
            level == 2 and heading.strip() == section_name
        ):  # Specifically look for level 2 (==) headings
            return i
    return -1


def extract_section_content(file_content: str, section_name: str) -> Optional[str]:
    """Extract content from a specific section in the AsciiDoc file"""
    lines = file_content.split("\n")
    start_idx = find_section_index(lines, section_name)

    if start_idx == -1:
        print(f"Debug: Available sections:")
        for line in lines:
            level, heading = get_heading_level(line)
            if level > 0:
                print(f"Level {level}: {heading}")
        return None

    content = []
    # Start capturing from the line after the heading
    for i in range(start_idx + 1, len(lines)):
        level, _ = get_heading_level(lines[i])
        # Stop if we hit another level 2 or higher heading
        if level > 0 and level <= 2:
            break
        content.append(lines[i])

    return "\n".join(content).strip()


def analyze_code(content: str, header_name: str) -> str:
    """Use Langchain with Claude to analyze the code content"""
    model = ChatAnthropic(
        model_name="claude-3-sonnet-20240229",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=1024,
        timeout=None,
        max_retries=3,
    )

    template = """You are analyzing code to generate documentation.
    Please analyze the following code section of a project and provide a clear, concise documentation. It may include as needed:
    1. Overview of what the code does
    2. Arguments and inputs
    3. Usage examples
    4. Key functions and their purposes
    5. Implementation details
    6. Any notable patterns or algorithms used
    7. Imports and project related files
    8. Dependencies and requirements

    DOCUMENTATION PRINCIPLES:
    - Document ONLY what is explicitly present in the provided code
    - Focus exclusively on observable functionality and implementation
    - Make NO assumptions about external modules not defined in the code
    - Avoid speculative language like "likely part of" or "probably connects to"
    - If an import is used but not defined in the provided code, simply document the import name without speculation about its implementation
    - When referencing imported modules, state only their observed usage without assumptions about their internal workings

    Format your response in proper AsciiDoc format. Make the documentation technical but clear, concise, and accessible.
    The user will start with the header to insert at, followed by the code. Do not include the header in your response, and only use level three headings (===) or lower.
    The purpose is to provide concise, semantically closed information about this specific code section.

    Code to analyze:
    {content}
    """
    prompt = ChatPromptTemplate.from_template(template)
    user_input = f"== {header_name}\n{content}"
    chain = {"content": RunnablePassthrough()} | prompt | model | StrOutputParser()
    return chain.invoke({"content": content})


def update_documentation_section(file_content: str, analysis: str, header: str) -> str:
    """Update the Documentation section with the analysis"""
    lines = file_content.split("\n")

    # Find Documentation section
    doc_index = find_section_index(lines, header)
    if doc_index == -1:
        raise ValueError("Documentation section not found in file")

    # Find the next section after Documentation to know where to stop
    next_section_index = len(lines)
    for i in range(doc_index + 1, len(lines)):
        level, _ = get_heading_level(lines[i])
        if level > 0 and level <= 2:  # Same or higher level heading
            next_section_index = i
            break

    # Replace everything between Documentation heading and next section
    new_lines = lines[: doc_index + 1]  # Keep the Documentation heading
    new_lines.extend(
        ["", analysis.strip(), ""]
    )  # Add analysis with surrounding blank lines
    new_lines.extend(lines[next_section_index:])  # Add the rest of the file

    return "\n".join(new_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze code section and update documentation in AsciiDoc files"
    )
    parser.add_argument("file", help="Path to the AsciiDoc file")
    parser.add_argument("--anthropic-key", help="Anthropic API key")
    parser.add_argument("--header", help="Header name to insert the documentation at")
    parser.add_argument("--from-section", help="Section path to extract code from")

    args = parser.parse_args()

    # Set API key
    if args.anthropic_key:
        os.environ["ANTHROPIC_API_KEY"] = args.anthropic_key
    elif "ANTHROPIC_API_KEY" not in os.environ:
        print(
            "Error: Anthropic API key not provided. Use --anthropic-key or set ANTHROPIC_API_KEY environment variable"
        )
        sys.exit(1)

    try:
        # Read the file
        with open(args.file, "r") as f:
            content = f.read()

        # Extract code section content
        print(f"Looking {args.from_section or 'Code'} section in {args.file}...")
        code_content = extract_section_content(content, args.from_section or "Code")

        if not code_content:
            print(f"Error: Code section not found in the file")
            sys.exit(1)

        print(f"Found code section with {len(code_content.split('\n'))} lines")

        # Generate analysis of the code
        print("Analyzing code...")
        analysis = analyze_code(code_content, args.header or "Code")
        # print("Analysis:\n")
        # print(analysis)

        # Update the documentation section
        print("Updating documentation...")
        updated_content = update_documentation_section(
            content, analysis, args.header or "Documentation"
        )

        # Write back to the file
        with open(args.file, "w") as f:
            f.write(updated_content)
        print("================New File====================")
        print(updated_content)

        print(f"\nSuccessfully updated documentation in {args.file}")

    except FileNotFoundError:
        print(f"Error: File '{args.file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
