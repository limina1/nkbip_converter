"""
NKBIP-01 compliant tag utilities
Implements the full tag specification for curated publications
"""

from typing import List, Dict, Optional, Literal
import re

def clean_tag(text: str) -> str:
    """Clean text for use in tags"""
    # Remove special characters and convert to lowercase
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    # Replace spaces with hyphens and remove multiple hyphens
    cleaned = re.sub(r"[-\s]+", "-", cleaned)
    return cleaned.strip("-")

def create_reference_tag(
    kind: int, pubkey: str, d_tag: str, event_id: str, relay_hint: str = ""
) -> List[str]:
    """Create an 'a' tag following NIP-62 format"""
    ref = f"{kind}:{pubkey}:{d_tag}"
    return ["a", ref, relay_hint, event_id]

# Publication types as defined in NKBIP-01
PublicationType = Literal["book", "illustrated", "magazine", "documentation", "academic", "blog"]

# Auto-update options
AutoUpdateType = Literal["yes", "ask", "no"]

# MIME types for different content
MIME_TYPES = {
    "index": "application/json",
    "asciidoc": "text/asciidoc",
    "markdown": "text/markdown",
    "plain": "text/plain",
    "html": "text/html"
}

# Nostr categorization tags (M tag)
NOSTR_CATEGORIES = {
    "index": "meta-data/index/replaceable",
    "content": "article/publication-content/replaceable",
    "external": "external-content/index/replaceable"
}


class NKBIP01Tags:
    """Helper class for creating NKBIP-01 compliant tags"""
    
    @staticmethod
    def create_index_tags(
        title: str,
        d_tag: str,
        author: Optional[str] = None,
        publication_type: PublicationType = "book",
        auto_update: AutoUpdateType = "yes",
        language: str = "en",
        version: str = "1",
        external: bool = False,
        metadata: Optional[Dict] = None
    ) -> List[List[str]]:
        """
        Create tags for a 30040 publication index event
        
        Required tags:
        - d: unique identifier
        - title: publication title
        - auto-update: update behavior
        - m: MIME type
        - M: Nostr categorization
        """
        tags = [
            ["d", d_tag],
            ["title", title],
            ["auto-update", auto_update],
            ["type", publication_type],
            ["m", MIME_TYPES["index"]],
            ["M", NOSTR_CATEGORIES["external" if external else "index"]],
            ["l", f"{language}, ISO-639-1"],
            ["reading-direction", "left-to-right, top-to-bottom"],
            ["version", version]
        ]
        
        # Add author if provided
        if author:
            tags.append(["author", author])
        
        # Add external flag if applicable
        if external:
            tags.append(["external", "true"])
        
        # Add optional metadata
        if metadata:
            # Standard metadata fields
            if "summary" in metadata:
                tags.append(["summary", metadata["summary"]])
            if "image" in metadata:
                tags.append(["image", metadata["image"]])
            if "published_on" in metadata:
                tags.append(["published_on", metadata["published_on"]])
            if "published_by" in metadata:
                tags.append(["published_by", metadata["published_by"]])
            if "source" in metadata:
                tags.append(["source", metadata["source"]])
            
            # Identifiers
            if "doi" in metadata:
                tags.append(["i", f"doi:{metadata['doi']}"])
                tags.append(["k", "doi"])
            if "isbn" in metadata:
                tags.append(["i", f"isbn:{metadata['isbn']}"])
                if "doi" not in metadata:  # Only add k tag once
                    tags.append(["k", "isbn"])
            
            # Topic tags
            if "tags" in metadata:
                for tag in metadata["tags"]:
                    tags.append(["t", tag])
            
            # Additional authors
            if "additional_authors" in metadata:
                for author in metadata["additional_authors"]:
                    tags.append(["author", author])
        
        return tags
    
    @staticmethod
    def create_content_tags(
        title: str,
        d_tag: str,
        content_type: str = "asciidoc",
        language: str = "en",
        wikilinks: Optional[List[Dict]] = None
    ) -> List[List[str]]:
        """
        Create tags for a 30041 publication content event
        
        Required tags:
        - d: unique identifier
        - title: section title
        - m: MIME type (for content)
        - M: Nostr categorization
        """
        tags = [
            ["d", d_tag],
            ["title", title],
            ["m", MIME_TYPES.get(content_type, MIME_TYPES["plain"])],
            ["M", NOSTR_CATEGORIES["content"]],
            ["l", f"{language}, ISO-639-1"]
        ]
        
        # Add wikilinks if present
        if wikilinks:
            for link in wikilinks:
                # Format: ["wikilink", "term", "<pubkey>", "relay", "<event_id>"]
                tags.append([
                    "wikilink",
                    link["term"],
                    link.get("pubkey", ""),
                    link.get("relay", ""),
                    link.get("event_id", "")
                ])
        
        return tags
    
    @staticmethod
    def add_derivative_work_tags(
        tags: List[List[str]],
        original_author_pubkey: str,
        original_event_id: str,
        relay_url: Optional[str] = None
    ) -> List[List[str]]:
        """
        Add tags for derivative works (p and E tags must be consecutive)
        """
        # Find where to insert (after auto-update tag)
        insert_index = None
        for i, tag in enumerate(tags):
            if tag[0] == "auto-update":
                insert_index = i + 1
                break
        
        if insert_index is None:
            insert_index = len(tags)
        
        # Insert p tag followed immediately by E tag
        p_tag = ["p", original_author_pubkey]
        e_tag = ["E", original_event_id]
        if relay_url:
            e_tag.extend([relay_url, original_author_pubkey])
        
        tags.insert(insert_index, p_tag)
        tags.insert(insert_index + 1, e_tag)
        
        return tags
    
    @staticmethod
    def validate_index_tags(tags: List[List[str]]) -> tuple[bool, List[str]]:
        """
        Validate that index tags meet NKBIP-01 requirements
        Returns (is_valid, list_of_errors)
        """
        errors = []
        tag_dict = {tag[0]: tag[1:] for tag in tags}
        
        # Check required tags
        required = ["d", "title", "auto-update", "m", "M"]
        for req in required:
            if req not in tag_dict:
                errors.append(f"Missing required tag: {req}")
        
        # Validate auto-update value
        if "auto-update" in tag_dict:
            if tag_dict["auto-update"][0] not in ["yes", "ask", "no"]:
                errors.append("auto-update must be 'yes', 'ask', or 'no'")
        
        # Validate MIME type
        if "m" in tag_dict:
            if tag_dict["m"][0] != "application/json":
                errors.append("Index events must have MIME type 'application/json'")
        
        # Check for 'a' tags (references)
        has_references = any(tag[0] == "a" for tag in tags)
        if not has_references:
            errors.append("Index must include at least one 'a' tag reference")
        
        # Check p/E tag ordering for derivative works
        p_index = None
        for i, tag in enumerate(tags):
            if tag[0] == "p":
                p_index = i
            elif tag[0] == "E" and p_index is not None:
                if i != p_index + 1:
                    errors.append("E tag must immediately follow p tag")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_content_tags(tags: List[List[str]]) -> tuple[bool, List[str]]:
        """
        Validate that content tags meet NKBIP-01 requirements
        Returns (is_valid, list_of_errors)
        """
        errors = []
        tag_dict = {tag[0]: tag[1:] for tag in tags}
        
        # Check required tags
        required = ["d", "title"]
        for req in required:
            if req not in tag_dict:
                errors.append(f"Missing required tag: {req}")
        
        return len(errors) == 0, errors


def upgrade_legacy_tags(tags: List[List[str]], event_kind: int) -> List[List[str]]:
    """
    Upgrade legacy tag structure to NKBIP-01 compliance
    """
    tag_dict = {tag[0]: tag[1:] for tag in tags}
    
    # Add missing MIME type
    if "m" not in tag_dict:
        if event_kind == 30040:
            tags.append(["m", MIME_TYPES["index"]])
        else:
            tags.append(["m", MIME_TYPES["asciidoc"]])
    
    # Add missing M tag
    if "M" not in tag_dict:
        if event_kind == 30040:
            is_external = "external" in tag_dict and tag_dict["external"][0] == "true"
            tags.append(["M", NOSTR_CATEGORIES["external" if is_external else "index"]])
        else:
            tags.append(["M", NOSTR_CATEGORIES["content"]])
    
    # Fix language tag format
    if "l" in tag_dict:
        lang_value = tag_dict["l"][0]
        if "ISO-639-1" not in lang_value:
            # Find and update the language tag
            for i, tag in enumerate(tags):
                if tag[0] == "l":
                    tags[i] = ["l", f"{lang_value}, ISO-639-1"]
                    break
    else:
        tags.append(["l", "en, ISO-639-1"])
    
    # Add reading direction if missing (only for index)
    if event_kind == 30040 and "reading-direction" not in tag_dict:
        tags.append(["reading-direction", "left-to-right, top-to-bottom"])
    
    # Add version if missing
    if "version" not in tag_dict:
        tags.append(["version", "1"])
    
    return tags