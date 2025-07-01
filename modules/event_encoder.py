import subprocess
from typing import List, Dict


def encode_event_id(event: Dict, relays: List[str], note_format: bool = False) -> str:
    """Encode an event ID to naddr/nevent format using nak
    Args:
        event: The event to encode
        relays: List of relay hints
        note_format: Whether to use nevent format
    """
    try:
        # Build base command
        cmd = ["nak", "encode"]

        if note_format:
            # For specific event reference (nevent)
            cmd.append("nevent")
            cmd.append(event["id"])
            # Add author hint
            cmd.extend(["--author", event["pubkey"]])
        else:
            # For replaceable event reference (naddr)
            cmd.append("naddr")
            # Required parameters for naddr
            cmd.extend(["--kind", str(event["kind"])])
            cmd.extend(["--pubkey", event["pubkey"]])
            # Get d tag from event tags
            d_tag = next(tag[1] for tag in event["tags"] if tag[0] == "d")
            cmd.extend(["--identifier", d_tag])

        # Add relay hints
        for relay in relays:
            cmd.extend(["--relay", relay])

        print(f"Debug: Encode command: {' '.join(cmd)}")

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            print("Debug: Encoding failed:")
            print(f"Debug: stderr: {result.stderr.decode()}")
            raise Exception(f"Failed to encode event: {result.stderr.decode()}")

        encoded = result.stdout.decode().strip()
        print(f"Debug: Encoded successfully as: {encoded}")
        return encoded
    except Exception as e:
        print(f"Error encoding event: {e}")
        return event["id"]
