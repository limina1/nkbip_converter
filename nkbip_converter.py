#!/usr/bin/env python3
import sys
import argparse
import json
import os
import re
from typing import Dict, List, Optional, Tuple
import metadata_parser
from modules.adoc_parser import parse_adoc_file
from modules.tag_utils import (
    clean_tag,
    create_section_tags,
    create_index_tags,
    add_reference_to_index,
    fetch_doi_metadata,
    create_external_tags,
    extract_wiki_links,
)
from modules.key_utils import read_encrypted_key
from modules.event_creator import create_event
from modules.event_verifier import verify_event
from modules.event_encoder import encode_event_id
from modules.event_publisher import publish_event
from modules.event_utils import print_event_summary, get_title_from_tags
from modules.nak_utils import nak_decode
import warnings
from pprint import pprint


def extract_metadata(file_path: str) -> Dict[str, str]:
    """
    Extract metadata from the section between title and first section.
    Returns a dictionary with metadata keys and values following NKBIP-01 spec.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract document title
    title_match = re.search(r"^=\s+(.+?)$", content, re.MULTILINE)
    if not title_match:
        print("Error: No document title found")
        return {}

    title = title_match.group(1).strip()

    # Find the position of the title and the first section heading
    title_pos = title_match.start()
    first_section_match = re.search(r"^==\s+.+?$", content, re.MULTILINE)
    first_section_pos = (
        first_section_match.start() if first_section_match else len(content)
    )

    # Extract the metadata section
    metadata_section = content[title_match.end() : first_section_pos].strip()

    # Initialize metadata dictionary with title
    metadata = {"title": title}

    # Extract image if it exists (usually right after title)
    image_match = re.search(r"image::([^\[]+)", metadata_section)
    if image_match:
        metadata["image"] = image_match.group(1).strip()

    # Extract author information - support multiple authors
    authors = []
    author_match = re.search(r"^:author:\s+(.+?)$", metadata_section, re.MULTILINE)
    if author_match:
        # Check if it's a comma-separated list
        author_str = author_match.group(1).strip()
        if "," in author_str:
            authors = [a.strip() for a in author_str.split(",")]
        else:
            authors = [author_str]
    
    # Also check for authors (plural)
    authors_match = re.search(r"^:authors:\s+(.+?)$", metadata_section, re.MULTILINE)
    if authors_match:
        author_str = authors_match.group(1).strip()
        authors.extend([a.strip() for a in author_str.split(",")])
    
    if authors:
        metadata["author"] = authors[0]  # Primary author
        if len(authors) > 1:
            metadata["additional_authors"] = authors[1:]

    # Extract summary - usually a paragraph before the first section
    # Look for a paragraph that's not attribute definition
    summary_lines = []
    for line in metadata_section.split("\n"):
        line = line.strip()
        if line and not line.startswith(":") and not line.startswith("image::"):
            summary_lines.append(line)

    if summary_lines:
        metadata["summary"] = " ".join(summary_lines)

    # Extract all AsciiDoc attributes and map to NKBIP-01 tags
    attribute_mapping = {
        "published_on": ["published_on", "publication_date", "date", "publishedon"],
        "published_by": ["published_by", "publisher", "publishedby"],
        "source": ["source", "url", "original_url"],
        "doi": ["doi"],
        "isbn": ["isbn"],
        "issn": ["issn"],
        "version": ["version", "edition"],
        "language": ["language", "lang"],
        "type": ["type", "publication_type", "pubtype"],
        "license": ["license"],
        "subject": ["subject"],
        "description": ["description", "abstract"],
        "copyright": ["copyright"],
        "translator": ["translator"],
        "editor": ["editor"],
        "illustrator": ["illustrator"]
    }
    
    # Process all attributes
    for match in re.finditer(r"^:([^:]+):\s+(.+?)$", metadata_section, re.MULTILINE):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        
        # Map to standard tag names
        mapped = False
        for standard_key, aliases in attribute_mapping.items():
            if key in aliases:
                metadata[standard_key] = value
                mapped = True
                break
        
        # If not mapped, still include it
        if not mapped and key not in ["author", "authors", "tags", "keywords"]:
            metadata[key] = value

    # Extract tags (could be specified in different ways)
    tags = []
    tags_match = re.search(r"^:tags:\s+(.+?)$", metadata_section, re.MULTILINE)
    if tags_match:
        tags = [tag.strip() for tag in tags_match.group(1).split(",")]

    # Some documents use keywords instead of tags
    keywords_match = re.search(r"^:keywords:\s+(.+?)$", metadata_section, re.MULTILINE)
    if keywords_match:
        tags.extend([tag.strip() for tag in keywords_match.group(1).split(",")])
    
    # Some use categories
    categories_match = re.search(r"^:categories:\s+(.+?)$", metadata_section, re.MULTILINE)
    if categories_match:
        tags.extend([tag.strip() for tag in categories_match.group(1).split(",")])

    if tags:
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                unique_tags.append(tag)
        metadata["tags"] = unique_tags

    return metadata


def extract_title_image(file_path: str) -> str:
    """Extract the title image from an AsciiDoc file."""
    metadata = extract_metadata(file_path)
    return metadata.get("image", "")


def extract_images(content: str) -> List[str]:
    """Extract all images from the content."""
    images = []
    for line in content.split("\n"):
        if line.startswith("image::"):
            image = line.split("::")[1].strip()
            image = image.split("[")[0].strip()
            images.append(image)

    return images


def create_asciidoc_file(
    title: str, tags: List[List[str]], sections: List[str]
) -> str:
    """Create an AsciiDoc file with the given title, tags, and sections."""
    # Clean filename - remove special characters
    filename = re.sub(r'[^\w\s-]', '', title)
    filename = re.sub(r'[-\s]+', '-', filename)
    filename = filename.strip('-')[:100]  # Limit length
    
    with open(f"{filename}.adoc", "w", encoding="utf-8") as f:
        f.write(f"= {title}\n")
        
        # Write metadata as AsciiDoc attributes
        # Skip certain tags that are handled differently
        skip_tags = ["a", "d", "auto-update", "m", "M", "l", "reading-direction"]
        
        for tag in tags:
            if len(tag) >= 2 and tag[0] not in skip_tags:
                # Convert tag name to AsciiDoc attribute format
                attr_name = tag[0].replace("-", "_")
                
                # Handle special cases
                if tag[0] == "i":
                    # Extract identifier type and value
                    if ":" in tag[1]:
                        id_type, id_value = tag[1].split(":", 1)
                        f.write(f":{id_type}: {id_value}\n")
                elif tag[0] == "t":
                    # Collect all t tags into a single tags attribute
                    continue  # Handle after loop
                else:
                    f.write(f":{attr_name}: {tag[1]}\n")
        
        # Collect all topic tags
        topic_tags = [tag[1] for tag in tags if tag[0] == "t"]
        if topic_tags:
            f.write(f":tags: {', '.join(topic_tags)}\n")
        
        f.write(":external: True\n")
        f.write("\n")
        
        if len(sections) > 0:
            for section in sections:
                f.write(f"== {section}\n\n")
        else:
            f.write("== Content\n\n")
            f.write("This document was extracted from external content.\n")
    
    print(f"Created {filename}.adoc with sections: {', '.join(sections)}")
    return f"{filename}.adoc"


def organize_sections(doc_title: str, sections: List[Dict]) -> List[Dict]:
    """Organize sections into L1 groups with their L2 sections.
    Uses document title as root section if no L1 sections exist.
    """
    # If no L1 sections, create virtual root section from document title
    has_l1_sections = any(s["level"] == 1 for s in sections)
    if not has_l1_sections:
        return [
            {
                "title": doc_title,
                "content": "",  # No content before first L2
                "is_root": True,
                "l2_sections": _group_l2_sections(sections),
            }
        ]

    # Normal processing for documents with L1 sections
    organized = []
    current_l1 = None
    current_l2 = None
    first_l1 = True

    for section in sections:
        if section["level"] == 1:
            if current_l1:
                if current_l2:
                    current_l1["l2_sections"].append(current_l2)
                organized.append(current_l1)

            current_l1 = {
                "title": section["title"],
                "content": section["content"],
                "is_root": first_l1,
                "l2_sections": [],
            }
            current_l2 = None
            first_l1 = False

        elif section["level"] == 2 and current_l1:
            if current_l2:
                current_l1["l2_sections"].append(current_l2)

            current_l2 = {"title": section["title"], "content": section["content"]}

        elif section["level"] > 2 and current_l2:
            heading = "=" * section["level"] + " " + section["title"]
            current_l2["content"] += f"\n\n{heading}\n{section['content']}"

    if current_l1:
        if current_l2:
            current_l1["l2_sections"].append(current_l2)
        organized.append(current_l1)

    return organized


def _group_l2_sections(sections: List[Dict]) -> List[Dict]:
    """Group level 2 sections and their subsections"""
    l2_sections = []
    current_section = None

    for section in sections:
        if section["level"] == 2:
            if current_section:
                l2_sections.append(current_section)
            current_section = {"title": section["title"], "content": section["content"]}
        elif section["level"] > 2 and current_section:
            heading = "=" * section["level"] + " " + section["title"]
            current_section["content"] += f"\n\n{heading}\n{section['content']}"

    if current_section:
        l2_sections.append(current_section)

    return l2_sections


def create_content_event(
    content: str,
    title: str,
    parent_title: str,
    key: str,
    author: Optional[str] = None,
    decrypt=True,
    env_pw=None,
) -> Dict:
    """Create a 30041 event for a section"""
    tags = create_section_tags(parent_title, title, namespace=True)
    images = extract_images(content)

    if images:
        for image in images:
            tags.append(["image", image])

    # Extract wiki links and create 'w' tags
    wiki_links = extract_wiki_links(content)
    for wiki_term in wiki_links:
        tags.append(["w", wiki_term])

    tags.append(["m", "text/asciidoc"])
    if author:
        tags.append(["author", author])

    event = create_event(30041, content, tags, key, decrypt=decrypt, env_pw=env_pw)
    if verify_event(event):
        print(f"Event verified: {event['id']}")
        return event
    else:
        print("Event verification failed!")
        sys.exit(1)


def create_index_event(
    title: str,
    section_events: List[Dict],
    key: str,
    primary_relay: str,
    metadata: Optional[Dict] = None,
    author: Optional[str] = None,
    author_pubkey: Optional[str] = None,
    decrypt=True,
    env_pw=None,
) -> Dict:
    """Create a 30040 event linking to section events with metadata"""
    # Build complete metadata dict for NKBIP-01
    index_metadata = {}
    
    if metadata:
        # Standard NKBIP-01 fields
        if "image" in metadata:
            index_metadata["image"] = metadata["image"]
        if "summary" in metadata:
            index_metadata["summary"] = metadata["summary"]
        if "published_on" in metadata:
            index_metadata["published_on"] = metadata["published_on"]
        elif "published" in metadata:
            index_metadata["published_on"] = metadata["published"]
        if "published_by" in metadata:
            index_metadata["published_by"] = metadata["published_by"]
        elif "publisher" in metadata:
            index_metadata["published_by"] = metadata["publisher"]
        if "source" in metadata:
            index_metadata["source"] = metadata["source"]
        if "doi" in metadata:
            index_metadata["doi"] = metadata["doi"]
        if "isbn" in metadata:
            index_metadata["isbn"] = metadata["isbn"]
        if "issn" in metadata:
            index_metadata["issn"] = metadata["issn"]
        if "tags" in metadata:
            index_metadata["tags"] = metadata["tags"]
        if "additional_authors" in metadata:
            index_metadata["additional_authors"] = metadata["additional_authors"]
        
        # Add version if present
        if "version" in metadata:
            version = metadata["version"]
        else:
            version = "1"
    else:
        version = "1"
    
    # Determine publication type
    pub_type = metadata.get("type", "book") if metadata else "book"
    
    # Use the NKBIP-01 compliant tag creation
    from modules.nkbip01_tags import NKBIP01Tags
    
    # Get language from metadata or default to English
    language = "en"
    if metadata and "language" in metadata:
        # Extract ISO 639-1 code if full language name is provided
        lang_value = metadata["language"].lower()
        if lang_value in ["english", "en"]:
            language = "en"
        elif lang_value in ["spanish", "es", "español"]:
            language = "es"
        elif lang_value in ["french", "fr", "français"]:
            language = "fr"
        else:
            language = lang_value[:2]  # Take first 2 chars as fallback
    
    # Create NKBIP-01 compliant tags
    index_tags = NKBIP01Tags.create_index_tags(
        title=title,
        d_tag=clean_tag(title),
        author=author or (metadata.get("author") if metadata else None),
        publication_type=pub_type,
        auto_update="yes",
        language=language,
        version=version,
        external=False,
        metadata=index_metadata
    )
    
    # Add author pubkey if provided
    if author_pubkey:
        # Find position after auto-update tag
        for i, tag in enumerate(index_tags):
            if tag[0] == "auto-update":
                index_tags.insert(i + 1, ["p", author_pubkey])
                break

    # Add section references
    for section in section_events:
        index_tags = add_reference_to_index(
            index_tags, section["event"], section["d_tag"], primary_relay
        )

    event = create_event(30040, "", index_tags, key, decrypt=decrypt, env_pw=env_pw)
    if verify_event(event):
        print(f"Event verified: {event['id']}")
        return event
    else:
        print("Index event verification failed!")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Convert AsciiDoc to NIP-62 Nostr events"
    )
    parser.add_argument("--nsec", required=True, help="ncryptsec key or file path")
    parser.add_argument(
        "--relays", required=True, nargs="+", help="Relay URLs to publish to"
    )
    parser.add_argument("--adoc-file", help="AsciiDoc file to convert")
    parser.add_argument("--author", help="Author name to include in tags")
    parser.add_argument("--author-pubkey", help="Author public key to include in tags")
    parser.add_argument("--external-url", help="Extract metadata from url", type=str)
    parser.add_argument(
        "--create-file", action="store_true", help="creates adoc file from url"
    )
    parser.add_argument(
        "--sections", nargs="+", type=str, help="list of sections to add"
    )
    parser.add_argument("--doi", type=str, help="Extract metadata from DOI")
    parser.add_argument(
        "--file-only", action="store_true", help="Only extract metadata from file"
    )
    parser.add_argument(
        "--env-pw", help="Environment variable name containing password for key decryption"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Auto-confirm all prompts"
    )

    args = parser.parse_args()

    key = read_encrypted_key(args.nsec) if args.nsec.startswith("/") else args.nsec
    if args.adoc_file:
        adoc_file = args.adoc_file

    if args.external_url or args.doi:
        print(f"Extracting metadata from {args.external_url or args.doi}")
        if args.sections:
            sections = args.sections
        else:
            sections = ["Main"]
    if args.doi:
        tags = fetch_doi_metadata(args.doi)
        for tag in tags:
            if tag[0] == "title":
                title = tag[1]
                break
        if tags:
            adoc_file = create_asciidoc_file(
                title,
                tags,
                sections,
            )

    if args.external_url:
        page = metadata_parser.MetadataParser(args.external_url, search_head_only=True)
        # extract open graph metadata
        open_graph = page.metadata["og"]
        print(open_graph)
        event_data = create_external_tags(open_graph, debug=True)
        for tag in event_data:
            if tag[0] == "title":
                title = tag[1]
                break
        if args.create_file:
            adoc_file = create_asciidoc_file(
                args.external_url,
                title,
                event_data,
                sections,
            )
        # publishthe event from metadata

    elif args.adoc_file:
        print("\nStarting conversion process...")
        print(f"Input file: {args.adoc_file}")
        print(f"Relays: {args.relays}")
    if args.author:
        print(f"Author: {args.author}")
    if args.file_only:
        sys.exit(0)

    # Extract metadata from the document
    metadata = extract_metadata(adoc_file)
    print("\nExtracted metadata:")

    for k, v in metadata.items():
        print(f"  {k}: {v}")

    # Parse the AsciiDoc file
    doc = parse_adoc_file(adoc_file)

    # Use metadata author if not provided in command line
    if not args.author and "author" in metadata:
        args.author = metadata["author"]
        print(f"Using author from document: {args.author}")

    # Organize sections using document title as root if needed
    organized = organize_sections(doc["title"], doc["sections"])
    if not organized:
        print("Error: No sections found in document")
        sys.exit(1)

    # Track all events for summary and publishing
    all_events = []
    primary_relay = args.relays[0]
    root_references = []  # Track everything to link in root 30040

    for l1_section in organized:
        section_events = []

        # Handle L2 sections under this L1
        for l2_section in l1_section["l2_sections"]:
            event = create_content_event(
                l2_section["content"],
                l2_section["title"],
                l1_section["title"],
                key,
                args.author,
                env_pw=args.env_pw,
            )

            section_events.append(
                {
                    "event": event,
                    "title": l2_section["title"],
                    "d_tag": next(tag[1] for tag in event["tags"] if tag[0] == "d"),
                }
            )
            all_events.append(("Content", event))

        # Create 30040 index for this L1 section only if it's not the root
        if not l1_section["is_root"] and section_events:
            # Each L1 section gets its own index, but without the full metadata
            l1_index = create_index_event(
                l1_section["title"],
                section_events,
                key,
                primary_relay,
                author=args.author,
                author_pubkey=args.author_pubkey,
                env_pw=args.env_pw,
            )
            all_events.append(("Index", l1_index))
            root_references.append(
                {
                    "event": l1_index,
                    "title": l1_section["title"],
                    "d_tag": next(tag[1] for tag in l1_index["tags"] if tag[0] == "d"),
                }
            )
        elif l1_section["is_root"]:
            # For root section, add its L2 sections directly to root references
            root_references.extend(section_events)

    # Create root index event linking everything with full metadata
    root_title = next(s["title"] for s in organized if s["is_root"])
    print("\nCreating root index event...")

    # Process author pubkey if provided
    if args.author_pubkey and "npub" in args.author_pubkey:
        warnings.warn("Author pubkey in npub format. Converting to pubkey...")
        args.author_pubkey = nak_decode(args.author_pubkey)["pubkey"]
    # Create the root index with full metadata
    root_index = create_index_event(
        root_title,
        root_references,
        key,
        primary_relay,
        metadata=metadata,
        author=args.author,
        author_pubkey=args.author_pubkey,
        env_pw=args.env_pw,
    )
    all_events.append(("Root Index", root_index))

    # Print summary of all events
    print("\n=== Events Summary ===")
    for event_type, event in all_events:
        print(f"\n{event_type}:")
        print_event_summary(event)

    # Get user confirmation unless auto-confirm is set
    if not args.yes:
        if input("\nReady to publish these events? (y/N): ").lower() != "y":
            print("Publication cancelled.")
            sys.exit(0)
    else:
        print("\nAuto-confirming publication...")

    # Publish events in order: content -> indexes -> root
    print(f"\nPublishing events to relays: {', '.join(args.relays)}")

    all_success = True
    for event_type, event in all_events:
        print(f"\nPublishing {event_type}...")
        if not publish_event(event, args.relays):
            print(f"Failed to publish {event_type} event!")
            all_success = False

    if all_success:
        print("\nAll events published successfully!")

        # Get nevent format (specific event)
        nevent = encode_event_id(root_index, args.relays, note_format=True)
        print(f"\nPublication references:")
        print(f"nevent: {nevent}")

        # Get naddr format (replaceable event)
        naddr = encode_event_id(root_index, args.relays, note_format=False)
        print(f"naddr:  {naddr}")
    else:
        print("\nSome events failed to publish.")


if __name__ == "__main__":
    main()
