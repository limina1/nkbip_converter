#!/usr/bin/env python3

"""
embed_article.py - Create semantic vector embeddings for NIP-62 publications

This script queries a specific NIP-62 publication (kind 30040) from a relay,
extracts its section IDs, creates embedding events (kind 1987) according to
NKBIP-02, and publishes them to the specified relay.

Usage:
  ./embed_article.py --id <event_id/nevent/naddr> --relay <relay_url> --nsec <private_key> [options]
"""

import argparse
import json
import sys
import os
import subprocess
import random
import time
from typing import List, Dict, Any, Tuple, Optional
import sys

# Try to import required modules
try:
    from modules.event_creator import create_event, create_a_tag
    from modules.event_verifier import verify_event
    from modules.event_encoder import encode_event_id
    from modules.event_publisher import publish_event
    from modules.event_utils import (
        print_event_summary,
        create_traceback_events_from_index,
    )
    from modules.nak_utils import nak_decode
    from modules.key_utils import read_encrypted_key
    from modules.event_embedder import create_embedding_event
except ImportError:
    print(
        "Warning: Some modules could not be imported. Using built-in implementations."
    )


def fetch_publication(event_id: str, relay: str) -> Dict:
    """
    Fetch a publication event (kind 30040) from a relay.

    Args:
        event_id: The event ID, nevent, or naddr code
        relay: The relay URL

    Returns:
        The publication event
    """
    # Decode NIP-19 identifiers if needed
    if event_id.startswith(("nevent", "note", "naddr")):
        try:
            process = subprocess.run(
                ["nak", "decode", event_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            decoded = json.loads(process.stdout.strip())
            if "id" in decoded:
                event_id = decoded["id"]
        except subprocess.CalledProcessError as e:
            print(f"Error decoding event ID: {e.stderr}")
            sys.exit(1)

    # Fetch the event using nak
    try:
        process = subprocess.run(
            ["nak", "req", "-i", event_id, relay],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        event = json.loads(process.stdout.strip())

        # Verify it's a publication event
        if event.get("kind") != 30040:
            raise ValueError(
                f"Event {event_id} is not a publication event (kind 30040)"
            )

        return event
    except Exception as e:
        print(f"Error fetching publication: {e}")
        sys.exit(1)


def extract_section_refs(pub_event: Dict) -> List[str]:
    """
    Extract section references from a publication event's 'a' tags.

    Args:
        pub_event: The publication event

    Returns:
        List of section event IDs
    """
    section_refs = []

    for tag in pub_event.get("tags", []):
        if tag[0] == "a" and len(tag) >= 2:
            # Format: ["a", "<kind:pubkey:dtag>", "<relay>", "<event id>"]
            if len(tag) >= 4 and tag[3]:
                section_refs.append(tag[3])
            else:
                print(f"Section reference without direct event ID: {tag}")

    return section_refs


def fetch_section_events(section_ids: List[str], relay: str) -> List[Dict]:
    """
    Fetch section events by their IDs.

    Args:
        section_ids: List of section event IDs
        relay: The relay URL

    Returns:
        List of section events
    """
    section_events = []

    for section_id in section_ids:
        try:
            process = subprocess.run(
                ["nak", "req", "-i", section_id, relay],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )

            section_event = json.loads(process.stdout.strip())
            section_events.append(section_event)

        except subprocess.CalledProcessError as e:
            print(f"Failed to fetch section {section_id}: {e.stderr}")
        except Exception as e:
            print(f"Error processing section {section_id}: {e}")

    return section_events


def get_nevent_code(event: Dict, relay: str) -> str:
    """
    Generate a nevent code for an event.

    Args:
        event: The event
        relay: The relay URL

    Returns:
        The nevent code
    """
    try:
        process = subprocess.run(
            ["nak", "encode", "nevent", "--relay", relay, event["id"]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        return process.stdout.strip()
    except Exception:
        # Fallback method if nak encode fails
        return f"nevent:{event['id']}"


def main():
    parser = argparse.ArgumentParser(
        description="Create embedding events for a NIP-62 publication"
    )
    parser.add_argument(
        "--id", required=True, help="Publication event ID, nevent, or naddr"
    )
    parser.add_argument("--relay", required=True, help="Relay URL")
    parser.add_argument(
        "--nsec", required=True, help="Private key (nsec, ncryptsec, or file path)"
    )
    parser.add_argument(
        "--model", default="all-MiniLM-L6-v2", help="Embedding model name"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't publish, just create embeddings"
    )
    parser.add_argument("--mode", required=True, help="embedding or traceback")
    parser.add_argument(
        "--delay",
        type=int,
        default=10,
        help="Seconds to wait between event publications",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=10,
        help="Number of retries for failed event publications",
    )

    args = parser.parse_args()
    print("reading key")
    key = read_encrypted_key(args.nsec) if "ncryptsec" in args.nsec else args.nsec

    # Fetch the publication
    print(f"Fetching publication {args.id} from {args.relay}...")
    pub_event = fetch_publication(args.id, args.relay)
    # Get publication title
    pub_title = None
    for tag in pub_event.get("tags", []):
        if tag[0] == "title" and len(tag) > 1:
            pub_title = tag[1]
            break

    print(f"Publication: {pub_title or 'Untitled'}")

    # Extract section references
    print("Extracting section references...")
    section_ids = extract_section_refs(pub_event)
    print(f"Found {len(section_ids)} section references")

    # Fetch section events
    print("Fetching section events...")
    section_events = fetch_section_events(section_ids, args.relay)
    print(f"Fetched {len(section_events)} section events")

    events = []
    if args.mode == "traceback":
        traceback_events = []
        print(f"Creating traceback events for {len(section_events)} sections...")
        try:
            traceback_events = create_traceback_events_from_index(
                pub_event, args.relay, key, decrypt=True
            )
            events.extend(traceback_events)
        except Exception as e:
            print(f"Error creating traceback events: {e}")

    elif args.mode == "embedding":
        # Create embedding events
        print(f"Creating embedding events using model {args.model}...")
        for section in section_events:
            try:
                # Get section title
                section_title = None
                for tag in section.get("tags", []):
                    if tag[0] == "title" and len(tag) > 1:
                        section_title = tag[1]
                        break

                print(
                    f"Creating embedding for section: {section_title or section['id'][:8]+'...'}"
                )
                embedding = create_embedding_event(section, key, args.relay, args.model)
                events.append(embedding)
            except Exception as e:
                print(f"Error creating embedding: {e}")

    print(f"Created {len(events)} embedding events")

    # Publish or display embedding events
    if args.dry_run:
        print("\nDry run - not publishing events")
        for i, event in enumerate(events, 1):
            print(f"\nEmbedding {i}/{len(events)}:")
            print(f"ID: {event['id']}")
            print(
                f"References: {next((t[1] for t in event['tags'] if t[0] == 'e'), 'None')}"
            )
            print(
                f"Model: {next((t[1] for t in event['tags'] if t[0] == 'model'), 'None')}"
            )
    else:
        print(f"\nPublishing events to {args.relay}...")
        successful = 0
        nevent_codes = []

        for i, event in enumerate(events, 1):
            print(f"Publishing embedding {i}/{len(events)}...")
            success = publish_event(
                event, [args.relay], max_retries=args.retries, delay=args.delay
            )
            if success:
                successful += 1
                nevent = get_nevent_code(event, args.relay)
                nevent_codes.append((nevent, True))
            else:
                nevent_codes.append((f"Failed: {event['id']}", False))

            # Add a small delay between publications
            if i < len(events):
                time.sleep(1)

        # Print results
        print(
            f"\nEmbedding publication complete: {successful}/{len(events)} successful"
        )

        for i, (nevent, success) in enumerate(nevent_codes, 1):
            status = "✓" if success else "✗"
            print(f"{status} {i}/{len(nevent_codes)}: {nevent}")


if __name__ == "__main__":
    main()
