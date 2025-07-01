import subprocess
import sys
import json


def verify_event(event: dict, debug: bool = False) -> bool:
    """Verify a Nostr event using nak"""
    try:
        if debug:
            print("\nDebug: Verifying event:")
            print(f"Debug: Event ID: {event['id']}")

        result = subprocess.run(
            ["nak", "verify"],
            input=json.dumps(event).encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )

        if result.returncode != 0:
            print("Debug: Verification failed:")
            print(f"Debug: stdout: {result.stdout.decode()}")
            print(f"Debug: stderr: {result.stderr.decode()}")
        else:
            if debug:
                print("Debug: Event verified successfully")

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("Error: Verification timed out")
        return False
    except Exception as e:
        print(f"Error verifying event: {e}")
        return False
