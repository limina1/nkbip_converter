import re
from typing import Dict

def convert_md_to_adoc(markdown_text: str) -> str:
    """Convert markdown to AsciiDoc format"""
    # Convert headers
    text = re.sub(r'^# (.*)', r'= \1', markdown_text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*)', r'== \1', text, flags=re.MULTILINE)
    text = re.sub(r'^### (.*)', r'=== \1', text, flags=re.MULTILINE)
    
    # Convert code blocks
    text = re.sub(r'```(\w+)?\n(.*?)\n```', r'[source,\1]\n----\n\2\n----', text, flags=re.MULTILINE | re.DOTALL)
    
    # Convert inline code
    text = re.sub(r'`([^`]+)`', r'`\1`', text)
    
    # Convert links
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1 <\2>', text)
    
    # Convert emphasis
    text = re.sub(r'\*\*([^\*]+)\*\*', r'*\1*', text)  # bold to strong
    text = re.sub(r'_([^_]+)_', r'_\1_', text)  # italic remains italic
    
    return text

def merge_markdown_into_adoc(markdown_path: str, adoc_content: Dict) -> Dict:
    """Read markdown file, convert it to AsciiDoc, and merge it into the document"""
    try:
        # Read the markdown file
        with open(markdown_path, 'r') as f:
            markdown_text = f.read()
        
        # Convert to AsciiDoc
        readme_adoc = convert_md_to_adoc(markdown_text)
        
        # Create a new section for the README
        readme_section = {
            'title': 'NAK README',
            'level': 1,
            'content': readme_adoc
        }
        
        # Insert README as the first section
        adoc_content['sections'].insert(0, readme_section)
        
        return adoc_content
        
    except Exception as e:
        print(f"Warning: Failed to convert README: {e}")
        return adoc_content