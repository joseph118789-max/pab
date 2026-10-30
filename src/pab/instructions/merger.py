"""Non-destructive merging of canonical AGENTS.md with provider instructions."""

from typing import Dict
from pab.instructions.differ import parse_instruction_rules


def merge_instruction_rules(canonical_agents_md: str, native_existing: str, provider: str) -> str:
    """
    Merge canonical rules into native instruction file without clobbering native-specific sections.
    """
    canon_rules = parse_instruction_rules(canonical_agents_md)
    native_rules = parse_instruction_rules(native_existing)

    merged_sections: Dict[str, str] = {}

    # 1. Start with canonical rules
    for r in canon_rules:
        merged_sections[r["title"]] = r["content"]

    # 2. Preserve native-specific sections
    for r in native_rules:
        title = r["title"]
        if title not in merged_sections:
            merged_sections[title] = r["content"]
        else:
            # If native section has provider marker or custom notes, preserve both
            if f"[{provider.upper()}]" in r["content"] or "CUSTOM:" in r["content"]:
                merged_sections[title] = f"{merged_sections[title]}\n\n<!-- Native {provider} additions -->\n{r['content']}"

    # Compile result
    output = [f"# Instructions ({provider.upper()})\n<!-- Managed by PersonaOS Agent Bridge (PAB) -->\n"]
    for title, content in merged_sections.items():
        if title.lower() != "instructions":
            output.append(f"## {title}\n{content}\n")
        else:
            output.append(f"{content}\n")

    return "\n".join(output)
