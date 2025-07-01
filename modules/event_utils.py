from typing import List, Dict
from .event_creator import create_event, create_a_tag


def print_event_summary(event: dict) -> None:
    """Print a readable summary of an event"""
    print("\nEvent Summary:")
    print(f"  ID: {event['id']}")
    print(f"  Kind: {event['kind']}")
    print(f"  Tags:")
    for tag in event["tags"]:
        print(f"    - {tag}")
    if event.get("content"):
        print(
            f"  Content preview: {event['content'][:100]}..."
            if len(event["content"]) > 100
            else f"  Content: {event['content']}"
        )
    print("  ---")


def get_title_from_tags(tags: List[List[str]]) -> str:
    """Extract title from event tags
    Expected format: tags is a list of lists, where each inner list is [tag_name, tag_value]
    e.g., [['title', 'My Title'], ['d', 'my-tag']]
    """
    print(f"Debug: Processing tags for title: {tags}")

    # Look for title tag
    for tag in tags:
        if len(tag) >= 2 and tag[0] == "title":
            return tag[1]

    # If no title tag found, try to extract from d tag
    for tag in tags:
        if len(tag) >= 2 and tag[0] == "d":
            parts = tag[1].split("-")  # Split on hyphens
            if parts:
                # Take the last segment and clean it up
                title = " ".join(parts[-1].split("-")).title()
                return title

    return "Untitled"


def create_traceback_event(link_a_tag, parent_a_tag, primary_relay, key, decrypt=False):
    return create_event(
        30043, "", [link_a_tag, parent_a_tag, ["link-kind", "30041"]], key, decrypt
    )


def create_traceback_events_from_index(index_event, primary_relay, key, decrypt=False):
    events = []
    index_a_tag = create_a_tag(index_event, primary_relay)
    for tag in index_event["tags"]:
        if tag[0] == "a":
            events.append(
                create_traceback_event(tag, index_a_tag, primary_relay, key, decrypt)
            )
    return events
