#!/usr/bin/env python3
from sentence_transformers import SentenceTransformer
from .event_creator import create_event
import numpy as np
import pprint
import base64


_MODEL = None
_DIMENSION = 384


def extract_vector_embedding(event):
    """
    Extract vector embedding from a Nostar event

    Args:
        event (dict): The Nostar event object

    Returns:
        numpy.ndarray: The vector embedding as a float32 array, or None if no embedding found
    """
    # Find the vec tag
    for tag in event.get("tags", []):
        if tag and len(tag) > 1 and tag[0] == "vec":
            # Get the base64 encoded string
            base64_string = tag[1]

            # Decode the base64 string to bytes
            binary_data = base64.b64decode(base64_string)

            # Convert bytes to float32 array
            float_array = np.frombuffer(binary_data, dtype=np.float32)

            return float_array

    return None


def create_vector_tag(embedding_array):
    """
    Convert a numpy array to a base64 encoded string for Nostar

    Args:
        embedding_array (numpy.ndarray): The vector embedding array (float32)

    Returns:
        list: A Nostar tag with the encoded embedding
    """
    # Ensure array is float32
    if embedding_array.dtype != np.float32:
        embedding_array = embedding_array.astype(np.float32)

    # Convert to bytes
    binary_data = embedding_array.tobytes()

    # Encode as base64
    base64_string = base64.b64encode(binary_data).decode("ascii")

    # Return as a tag
    return ["vec", base64_string]


def set_model(model):
    global _MODEL
    _MODEL = SentenceTransformer(model)


def create_embedding_event(
    section_event, key, decrypt=True, model="all-MiniLM-L6-v2", primary_relay=None
):
    event_id = section_event["id"]
    tags = []
    try:
        global _MODEL
        if _MODEL is None and model:
            set_model(model)

        # Create the embedding
        content = section_event["content"]
        embedding = _MODEL.encode(content, normalize_embeddings=True)
        if primary_relay:
            tags.append(["e", event_id, primary_relay])
        else:
            tags.append(["e", event_id])
        tags.append(["model", model])
        tags.append(["dims", str(_DIMENSION)])
        tags.append(create_vector_tag(embedding))
        tags.append(["norm", "true"])
        created_event = create_event(1987, "", tags, key, decrypt)
        return created_event
    except Exception as e:
        print(f"Error creating embedding: {e}")
        return None


def main():
    section_event = {
        "kind": 30041,
        "id": "fa0de78853439fa34ea945546a566911cb61df80856b30001a635ee2b73b93f9",
        "pubkey": "cc189cc0723e7384c15e798994a8fd2570c942fa8452dd8eb274047d0a5ac91f",
        "created_at": 1742409493,
        "tags": [
            ["d", "nostr-apps-101-introduction-to-nostr-apps-101"],
            ["title", "Introduction to Nostr Apps 101"],
            ["image", "https://i.nostr.build/xWIVg3lx9usiQSWH.png"],
            ["image", "https://i.nostr.build/uPPHxdVWv7IGjp6S.png"],
            ["image", "https://i.nostr.build/blui49Ro3TjIHuRt.png"],
            ["image", "https://i.nostr.build/1AnH691AJs0B86uD.png"],
            ["m", "text/asciidoc"],
            ["author", "Nostr.Build"],
        ],
        "content": "image::https://i.nostr.build/xWIVg3lx9usiQSWH.png[Introduction Image]\n\n\n\nAs a [[Nostr]] enthusiast and developer, I'm excited to introduce you to the world of Nostr applications. In this section, we'll explore the basics of Nostr apps and why they're revolutionizing the way we interact online.\n\n\n\nimage::https://i.nostr.build/uPPHxdVWv7IGjp6S.png[Overview Image]\n\n=== The Basics of Nostr\nimage::https://i.nostr.build/blui49Ro3TjIHuRt.png[Basics Image]\n\n\n\nNostr, which stands for \"Notes and Other Stuff Transmitted by Relays,\" is an [[open protocol]] that enables global decentralization and censorship-resistant media. To understand its significance, let's compare it to a centralized platform like Twitter:\n\n\n\n* Twitter: Centralized, controlled by a single company\n\n* Nostr: Decentralized, powered by [[relays]] that anyone can host\n\n\n\nThis decentralized nature of Nostr provides several advantages:\n\n\n\n1. Resilience: If one relay goes down, others can take its place\n\n2. Diversity: Relays can represent different areas of interest (e.g., cooking, Bitcoin)\n\n3. Global connectivity: Users can connect with people worldwide based on shared interests\n\n=== Key Concepts in Nostr\nimage::https://i.nostr.build/1AnH691AJs0B86uD.png[Key Concepts Image]\n\n==== Public and Private Keys\nNostr uses a [[public-private key]] system for user identification and security. This system is similar to a username and password but with some crucial differences:\n\n\n\n* Your public key is like your username\n\n* Your private key is like your password, but it can't be changed\n\n* Be extremely careful with your private key - it's the key to your Nostr identity\n\n\n\n[IMPORTANT]\n\n==== \nNever share your private key or enter it into untrusted clients. A compromised private key could lead to a complete loss of your Nostr identity.\n\n==== \n\n\n==== Relays\n[[Relays]] are the backbone of the Nostr network. They serve several purposes:\n\n\n\n* Store and transmit messages\n\n* Allow users to connect based on interests\n\n* Provide redundancy and resilience to the network\n\n==== Encrypted Direct Messages\nOne of the key features of Nostr is the ability to send [[encrypted direct messages]]. These messages are:\n\n\n\n* End-to-end encrypted\n\n* Visible only to the sender and recipient\n\n* Secure by default\n\n=== The Potential of Nostr Apps\nThe beauty of Nostr lies in its versatility. While many current applications are Twitter-like clones, the potential use cases are vast:\n\n\n\n* Social media platforms\n\n* Messaging apps\n\n* Content creation and sharing tools\n\n* Collaborative workspaces\n\n* And much more!\n\n\n\nIn essence, Nostr can be adapted to almost any online interaction you can imagine. Its decentralized nature and focus on user privacy make it an exciting platform for developers and users alike.\n\n\n\nAs we delve deeper into the world of Nostr apps, we'll explore specific applications, their features, and how they're pushing the boundaries of decentralized communication. Stay tuned for more insights into this revolutionary protocol!",
        "sig": "d0d50940cf09d4933faf499b264960422a641b0e49b4008139388880e671f0b5d9ef3ad2c3309684f8b4d57c3a5bd216c709e2f28e5a4c863fc42f4e4987e820",
    }
    key = "57477c2240b53c583e1b156eb102be9733892d27d2fc04d638226516c1b849cb"  # test key
    event = create_embedding_event(section_event, key, decrypt=False)
    pprint.pprint(event)


if __name__ == "__main__":
    main()
