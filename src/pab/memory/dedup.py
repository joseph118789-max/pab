"""Memory normalization and deduplication."""

import hashlib
import re
from typing import List
from pab.core.models.memory import MemoryItem


def normalize_memory_content(text: str) -> str:
    """Normalize whitespace, lowercasing, and punctuation for content comparison."""
    # Collapse multiple whitespaces
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    # Remove markdown header markers for comparison
    normalized = re.sub(r"#+\s*", "", normalized)
    return normalized


def compute_memory_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized text."""
    norm = normalize_memory_content(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def find_duplicates(items: List[MemoryItem]) -> List[List[MemoryItem]]:
    """Group duplicate memory items by content hash."""
    by_hash = {}
    for item in items:
        h = item.content_hash or compute_memory_hash(item.content)
        by_hash.setdefault(h, []).append(item)
    return [group for group in by_hash.values() if len(group) > 1]
