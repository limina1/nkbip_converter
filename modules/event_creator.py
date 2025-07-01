from typing import List, Dict, Tuple
import subprocess
import sys
import json
import getpass
import time
import os


_DECRYPTED_KEY = None


def decrypt_key(encrypted_key: str, env_pw: str = None) -> str:
    """Decrypt an encrypted key using nak
    
    Args:
        encrypted_key: The encrypted key (ncryptsec)
        env_pw: Name of environment variable containing the password (optional)
    """
    global _DECRYPTED_KEY
    try:
        # First check for password in specified environment variable
        password = None
        if env_pw:
            password = os.environ.get(env_pw)
            if not password:
                print(f"Warning: Environment variable '{env_pw}' not found")
        
        # Fall back to default env var if no specific one provided or found
        if not password:
            password = os.environ.get("NOSTR_PASSWORD")
            
        # Finally, prompt if no env var found
        if not password:
            password = getpass.getpass("Enter password to decrypt key: ")

        # Pass both encrypted key and password as arguments
        decrypt_process = subprocess.run(
            ["nak", "key", "decrypt", encrypted_key, password],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if decrypt_process.returncode != 0:
            print(f"Debug: Decryption failed:")
            print(f"Debug: stdout: {decrypt_process.stdout.decode()}")
            print(f"Debug: stderr: {decrypt_process.stderr.decode()}")
            raise Exception("Failed to decrypt key")

        # Get the decrypted private key
        privkey = decrypt_process.stdout.decode().strip()

        # Verify by getting the pubkey
        pubkey_process = subprocess.run(
            ["nak", "key", "public", privkey],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if pubkey_process.returncode == 0:
            print(f"Debug: Using pubkey: {pubkey_process.stdout.decode().strip()}")
        if not _DECRYPTED_KEY:
            _DECRYPTED_KEY = privkey

        return privkey

    except Exception as e:
        print(f"Error decrypting key: {e}")
        sys.exit(1)


# Global decrypted key cache


def create_event(
    kind: int,
    content: str,
    tags: List[List[str]],
    ncryptsec: str,
    decrypt=True,
    debug=False,
    env_pw=None,
) -> dict:
    """Create and sign a Nostr event using nak"""
    try:
        global _DECRYPTED_KEY

        # Get or decrypt the key
        if _DECRYPTED_KEY is None and decrypt:
            # Read the encrypted key if it's a file path
            if ncryptsec.startswith("/"):
                with open(ncryptsec, "r") as f:
                    ncryptsec = f.read().strip()

            _DECRYPTED_KEY = decrypt_key(ncryptsec, env_pw=env_pw)
        elif _DECRYPTED_KEY is None:
            _DECRYPTED_KEY = ncryptsec

        # Create the complete event
        event = {
            "kind": kind,
            "content": content,
            "tags": tags,
            "created_at": int(time.time()),
        }

        # Convert to JSON - ensure no extra newlines
        event_json = json.dumps(event, separators=(",", ":"))

        # Debug output
        if debug:
            print(f"Debug: Creating event with kind {kind}")
            print(f"Debug: Tags: {json.dumps(tags, indent=2)}")
            print(f"Debug: Event JSON: {event_json}")

        # Create the event with decrypted key using new nak syntax
        cmd = ["nak", "event", "--sec", _DECRYPTED_KEY, "--kind", str(kind), "--content", content]
        
        # Add tags using the new format
        for tag in tags:
            if len(tag) >= 2:
                # Format: -t tagname=value or -t tagname="value1;value2"
                if len(tag) == 2:
                    cmd.extend(["--tag", f"{tag[0]}={tag[1]}"])
                else:
                    # Multiple values in a tag
                    values = ";".join(tag[1:])
                    cmd.extend(["--tag", f"{tag[0]}={values}"])

        # Run the command without stdin since new nak creates event from arguments
        process = subprocess.run(
            cmd, capture_output=True, text=True
        )

        if process.returncode != 0:
            print("Debug: Event creation failed:")
            print(f"Debug: stdout: {process.stdout}")
            print(f"Debug: stderr: {process.stderr}")
            raise Exception(f"Command failed: {process.stderr}")

        result_event = json.loads(process.stdout)
        if debug:
            print(f"Debug: Event created successfully with ID: {result_event['id']}")
            print(f"Debug: Event tags: {json.dumps(result_event['tags'], indent=2)}")
        return result_event

    except subprocess.TimeoutExpired:
        print("Error: Command timed out")
        sys.exit(1)
    except Exception as e:
        print(f"Error creating event: {e}")
        sys.exit(1)


def create_a_tag(event, relay_hint):
    pubkey = event["pubkey"]
    kind = event["kind"]
    tags = event["tags"]
    for tag in tags:
        if tag[0] == "d":
            d_tag = tag[1]
            break
    return ["a", f"{kind}:{pubkey}:{d_tag}", relay_hint, event["id"]]
