#!/usr/bin/env python3
"""
Convert OER metadata to NKBIP-01 event structure
Creates hierarchical Nostr publications from OER course data
"""

import argparse
import json
import sys
import requests
from typing import Dict, List, Optional
from urllib.parse import urlparse, quote
import re

from modules.tag_utils import clean_tag
from modules.key_utils import read_encrypted_key
from modules.event_creator import create_event
from modules.event_verifier import verify_event
from modules.event_publisher import publish_event
from modules.event_utils import print_event_summary
from modules.nkbip01_tags import NKBIP01Tags


def fetch_oer_metadata(resource_id: str) -> Dict:
    """Fetch metadata from OER API"""
    # Handle both full URLs and just the resource ID
    oer_url = resource_id
    if resource_id.startswith("http"):
        # Extract resource ID from URL
        parsed = urlparse(resource_id)
        path_parts = parsed.path.split("/")
        if "resources" in path_parts:
            idx = path_parts.index("resources")
            if idx + 1 < len(path_parts):
                resource_id = path_parts[idx + 1]

    url = f"https://oersi.org/resources/{resource_id}?format=json"
    print(f"Fetching metadata from: {url}")

    response = requests.get(url)
    response.raise_for_status()
    resp = response.json()
    resp["oer"] = oer_url
    return resp


def extract_course_metadata(data: Dict) -> Dict:
    """Extract relevant metadata from OER data"""
    metadata = {
        "title": data.get("name", "Untitled Course"),
        "summary": data.get("description", ""),
        "image": data.get("image", ""),
        "source": data.get("id", ""),
        "i": data.get("oer", ""),
        "k": "web",
        "tags": [],
    }

    # Extract creator information
    creators = data.get("creator", [])
    if creators:
        # Use first person as primary author
        for creator in creators:
            if creator.get("type") == "Person":
                metadata["author"] = creator.get("name", "")
                if creator.get("honorificPrefix"):
                    metadata["author"] = (
                        f"{creator['honorificPrefix']} {metadata['author']}"
                    )
                break

        # Add organizations to published_by
        orgs = [c.get("name") for c in creators if c.get("type") == "Organization"]
        if orgs:
            metadata["published_by"] = ", ".join(orgs)

    # Extract keywords as tags
    keywords = data.get("keywords", [])
    if keywords:
        metadata["tags"] = [clean_tag(k) for k in keywords]

    metadata["tags"].append("oer")
    # License
    license_info = data.get("license", {})
    if isinstance(license_info, dict) and "id" in license_info:
        metadata["license"] = license_info["id"]

    # Language
    languages = data.get("inLanguage", [])
    if languages:
        metadata["language"] = languages[0]

    # Publication date from mainEntityOfPage
    main_entity = data.get("mainEntityOfPage", [])
    if main_entity and isinstance(main_entity, list):
        for entity in main_entity:
            if isinstance(entity, dict) and "dateCreated" in entity:
                metadata["published_on"] = entity["dateCreated"]
                break

    return metadata


def create_lecture_content_event(
    lecture_data: Dict,
    parent_title: str,
    key: str,
    metadata: Dict,
    env_pw: Optional[str] = None,
) -> Dict:
    """Create a 30041 content event for a lecture"""
    lecture_title = lecture_data.get("name", "Untitled Lecture")
    lecture_id = lecture_data.get("id", "")

    # Create placeholder content with metadata
    content_lines = [
        f"= {lecture_title}",
        "",
        f"This is a placeholder for lecture content from: {lecture_id}",
        "",
        "== Lecture Information",
        f"* Part of: {parent_title}",
        f"* Source: {lecture_id}",
    ]

    if metadata.get("author"):
        content_lines.append(f"- Instructor: {metadata['author']}")

    if metadata.get("license"):
        content_lines.append(f"- License: {metadata['license']}")

    content_lines.extend(
        [
            "",
            "== Content",
            "The actual lecture content would be extracted and placed here.\n",
            "This could include:\n",
            "* Video transcripts\n",
            "* Lecture notes\n",
            "* Slides\n",
            "* Additional resources",
        ]
    )

    content = "\n".join(content_lines)

    # Create d-tag from lecture title
    d_tag = f"{clean_tag(parent_title)}-{clean_tag(lecture_title)}"

    # Create tags for the content event
    tags = NKBIP01Tags.create_content_tags(
        title=lecture_title,
        d_tag=d_tag,
        content_type="adoc",  # Using markdown for placeholder content
        language=metadata.get("language", "en"),
    )

    # Add source URL as a tag
    tags.append(["source", lecture_id])

    # Add author if available
    if metadata.get("author"):
        tags.append(["author", metadata["author"]])

    # Create and verify event
    event = create_event(30041, content, tags, key, decrypt=True, env_pw=env_pw)
    if verify_event(event):
        print(f"Created content event for: {lecture_title}")
        return event
    else:
        print(f"Failed to verify event for: {lecture_title}")
        sys.exit(1)


def export_to_asciidoc(
    metadata: Dict, lecture_events: List[Dict], filename: str
) -> None:
    """Export course/collection to a single AsciiDoc file"""
    print(f"\nExporting to AsciiDoc file: {filename}")

    with open(filename, "w", encoding="utf-8") as f:
        # Write document title
        f.write(f"= {metadata['title']}\n")

        # Write metadata as AsciiDoc attributes
        if metadata.get("author"):
            f.write(f":author: {metadata['author']}\n")

        if metadata.get("published_on"):
            f.write(f":published_on: {metadata['published_on']}\n")

        if metadata.get("published_by"):
            f.write(f":published_by: {metadata['published_by']}\n")

        if metadata.get("source"):
            f.write(f":source: {metadata['source']}\n")

        if metadata.get("license"):
            f.write(f":license: {metadata['license']}\n")

        if metadata.get("language"):
            f.write(f":language: {metadata['language']}\n")

        if metadata.get("tags"):
            f.write(f":tags: {', '.join(metadata['tags'])}\n")

        # Add any additional metadata fields
        for key, value in metadata.items():
            if key not in [
                "title",
                "author",
                "published_on",
                "published_by",
                "source",
                "license",
                "language",
                "tags",
                "summary",
                "image",
            ]:
                f.write(f":{key}: {value}\n")

        f.write("\n")

        # Write image if present
        if metadata.get("image"):
            f.write(f"image::{metadata['image']}[{metadata['title']}]\n\n")

        # Write summary
        if metadata.get("summary"):
            f.write(f"{metadata['summary']}\n\n")

        # Write each lecture/content as a level 2 section
        for item in lecture_events:
            event = item["event"]

            # Extract title from event tags
            title = next(
                (tag[1] for tag in event["tags"] if tag[0] == "title"), item["title"]
            )

            # Write section header
            f.write(f"== {title}\n\n")

            # Extract source URL if available
            source_url = next(
                (tag[1] for tag in event["tags"] if tag[0] == "source"), None
            )
            if source_url:
                f.write(f"_Source: {source_url}_\n\n")

            # Write content
            content = event["content"]

            # Skip the markdown headers in placeholder content since we're using AsciiDoc
            lines = content.split("\n")
            skip_headers = True
            for line in lines:
                if skip_headers and (line.startswith("#") or line.strip() == ""):
                    continue
                elif line.strip().startswith("This is a placeholder"):
                    skip_headers = False
                    f.write("// " + line + "\n")
                elif line.strip() == "## Content":
                    f.write("\n// TODO: Add actual content here\n\n")
                    skip_headers = False
                else:
                    f.write(line + "\n")

            f.write("\n")

    print(f"Successfully exported {len(lecture_events)} sections to {filename}")
    print("\nYou can now:")
    print(f"1. Edit the content in {filename}")
    print(f"2. Convert it back to Nostr events using:")
    print(
        f"   python nkbip_converter.py --adoc-file {filename} --nsec <key> --relays <relays>"
    )


def sort_lectures(lectures: List[Dict], patterns: List[str] = None) -> List[Dict]:
    """Sort lectures using multiple patterns with priorities

    Args:
        lectures: List of lecture dictionaries
        patterns: List of 'priority:pattern' strings where:
                 - priority is a number (lower = higher priority)
                 - pattern is a regex with optional capture group
                 Default: ['1:Lecture (\\d+)']
    """
    # Parse patterns into (priority, regex) tuples
    pattern_rules = []
    if patterns:
        for pattern_str in patterns:
            if ":" in pattern_str:
                priority_str, pattern = pattern_str.split(":", 1)
                try:
                    priority = int(priority_str)
                except ValueError:
                    print(
                        f"Warning: Invalid priority '{priority_str}' in pattern, using 999"
                    )
                    priority = 999
            else:
                # No priority specified, treat as old-style pattern
                pattern = pattern_str
                priority = 1
            pattern_rules.append((priority, pattern))
    else:
        # Default pattern
        pattern_rules = [(1, r"Lecture (\d+)")]

    # Sort patterns by priority
    pattern_rules.sort(key=lambda x: x[0])

    def get_sort_key(lecture: Dict) -> tuple:
        name = lecture.get("name", "")

        # Try each pattern in priority order
        for priority, pattern in pattern_rules:
            match = re.search(pattern, name)
            if match:
                # Extract number from first capture group if available
                if match.groups():
                    try:
                        # Try to convert captured group to int
                        return (priority, int(match.group(1)), "")
                    except (ValueError, IndexError):
                        # Non-numeric or no capture group
                        return (priority, 0, name)
                else:
                    # Pattern matched but no capture group
                    return (priority, 0, name)

        # No pattern matched - put at end
        # Try to extract any number for sub-sorting
        number_match = re.search(r"\d+", name)
        if number_match:
            return (999, int(number_match.group(0)), name)

        return (999, 999, name)

    return sorted(lectures, key=get_sort_key)


def main():
    parser = argparse.ArgumentParser(
        description="Convert OER course metadata to NKBIP-01 Nostr events"
    )
    parser.add_argument("--nsec", required=True, help="ncryptsec key or file path")
    parser.add_argument(
        "--relays", required=True, nargs="+", help="Relay URLs to publish to"
    )
    parser.add_argument(
        "--oer-url",
        nargs="+",
        help="OER resource URL(s) or ID(s). Multiple URLs create a collection.",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Treat single OER resource as standalone (create both 30040 and 30041)",
    )
    parser.add_argument(
        "--collection-title", help="Title for collection when using multiple OER URLs"
    )
    parser.add_argument(
        "--sort-pattern",
        action="append",
        help="Regex pattern with priority for sorting. Can be used multiple times. Format: 'priority:pattern' where priority is a number (lower = higher priority). Example: '1:Lecture (\\\\d+)' '2:Exam (\\\\d+)' '3:.*Solution.*'. Items not matching any pattern go to the end.",
    )
    parser.add_argument(
        "--env-pw", help="Environment variable name containing password"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Auto-confirm all prompts"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't publish, just show what would be created",
    )
    parser.add_argument(
        "--to-adoc",
        help="Export to AsciiDoc file instead of publishing. Specify output filename.",
    )

    args = parser.parse_args()

    # Read key
    key = read_encrypted_key(args.nsec) if args.nsec.startswith("/") else args.nsec

    # Handle multiple URLs (collection mode)
    if len(args.oer_url) > 1:
        print(f"\nCollection mode: Processing {len(args.oer_url)} resources")

        # Create a collection index
        collection_title = (
            args.collection_title or f"OER Collection ({len(args.oer_url)} items)"
        )
        all_events = []
        lecture_events = []
        primary_relay = args.relays[0]

        # Process each URL as a content item
        for idx, url in enumerate(args.oer_url, 1):
            try:
                resource_data = fetch_oer_metadata(url)
                resource_meta = extract_course_metadata(resource_data)
                print(
                    f"\n[{idx}/{len(args.oer_url)}] Processing: {resource_meta['title']}"
                )

                # Create content event for this resource
                event = create_lecture_content_event(
                    {
                        "name": resource_meta["title"],
                        "id": resource_meta.get("source", url),
                    },
                    collection_title,
                    key,
                    resource_meta,
                    args.env_pw,
                )

                d_tag = next(tag[1] for tag in event["tags"] if tag[0] == "d")
                lecture_events.append(
                    {"event": event, "title": resource_meta["title"], "d_tag": d_tag}
                )
                all_events.append((f"Resource {idx}", event))

            except Exception as e:
                print(f"Error processing {url}: {e}")
                continue

        # Create collection index
        print("\nCreating collection index...")
        collection_metadata = {
            "title": collection_title,
            "summary": f"A curated collection of {len(lecture_events)} educational resources",
            "tags": ["collection", "oer"],
        }

    # Handle single URL
    else:
        # Fetch OER metadata
        try:
            course_data = fetch_oer_metadata(args.oer_url[0])
        except Exception as e:
            print(f"Error fetching OER metadata: {e}")
            sys.exit(1)

        # Extract metadata
        metadata = extract_course_metadata(course_data)
        print("\nExtracted metadata:")
        for k, v in metadata.items():
            if k != "tags" or v:  # Only show tags if not empty
                print(f"  {k}: {v}")

        # Check if this is a course with lectures or a standalone resource
        lectures = course_data.get("hasPart", [])

        if args.standalone or not lectures:
            # Standalone mode: create both 30040 and 30041 for single resource
            print("\nStandalone mode: Creating index and content for single resource")
            all_events = []
            lecture_events = []
            primary_relay = args.relays[0]

            # Create content event
            content_event = create_lecture_content_event(
                {"name": metadata["title"], "id": metadata.get("source", "")},
                metadata["title"],
                key,
                metadata,
                args.env_pw,
            )

            d_tag = next(tag[1] for tag in content_event["tags"] if tag[0] == "d")
            lecture_events.append(
                {"event": content_event, "title": metadata["title"], "d_tag": d_tag}
            )
            all_events.append(("Content", content_event))

        else:
            # Course mode: process all lectures
            print(f"\nCourse mode: Found {len(lectures)} lectures")

            # Sort lectures using patterns
            if args.sort_pattern:
                print(f"\nSorting lectures using patterns:")
                for p in args.sort_pattern:
                    print(f"  - {p}")
            lectures = sort_lectures(lectures, args.sort_pattern)

            print("\nLectures (sorted):")
            for i, lecture in enumerate(lectures, 1):
                print(f"  {i}. {lecture.get('name', 'Untitled')}")

            # Continue with normal course processing...
            all_events = []
            lecture_events = []
            primary_relay = args.relays[0]

            # Create content events for each lecture
            for lecture in lectures:
                event = create_lecture_content_event(
                    lecture, metadata["title"], key, metadata, args.env_pw
                )

                d_tag = next(tag[1] for tag in event["tags"] if tag[0] == "d")
                lecture_events.append(
                    {
                        "event": event,
                        "title": lecture.get("name", "Untitled"),
                        "d_tag": d_tag,
                    }
                )
                all_events.append(("Lecture Content", event))

    # Now create the index event based on mode
    if len(args.oer_url) > 1:
        # Use collection metadata for multiple URLs
        metadata = collection_metadata
        index_title = "Collection Index"
    elif args.standalone or not lectures:
        # Use resource metadata for standalone
        index_title = "Resource Index"
    else:
        # Use course metadata for courses with lectures
        index_title = "Course Index"

    # Create index event
    print(f"\nCreating {index_title.lower()}...")
    index_event = create_event(
        30040,
        "",
        NKBIP01Tags.create_index_tags(
            title=metadata["title"],
            d_tag=clean_tag(metadata["title"]),
            author=metadata.get("author"),
            publication_type="course" if lectures else "resource",
            language=metadata.get("language", "en"),
            metadata=metadata,
        ),
        key,
        decrypt=True,
        env_pw=args.env_pw,
    )

    # Add content references to index
    for item in lecture_events:
        ref_tag = [
            "a",
            f"30041:{index_event['pubkey']}:{item['d_tag']}",
            primary_relay,
            item["event"]["id"],
        ]
        index_event["tags"].append(ref_tag)

    # Re-sign the index with references
    index_event = create_event(
        30040, "", index_event["tags"], key, decrypt=True, env_pw=args.env_pw
    )

    if verify_event(index_event):
        print(f"{index_title} verified")
        all_events.append((index_title, index_event))
    else:
        print(f"{index_title} verification failed!")
        sys.exit(1)

    # Handle export to AsciiDoc
    if args.to_adoc:
        export_to_asciidoc(metadata, lecture_events, args.to_adoc)
        return

    # Print summary
    print("\n=== Events Summary ===")
    for event_type, event in all_events:
        print(f"\n{event_type}:")
        print_event_summary(event)

    if args.dry_run:
        print("\nDry run complete. No events published.")
        return

    # Get confirmation
    if not args.yes:
        if input("\nReady to publish these events? (y/N): ").lower() != "y":
            print("Publication cancelled.")
            sys.exit(0)

    # Publish events
    print(f"\nPublishing events to relays: {', '.join(args.relays)}")

    all_success = True
    for event_type, event in all_events:
        print(f"\nPublishing {event_type}...")
        if not publish_event(event, args.relays):
            print(f"Failed to publish {event_type} event!")
            all_success = False

    if all_success:
        print("\nAll events published successfully!")

        # Get the naddr for the index event
        from modules.event_encoder import encode_event_id

        naddr = encode_event_id(index_event, args.relays, note_format=False)
        print(f"\nPublication available at:")
        print(f"naddr: {naddr}")
    else:
        print("\nSome events failed to publish.")


if __name__ == "__main__":
    main()
