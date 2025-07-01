from typing import List, Dict, Tuple


def parse_adoc_section(lines: List[str], start: int) -> Tuple[dict, int]:
    """Parse a section from the AsciiDoc content"""
    content = []
    current_line = start
    section_level = 0
    title = ""

    # Get section level and title
    if lines[start].startswith("="):
        heading = lines[start].strip()
        section_level = len(heading.split(" ")[0])
        title = heading.split(" ", 1)[1].strip() if " " in heading else ""
        current_line += 1

    # Collect content until next section or end
    while current_line < len(lines):
        line = lines[current_line]
        # Check if we've hit the next section
        if line.startswith("="):
            break
        content.append(line)
        current_line += 1

    return {
        "title": title,
        "level": section_level,
        "content": "\n".join(content).strip(),
    }, current_line


def parse_adoc_file(file_path: str, debug=False) -> dict:
    """Parse AsciiDoc file and return structured content"""
    if debug:
        print(f"\nDebug: Opening file {file_path}")
    with open(file_path, "r") as f:
        lines = f.readlines()

    if debug:
        print(f"Debug: File loaded, {len(lines)} lines")

    # Skip header metadata (lines starting with :)
    start_line = 0
    while start_line < len(lines) and lines[start_line].startswith(":"):
        if debug:
            print(f"Debug: Skipping metadata line: {lines[start_line].strip()}")
        start_line += 1

    sections = []
    current_line = start_line

    # Get document title from first level 1 heading
    title = ""
    for line in lines:
        if line.startswith("= "):
            title = line[2:].strip()
            if debug:
                print(f"Debug: Found document title: {title}")
            break

    if debug:
        print("\nDebug: Processing sections...")
    while current_line < len(lines):
        line = lines[current_line]
        if line.startswith("="):
            level = len(line.split(" ")[0])  # Count the = signs
            # Only process level 2 and deeper sections as content
            if level >= 2:
                if debug:
                    print(f"Debug: Found heading: {line.strip()}")
                section, current_line = parse_adoc_section(lines, current_line)
                if debug:
                    print(
                        f"Debug: Adding section: {section['title']} (level {section['level']})"
                    )
                    print(f"Debug: Content length: {len(section['content'])} chars")
                sections.append(section)
            else:
                current_line += 1
        else:
            current_line += 1

    result = {"title": title, "sections": sections}

    print(f"\nParsing complete")
    print(f"Title: {result['title']}")
    print(f"Number of sections: {len(result['sections'])}")

    return result
