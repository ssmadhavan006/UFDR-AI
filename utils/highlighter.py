# utils/highlighter.py
import re
from typing import Dict, List, Tuple

def create_entity_patterns() -> Dict[str, Tuple[str, str]]:
    """Create patterns for different entity types with their highlighting colors"""
    return {
        'crypto': (
            r'\b(bc1[a-zA-Z0-9]{25,62}|0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b',
            '#FFD700'  # Gold for crypto addresses
        ),
        'phone': (
            r'\+?\d[\d\s\-\(\)]{7,15}',
            '#98FB98'  # Pale green for phone numbers
        ),
        'amount': (
            r'\b(\d+(?:[.,]\d+)*\s*(?:BTC|ETH|USDT|USD|Rs\.?|₹|\$|€|£))\b',
            '#87CEEB'  # Sky blue for amounts with currency
        ),
        'url': (
            r'\b(https?://[^\s]+)\b',
            '#DDA0DD'  # Plum for URLs
        ),
        'email': (
            r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b',
            '#FFB6C1'  # Light pink for emails
        )
    }

def highlight_entities(text: str) -> str:
    """Highlight various entities in the text with different colors"""
    if not text:
        return text
    
    # First clean the text by removing any existing HTML-style tags and noisy fragments
    text = clean_text(text)
    
    # Sanity check: if text still contains HTML-like artifacts, return clean text only
    if any(indicator in text.lower() for indicator in ['style=', 'span', 'background-color', 'padding:', ';']):
        return text  # Return clean text without highlighting to avoid further corruption
    
    patterns = create_entity_patterns()
    
    # Process in reverse order to avoid position shifting issues
    matches = []
    
    # Find all matches first
    for entity_type, (pattern, color) in patterns.items():
        for match in re.finditer(pattern, text):
            start, end = match.span()
            matches.append({
                'start': start,
                'end': end,
                'text': match.group(),
                'entity_type': entity_type,
                'color': color
            })
    
    # Sort matches by start position in reverse order
    matches.sort(key=lambda x: x['start'], reverse=True)
    
    # Apply highlights from end to beginning to avoid position shifting
    for match in matches:
        start, end = match['start'], match['end']
        # Escape the text to prevent any HTML injection
        safe_text = match["text"].replace('<', '&lt;').replace('>', '&gt;')
        highlighted_text = f'<span style="background-color: {match["color"]}; padding: 1px 4px; border-radius: 3px; font-weight: 500;" title="{match["entity_type"].title()}">{safe_text}</span>'
        text = text[:start] + highlighted_text + text[end:]

    return text

def clean_text(text: str) -> str:
    """Aggressively remove HTML tags, CSS fragments and malformed highlighting artifacts.
    
    This function is designed to clean up corrupted text that contains broken HTML/CSS
    from previous highlighting attempts.
    """
    if not text:
        return text
    
    # Step 1: Remove all well-formed HTML tags first
    text = re.sub(r'<[^<>]*>', '', text)
    
    # Step 2: Remove malformed span fragments that appear in corrupted highlighting
    # Remove patterns like "1span style=" or "87CEEB; padding:" etc.
    text = re.sub(r'\d*span\s*style\s*=\s*["\'][^"\'>]*["\'][^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\d*span\s*style\s*=', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\d*span\s+style\s*=', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\d*span\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'span\s*style\s*=', '', text, flags=re.IGNORECASE)
    
    # Step 3: Remove CSS properties and values that appear as plain text
    css_patterns = [
        r'background-color\s*:\s*[^;\s]+;?',
        r'padding\s*:\s*[^;\s]+;?',
        r'border-radius\s*:\s*[^;\s]+;?',
        r'font-weight\s*:\s*[^;\s]+;?',
        r'color\s*:\s*[^;\s]+;?',
        r'margin\s*:\s*[^;\s]+;?',
        r'text-[a-z-]+\s*:\s*[^;\s]+;?'
    ]
    for pattern in css_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Step 4: Remove HTML attributes that appear as plain text
    text = re.sub(r'title\s*=\s*["\'][^"\'>]*["\']', '', text, flags=re.IGNORECASE)
    text = re.sub(r'style\s*=\s*["\'][^"\'>]*["\']', '', text, flags=re.IGNORECASE)
    text = re.sub(r'class\s*=\s*["\'][^"\'>]*["\']', '', text, flags=re.IGNORECASE)
    
    # Step 5: Remove any remaining attribute-like patterns (key="value" or key='value')
    text = re.sub(r'\b\w+\s*=\s*["\'][^"\'>]*["\']', '', text)
    
    # Step 6: Clean up color codes and hex values that appear as plain text
    text = re.sub(r'#[A-Fa-f0-9]{3,6}\b', '', text)
    text = re.sub(r'\b(?:rgb|rgba)\s*\([^)]*\)', '', text)
    
    # Step 7: Remove standalone CSS properties and fragments
    text = re.sub(r'\b(?:padding|margin|border|background|color|font|text|display|position|width|height)\s*[:-]\s*[^\s;]+;?', '', text, flags=re.IGNORECASE)
    
    # Step 8: Remove measurement units that appear standalone (px, em, %, etc.)
    text = re.sub(r'\b\d+(?:px|em|rem|%|pt|pc|in|cm|mm|ex|ch|vw|vh|vmin|vmax)\b', '', text)
    
    # Step 9: Clean up common HTML entities and escape sequences
    text = re.sub(r'&[a-zA-Z0-9]+;', '', text)
    
    # Step 10: Remove specific malformed patterns from corrupted highlighting
    # Remove patterns like "87CEEB; padding:" that appear as plain text
    text = re.sub(r'\b[A-F0-9]{6};\s*padding:', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bCEEB;\s*padding:', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\w+ground-color:', ' ', text, flags=re.IGNORECASE)  # "ckground-color:", "background-color:"
    text = re.sub(r'\be=["\']?background-color:', ' ', text, flags=re.IGNORECASE)  # "e="background-color:"
    text = re.sub(r'\w*ckground-', ' ', text, flags=re.IGNORECASE)  # Remove "ckground-"
    
    # Remove remaining " > patterns and similar artifacts
    text = re.sub(r'\s*["\']\s*>\s*', ' ', text)
    text = re.sub(r'\s*>\s*', ' ', text)
    
    # Remove any remaining semicolons and malformed punctuation
    text = re.sub(r';+', ' ', text)
    text = re.sub(r'\s*[=:]\s*["\'][^"\'>]*["\']', '', text)
    
    # Step 11: Handle timestamp cleaning
    text = re.sub(r'\[(\d{4})n\s*', r'[\1-', text)
    text = re.sub(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}:\d{2}:\d{2})', r'\1-\2-\3T\4Z', text)
    
    # Step 12: Remove duplicated words/tokens that appear from corrupted highlighting
    # This addresses cases where crypto addresses or phone numbers appear twice
    words = text.split()
    cleaned_words = []
    for i, word in enumerate(words):
        # If this word is not a duplicate of the previous word (accounting for minor variations)
        if i == 0 or word != words[i-1]:
            # Also check if it's a substring of the previous word (corrupted duplicates)
            if i == 0 or not (word in words[i-1] and len(word) < len(words[i-1])):
                cleaned_words.append(word)
    text = ' '.join(cleaned_words)
    
    # Step 13: Final cleanup - normalize whitespace and remove extra punctuation
    text = re.sub(r'\s+', ' ', text)  # Collapse all whitespace
    text = re.sub(r'\s*([,.!?])\s*', r'\1 ', text)  # Fix punctuation spacing
    text = re.sub(r'\[\s+', '[', text)  # Fix bracket spacing
    text = re.sub(r'\s+\]', ']', text)
    text = re.sub(r'\s+$', '', text)  # Remove trailing whitespace
    text = re.sub(r'^\s+', '', text)  # Remove leading whitespace
    
    return text

def highlight_query_terms(text: str, query: str) -> str:
    """Highlight query terms in the text, avoiding HTML tags"""
    if not text or not query:
        return text
        
    query_terms = set(query.lower().split())
    
    # Split text by HTML tags to avoid highlighting inside them
    parts = re.split(r'(<[^>]+>)', text)
    
    for i, part in enumerate(parts):
        if not part.startswith('<'):
            # This is not a tag, so we can highlight terms here
            pattern = r'\b(' + '|'.join(re.escape(term) for term in query_terms) + r')\b'
            parts[i] = re.sub(pattern, r'<span style="background-color: #FFFF00; padding: 1px 4px; border-radius: 3px;">\g<0></span>', part, flags=re.IGNORECASE)
            
    return "".join(parts)

def apply_all_highlights(text: str, query: str = None) -> str:
    """Apply both entity and query term highlighting"""
    result = highlight_entities(text)
    if query:
        result = highlight_query_terms(result, query)
    return result