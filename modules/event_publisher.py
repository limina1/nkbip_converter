from typing import List
import subprocess
import json
import time


def publish_event(
    event: dict, relays: List[str], max_retries: int = 3, delay: int = 0
) -> bool:
    """Publish an event to specified relays using nak"""
    try:
        print(f"\nDebug: Publishing event {event['id']} to relays: {relays}")
        event_str = json.dumps(event)

        # Create command with relays appended
        cmd = ["nak", "event"] + relays

        print(f"Debug: Event tags: {json.dumps(event.get('tags', []), indent=2)}")
        print(f"Debug: Publish command: {' '.join(cmd)}")

        # Try publishing with retries
        success = False
        attempts = 0
        while not success and attempts < max_retries:
            attempts += 1
            print(f"Debug: Attempt {attempts} of {max_retries}")

            # Create and publish the event
            result = subprocess.run(
                cmd,
                input=event_str.encode("utf-8"),
                capture_output=True,
                timeout=30,  # Longer timeout for publishing
            )

            if result.returncode != 0:
                print("Debug: Publishing failed:")
                print(f"Debug: stdout: {result.stdout.decode()}")
                print(f"Debug: stderr: {result.stderr.decode()}")
                if attempts < max_retries:
                    print(f"Debug: Retrying after {delay} seconds...")
                    time.sleep(delay)
            else:
                print("Debug: Event published successfully")

                # Verify publication by requesting event
                verify_cmd = ["nak", "req", "-i", event["id"]] + relays
                print(f"Debug: Verifying with command: {' '.join(verify_cmd)}")

                verify_result = subprocess.run(
                    verify_cmd, capture_output=True, timeout=10
                )

                if verify_result.returncode == 0 and verify_result.stdout:
                    print("Debug: Event verified on relay")
                    success = True
                else:
                    print("Debug: Could not verify event on relay")
                    if attempts < max_retries:
                        print(f"Debug: Retrying after {delay} seconds...")
                        time.sleep(delay)

        print("Publish successful, adding delay before next event...")
        time.sleep(delay)
        return success

    except subprocess.TimeoutExpired:
        print("Error: Publishing timed out")
        return False
    except Exception as e:
        print(f"Error publishing event: {e}")
        return False
