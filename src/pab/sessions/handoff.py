"""Portable Handoff Package generation."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pab.core.models.session import HandoffBundle, NormalizedSession
from pab.core.security import redact_secrets


def generate_handoff_markdown(session: NormalizedSession, target_provider: Optional[str] = None) -> str:
    """Generate structured HANDOFF.md markdown."""
    ctx = session.context
    completed_md = "\n".join(f"- [x] {w}" for w in ctx.completed_work) if ctx.completed_work else "- None recorded"
    pending_md = "\n".join(f"- [ ] {w}" for w in ctx.pending_work) if ctx.pending_work else "- None recorded"
    decisions_md = "\n".join(f"- {d}" for d in ctx.technical_decisions) if ctx.technical_decisions else "- None recorded"
    files_md = "\n".join(f"- `{f}`" for f in ctx.important_files) if ctx.important_files else "- None recorded"
    issues_md = "\n".join(f"- ⚠️ {i}" for i in ctx.unresolved_issues) if ctx.unresolved_issues else "- None recorded"

    md = (
        f"# PersonaOS Portable Handoff Bundle\n\n"
        f"**Source Platform:** {session.source_provider}  \n"
        f"**Target Platform:** {target_provider or 'Any'}  \n"
        f"**Session ID:** `{session.source_session_id}`  \n"
        f"**Exported At:** {session.exported_at}  \n\n"
        f"## 1. Original User Objective\n"
        f"> {ctx.original_objective or 'No specific prompt recorded'}\n\n"
        f"## 2. Task Summary\n"
        f"{ctx.task_summary or 'In-progress task'}\n\n"
        f"## 3. Completed Work\n"
        f"{completed_md}\n\n"
        f"## 4. Pending Work & Next Actions\n"
        f"{pending_md}\n\n"
        f"## 5. Architectural & Technical Decisions\n"
        f"{decisions_md}\n\n"
        f"## 6. Important Files & Artifacts\n"
        f"{files_md}\n\n"
        f"## 7. Outstanding Issues & Blockers\n"
        f"{issues_md}\n"
    )
    return redact_secrets(md)


def create_handoff_package(
    session: NormalizedSession,
    target_provider: Optional[str],
    output_dir: Path,
) -> HandoffBundle:
    """Create on-disk portable handoff bundle."""
    bundle_id = f"handoff-{session.source_provider}-{session.id}"
    bundle_dir = output_dir / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    handoff_md = generate_handoff_markdown(session, target_provider)
    (bundle_dir / "HANDOFF.md").write_text(handoff_md, encoding="utf-8")

    # context.json
    context_json = json.dumps(session.context.model_dump(mode="json"), indent=2)
    (bundle_dir / "context.json").write_text(redact_secrets(context_json), encoding="utf-8")

    # workspace.diff if available
    diff_text = session.context.git_diff_summary or ""
    if diff_text:
        (bundle_dir / "workspace.diff").write_text(diff_text, encoding="utf-8")

    return HandoffBundle(
        bundle_id=bundle_id,
        source_provider=session.source_provider,
        target_provider=target_provider,
        session_id=session.id,
        created_at=datetime.now(timezone.utc).isoformat(),
        handoff_markdown=handoff_md,
        context=session.context,
        workspace_diff=diff_text if diff_text else None,
    )
