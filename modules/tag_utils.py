import re
from typing import List, Dict, Optional, Literal
from habanero import Crossref
import json
from pprint import pprint

# Import NKBIP-01 utilities
from modules.nkbip01_tags import (
    NKBIP01Tags, 
    upgrade_legacy_tags,
    PublicationType,
    AutoUpdateType,
    MIME_TYPES,
    NOSTR_CATEGORIES
)


def clean_tag(text: str) -> str:
    """Clean text for use in tags"""
    # Remove special characters and convert to lowercase
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    # Replace spaces with hyphens and remove multiple hyphens
    cleaned = re.sub(r"[-\s]+", "-", cleaned)
    return cleaned.strip("-")


def create_standard_tag(tag_type: str, value: str) -> List[str]:
    """Create a standard tag with type and value"""
    return [tag_type, value]


def create_reference_tag(
    kind: int, pubkey: str, d_tag: str, event_id: str, relay_hint: str = ""
) -> List[str]:
    """Create an 'a' tag following NIP-62 format
    Format: ["a", "kind:pubkey:dtag", "<relay hint>", "<event id>"]
    """
    # Create the reference string without the dtag prefix
    ref = f"{kind}:{pubkey}:{d_tag}"
    return ["a", ref, relay_hint, event_id]


def create_section_tags(
    doc_title: str, section_title: str, doc_author: str = None, namespace: bool = False
) -> List[List[str]]:
    """Create tags for a section event following NKBIP-01 format"""
    if namespace:
        d_tag = f"{clean_tag(doc_title)}-{clean_tag(section_title)}"
    else:
        d_tag = clean_tag(section_title)

    # Use NKBIP-01 compliant tag creation
    return NKBIP01Tags.create_content_tags(
        title=section_title,
        d_tag=d_tag
    )


def create_index_tags(
    doc_title: str, auto_update: str = "yes", doc_author: str = None
) -> List[List[str]]:
    """Create initial tags for an index event following NKBIP-01"""
    d_tag = clean_tag(doc_title)
    
    # Use NKBIP-01 compliant tag creation
    return NKBIP01Tags.create_index_tags(
        title=doc_title,
        d_tag=d_tag,
        author=doc_author,
        auto_update=auto_update
    )


def add_reference_to_index(
    index_tags: List[List[str]], section_event: dict, d_tag: str, relay: str
) -> List[List[str]]:
    """Add a section reference to index tags
    Following NIP-62 format for 'a' tags
    """
    ref_tag = create_reference_tag(
        kind=section_event["kind"],
        pubkey=section_event["pubkey"],
        d_tag=d_tag,  # Use clean d_tag without prefix
        event_id=section_event["id"],
        relay_hint=relay,
    )
    index_tags.append(ref_tag)
    return index_tags


def create_external_tags(open_graph: dict, debug=False) -> List[List[str]]:
    """Create an external event using the OpenGraph data and sections"""
    # Extract necessary data from OpenGraph
    meta = open_graph.get("meta", {})
    
    # Build metadata dict for NKBIP-01
    metadata = {}
    
    if open_graph.get("image"):
        metadata["image"] = open_graph["image"]
    if meta.get("description"):
        metadata["summary"] = meta["description"]
    if meta.get("article:published_time"):
        metadata["published_on"] = meta["article:published_time"]
    if open_graph.get("url"):
        metadata["source"] = open_graph["url"]
    
    # Collect tags
    tags_list = []
    if meta.get("article:tag"):
        tags_list.extend(meta["article:tag"])
    metadata["tags"] = tags_list
    
    # Collect authors
    authors = []
    if meta.get("article:author"):
        authors.append(meta["article:author"])
    if meta.get("book:author"):
        authors.append(meta["book:author"])
    
    # ISBN
    if meta.get("book:isbn"):
        metadata["isbn"] = meta["book:isbn"]
    
    # Publication date
    if meta.get("book:release_date"):
        metadata["published_on"] = meta["book:release_date"]
    
    # Determine publication type
    pub_type = "book" if "book:" in str(meta) else "article"
    if open_graph.get("type") == "academic":
        pub_type = "academic"
    
    # Create NKBIP-01 compliant tags
    title = open_graph.get("title", "")
    d_tag = clean_tag(title)
    
    tags = NKBIP01Tags.create_index_tags(
        title=title,
        d_tag=d_tag,
        author=authors[0] if authors else None,
        publication_type=pub_type,
        external=True,
        metadata=metadata
    )
    
    # Add additional authors
    for author in authors[1:]:
        tags.append(["author", author])
    
    # Add URL tag if present
    if open_graph.get("url"):
        tags.append(["url", open_graph["url"]])
    
    if debug:
        for tag in tags:
            print(f"Debug: Tag: {tag[0]} - Value: {tag[1] if len(tag) > 1 else ''}")
    
    return tags


def fetch_doi_metadata(doi):
    """
    Fetch DOI metadata and format it according to NKBIP-01 structure
    """
    # Clean DOI if it has a prefix
    clean_doi = doi.replace("https://doi.org", "") if "https://doi.org" in doi else doi
    
    # Initialize Crossref client
    cr = Crossref()
    
    try:
        # Fetch metadata from Crossref
        result = cr.works(ids=clean_doi)
        metadata = result["message"]
        
        # Build metadata dict
        meta_dict = {
            "doi": clean_doi,
            "source": f"https://doi.org/{clean_doi}",
            "published_by": metadata.get("publisher", "public domain")
        }
        
        # Cover image (using a generic pattern for Springer journals)
        if "ISSN" in metadata and metadata["ISSN"]:
            meta_dict["image"] = "https://i.nostr.build/kUoQk9R1PsWBN5nb.jpg"
        
        # Summary (title or abstract)
        if "title" in metadata and metadata["title"]:
            summary = metadata["title"][0]
            if "abstract" in metadata and metadata["abstract"]:
                # Use abstract instead if available (clean HTML tags)
                summary = re.sub("<[^<]+?>", "", metadata["abstract"])
            meta_dict["summary"] = summary
        
        # Published date
        if "published" in metadata and "date-parts" in metadata["published"]:
            date_parts = metadata["published"]["date-parts"][0]
            if len(date_parts) >= 3:
                published_date = f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
                meta_dict["published_on"] = published_date
        
        # Title and d-tag
        title = metadata["title"][0] if "title" in metadata and metadata["title"] else ""
        title_slug = re.sub(r"[^a-z0-9]", "-", title.lower())
        title_slug = re.sub(r"-+", "-", title_slug).strip("-")
        
        # First author
        first_author = ""
        authors = []
        if "author" in metadata and metadata["author"]:
            for author in metadata["author"]:
                author_name = ""
                if "given" in author:
                    author_name += author["given"]
                if "family" in author:
                    if author_name:
                        author_name += " "
                    author_name += author["family"]
                
                if author_name:
                    authors.append(author_name)
            
            if authors:
                first_author = metadata["author"][0].get("family", "").lower()
                first_author = re.sub(r"[^a-z0-9]", "-", first_author)
        
        doc_id = f"{title_slug}-by-{first_author}-v-1" if first_author else f"{title_slug}-v-1"
        
        # Additional authors for metadata
        if len(authors) > 1:
            meta_dict["additional_authors"] = authors[1:]
        
        # Create NKBIP-01 compliant tags
        tags = NKBIP01Tags.create_index_tags(
            title=title,
            d_tag=doc_id,
            author=authors[0] if authors else None,
            publication_type="academic",
            external=True,
            metadata=meta_dict
        )
        
        return tags
        
    except Exception as e:
        print(f"Error fetching DOI metadata: {e}")
        return []


# Backward compatibility functions
def create_section_tags_legacy(
    doc_title: str, section_title: str, doc_author: str = None, namespace: bool = False
) -> List[List[str]]:
    """Legacy version without NKBIP-01 compliance"""
    if namespace:
        d_tag = f"{clean_tag(doc_title)}-{clean_tag(section_title)}"
    else:
        d_tag = clean_tag(section_title)

    return [["d", d_tag], ["title", section_title]]


def create_index_tags_legacy(
    doc_title: str, auto_update: str = "yes", doc_author: str = None
) -> List[List[str]]:
    """Legacy version without NKBIP-01 compliance"""
    if doc_author:
        return [
            ["d", clean_tag(doc_title)],
            ["title", doc_title],
            ["auto-update", auto_update],
            ["author", doc_author],
            ["type", "book"],
        ]
    return [
        ["d", clean_tag(doc_title)],
        ["title", doc_title],
        ["auto-update", auto_update],
    ]
