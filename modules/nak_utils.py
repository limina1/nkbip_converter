import subprocess
import json
import shlex
from typing import Optional, Dict, List, Union, Any


def nak_decode(npub_or_entity: str) -> json:
    """
    Decode a Nostr NIP-19 entity (like npub) to its raw hex form using NAK.

    Args:
        npub_or_entity: A NIP-19 encoded entity (npub, nsec, note, etc.)

    Returns:
        Decoded hex string

    Raises:
        subprocess.CalledProcessError: If NAK decode fails
        ValueError: If the output format isn't as expected
    """
    try:
        # Call the NAK command-line tool, returns json
        result = subprocess.run(
            ["nak", "decode", npub_or_entity],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse the output
        output = result.stdout.strip()

        # Handle different formats based on entity type
        if npub_or_entity.startswith("npub"):
            # npub decodes to just a hex string
            return {"pubkey": output}
        elif npub_or_entity.startswith("note"):
            # note decodes to just a hex string
            return {"event_id": output}
        else:
            # Try to parse as JSON first, fall back to raw output
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return output
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise ValueError(f"Failed to decode {npub_or_entity}: {error_msg}")


def nak_encode(hex_string: str, prefix: str = "npub") -> str:
    """
    Encode a hex string to a NIP-19 entity using NAK.

    Args:
        hex_string: The hex string to encode
        prefix: The prefix to use (npub, nsec, note, etc.)

    Returns:
        Encoded NIP-19 entity

    Raises:
        subprocess.CalledProcessError: If NAK encode fails
    """
    try:
        result = subprocess.run(
            ["nak", "encode", "--prefix", prefix, hex_string],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise ValueError(f"Failed to encode {hex_string}: {error_msg}")


def nak_fetch(
    entity: str, relays: List[str] = None, timeout: int = 10, raw: bool = False
) -> Any:
    """
    Fetch events related to a NIP-19 entity using NAK.

    Args:
        entity: A NIP-19 encoded entity (npub, note, etc.)
        relays: List of relay URLs to connect to
        timeout: Maximum time to wait for responses
        raw: Whether to return raw output instead of parsed JSON

    Returns:
        Dictionary with the fetched events or raw output

    Raises:
        subprocess.CalledProcessError: If NAK fetch fails
    """
    cmd = ["nak", "fetch"]

    if relays:
        for relay in relays:
            cmd.extend(["--relay", relay])

    cmd.extend(["--timeout", str(timeout)])

    if raw:
        cmd.append("--raw")

    cmd.append(entity)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Try to parse as JSON if not raw, otherwise return stdout
        if raw:
            return result.stdout.strip()

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw_output": result.stdout.strip()}
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise ValueError(f"Failed to fetch {entity}: {error_msg}")


def nak_event(
    content: str, sec_key: str, kind: int = 1, tags: List[List[str]] = None
) -> Dict:
    """
    Create a Nostr event using NAK.

    Args:
        content: Event content
        sec_key: Secret key to use for signing
        kind: Event kind
        tags: List of tags to include

    Returns:
        Dictionary with the created event

    Raises:
        subprocess.CalledProcessError: If NAK event fails
    """
    cmd = ["nak", "event", "--sec", sec_key, "--kind", str(kind), "--content", content]

    if tags:
        for tag in tags:
            if len(tag) >= 2:  # Tags should have at least name and value
                cmd.extend(["--tags", f"{tag[0]}:{tag[1]}"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw_output": result.stdout.strip()}
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise ValueError(f"Failed to create event: {error_msg}")


def is_nak_installed() -> bool:
    """
    Check if NAK is installed and available in the PATH.

    Returns:
        True if NAK is installed, False otherwise
    """
    try:
        subprocess.run(["nak", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def nak_req(filters: Dict, relays: List[str] = None, timeout: int = 10) -> List[Dict]:
    """
    Make a REQ query to Nostr relays using NAK.

    Args:
        filters: Dictionary with filter parameters (authors, kinds, etc.)
        relays: List of relay URLs to connect to
        timeout: Maximum time to wait for responses

    Returns:
        List of events matching the filter

    Raises:
        subprocess.CalledProcessError: If NAK req fails
    """
    cmd = ["nak", "req"]

    # Add filter parameters
    if "authors" in filters:
        for author in filters["authors"]:
            cmd.extend(["--authors", author])

    if "kinds" in filters:
        for kind in filters["kinds"]:
            cmd.extend(["--kinds", str(kind)])

    if "ids" in filters:
        for id in filters["ids"]:
            cmd.extend(["--ids", id])

    if "tags" in filters:
        for tag_name, tag_values in filters["tags"].items():
            for value in tag_values:
                cmd.extend(["--tags", f"{tag_name}:{value}"])

    if "since" in filters:
        cmd.extend(["--since", str(filters["since"])])

    if "until" in filters:
        cmd.extend(["--until", str(filters["until"])])

    if "limit" in filters:
        cmd.extend(["--limit", str(filters["limit"])])

    # Add relays
    if relays:
        for relay in relays:
            cmd.extend(["--relay", relay])

    cmd.extend(["--timeout", str(timeout)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Try to parse as JSON
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return [{"raw_output": result.stdout.strip()}]
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise ValueError(f"Failed to execute req: {error_msg}")


def run_nak_command(command_args: List[str], input_data: str = None) -> str:
    """
    Run an arbitrary NAK command.

    Args:
        command_args: List of command arguments
        input_data: Optional input data to pass to the command

    Returns:
        Command output

    Raises:
        subprocess.CalledProcessError: If NAK command fails
    """
    cmd = ["nak"] + command_args

    try:
        if input_data:
            result = subprocess.run(
                cmd, input=input_data, capture_output=True, text=True, check=True
            )
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        cmd_str = " ".join(shlex.quote(arg) for arg in cmd)
        raise ValueError(f"Failed to run command '{cmd_str}': {error_msg}")
