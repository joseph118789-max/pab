"""Session normalization across disparate provider logs and transcripts."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pab.core.models.session import NormalizedSession, SessionContext


def build_normalized_session(
    source_provider: str,
    source_session_id: str,
    project: str,
    task_summary: str,
    original_objective: str,
    completed_work: List[str],
    pending_work: List[str],
    technical_decisions: List[str],
    important_files: List[str],
    commands_executed: List[str],
    unresolved_issues: List[str],
    transcript_file: Optional[str] = None,
) -> NormalizedSession:
    ctx = SessionContext(
        task_summary=task_summary,
        original_objective=original_objective,
        completed_work=completed_work,
        pending_work=pending_work,
        technical_decisions=technical_decisions,
        important_files=important_files,
        commands_executed=commands_executed,
        unresolved_issues=unresolved_issues,
    )

    return NormalizedSession(
        id=f"{source_provider}-{source_session_id.replace(':', '-')}",
        source_provider=source_provider,
        source_session_id=source_session_id,
        project=project,
        created_at=datetime.now(timezone.utc).isoformat(),
        exported_at=datetime.now(timezone.utc).isoformat(),
        context=ctx,
        transcript_file=transcript_file,
    )
