"""Memory search and relevance scoring."""

import re
from typing import List
from pab.core.models.memory import MemoryItem


def search_memories(items: List[MemoryItem], query: str) -> List[MemoryItem]:
    """Search memory items by case-insensitive keyword match in title, content, or tags."""
    if not query.strip():
        return items

    keywords = query.lower().split()
    matched = []

    for item in items:
        searchable_text = f"{item.title} {item.content} {' '.join(item.tags)}".lower()
        if all(kw in searchable_text for kw in keywords):
            matched.append(item)

    return matched
