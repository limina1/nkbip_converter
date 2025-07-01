#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
import os
from typing import List, Dict, Any

# Import the modules from your existing codebase
try:
    from modules.key_utils import read_encrypted_key
    from modules.event_creator import create_event, decrypt_key
    from modules.event_verifier import verify_event
    from modules.event_publisher import publish_event
    from modules.event_utils import print_event_summary
    from modules.event_encoder import encode_event_id
except ImportError:
    print("Error: Required modules not found.")
    print(
        "Make sure modules/key_utils.py, modules/event_creator.py, etc. are available."
    )
    sys.exit(1)


def fetch_events_by_kind(
    kind: int, relay: str, limit: int = 0, since: int = 0
) -> List[Dict[str, Any]]:
    """Fetch events of a specific kind from a relay.

    Args:
        kind: Event kind to fetch
        relay: Relay URL to fetch from
        limit: Maximum number of events to fetch (0 for all)
        since: Unix timestamp, fetch events newer than this

    Returns:
        List of event dictionaries
    """
    try:
        cmd = ["nak", "req", "-k", str(kind)]
        if limit > 0:
            cmd.extend(["-l", str(limit)])
        if since > 0:
            cmd.extend(["-s", str(since)])
        cmd.append(relay)

        process = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if process.returncode != 0:
            raise Exception(f"Failed to fetch events: {process.stderr}")

        # Parse JSON output
        events = []
        output_lines = process.stdout.strip().split("\n")

        for line in output_lines:
            if not line or line.startswith("connecting") or line.startswith("ok."):
                continue

            try:
                event = json.loads(line)
                events.append(event)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON: {line}")

        return events
    except Exception as e:
        print(f"Error fetching events: {e}")
        sys.exit(1)


def get_pubkey(key: str) -> str:
    """Get public key from private key."""
    try:
        process = subprocess.run(
            ["nak", "key", "public", key],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if process.returncode != 0:
            raise Exception(f"Failed to get pubkey: {process.stderr}")
        return process.stdout.strip()
    except Exception as e:
        print(f"Error getting pubkey: {e}")
        sys.exit(1)


def filter_events_by_pubkey(
    events: List[Dict[str, Any]], pubkey: str
) -> List[Dict[str, Any]]:
    """Filter events to only include those from the specified pubkey."""
    return [event for event in events if event.get("pubkey") == pubkey]


def create_deletion_request(
    event_ids: List[str], kind: int, reason: str, key: str
) -> Dict[str, Any]:
    """Create a NIP-09 deletion request for the specified events."""
    # Create tags for each event ID
    tags = [["e", event_id] for event_id in event_ids]

    # Add k tag for the kind being deleted (per NIP-09)
    tags.append(["k", str(kind)])

    # Create the event
    event = create_event(5, reason, tags, key)

    # Verify it
    if verify_event(event):
        print(f"Created deletion event: {event['id']}")
        return event
    else:
        print("Failed to verify deletion event!")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Delete all events of a specific kind from a relay"
    )
    parser.add_argument(
        "--nsec", required=True, help="Private key (ncryptsec or file path)"
    )
    parser.add_argument(
        "--relay", required=True, help="Relay URL to delete events from"
    )
    parser.add_argument("--kind", required=True, type=int, help="Event kind to delete")
    parser.add_argument(
        "--limit", type=int, default=100, help="Maximum number of events to fetch"
    )
    parser.add_argument(
        "--since", type=int, default=0, help="Delete events newer than this timestamp"
    )
    parser.add_argument("--reason", default="", help="Optional reason for deletion")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview events without deleting"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Maximum number of events to delete in a single request",
    )

    args = parser.parse_args()

    print(f"\nStarting event deletion process...")
    print(f"Target kind: {args.kind}")
    print(f"Relay: {args.relay}")

    # Read the private key

    key = read_encrypted_key(args.nsec) if "ncryptsec" in args.nsec else args.nsec
    key = decrypt_key(key)

    # Get pubkey
    pubkey = get_pubkey(key)
    print(f"Using pubkey: {pubkey}")

    # Fetch events
    print(f"\nFetching events of kind {args.kind} from {args.relay}...")
    events = fetch_events_by_kind(args.kind, args.relay, args.limit, args.since)
    print(f"Found {len(events)} events of kind {args.kind}")

    # Filter events by pubkey
    user_events = filter_events_by_pubkey(events, pubkey)
    print(f"Found {len(user_events)} events created by your pubkey")

    if len(user_events) == 0:
        print("No events to delete. Exiting.")
        sys.exit(0)

    # Sort events by created_at (newest first)
    user_events.sort(key=lambda e: e.get("created_at", 0), reverse=True)

    # In dry-run mode, just show events and exit
    if args.dry_run:
        print("\nEvents that would be deleted (dry run):")
        for i, event in enumerate(user_events, 1):
            created_at = event.get("created_at", "unknown")
            content_preview = event.get("content", "")[:50] + (
                "..." if len(event.get("content", "")) > 50 else ""
            )
            print(
                f"{i}. ID: {event['id']}, Created: {created_at}, Content: {content_preview}"
            )
        sys.exit(0)

    # Process events in batches to avoid large deletion requests
    event_ids = [event["id"] for event in user_events]
    batches = [
        event_ids[i : i + args.batch_size]
        for i in range(0, len(event_ids), args.batch_size)
    ]

    print(f"\nWill process {len(batches)} batch(es) of events")

    # Confirm deletion
    confirmation = input(
        f"\nWill delete {len(event_ids)} events of kind {args.kind}. Continue? (y/N): "
    )
    if confirmation.lower() != "y":
        print("Operation cancelled.")
        sys.exit(0)

    # Process each batch
    for i, batch in enumerate(batches, 1):
        print(f"\nProcessing batch {i}/{len(batches)} ({len(batch)} events)...")

        # Create deletion event for this batch
        deletion_event = create_deletion_request(batch, args.kind, args.reason, key)

        # Print event summary
        print("\nDeletion event details:")
        print_event_summary(deletion_event)

        # Publish event
        print(f"Publishing deletion request to {args.relay}...")
        if publish_event(deletion_event, [args.relay]):
            print(f"Successfully published deletion request for batch {i}")
        else:
            print(f"Failed to publish deletion request for batch {i}")
            if (
                len(batches) > 1
                and input("Continue with next batch? (y/N): ").lower() != "y"
            ):
                print("Operation cancelled.")
                sys.exit(1)

    print("\nEvent deletion process complete!")
    nevent = encode_event_id(deletion_event, [args.relay], note_format=True)
    print(f"Deletion event ID: {nevent}")


if __name__ == "__main__":
    main()
