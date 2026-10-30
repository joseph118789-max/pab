"""Unit tests for Security, Redaction, and Path Validation."""

from pathlib import Path
import pytest
from pab.core.security import (
    ensure_secure_permissions,
    redact_secrets,
    validate_safe_path,
)


def test_secret_redaction():
    text = (
        "api_key: 'abcdef1234567890abcdef'\n"
        "Authorization: Bearer my-secret-bearer-token-123456\n"
        "password = 'SuperSecretPassword!'\n"
        "GITHUB_TOKEN=ghp_123456789012345678901234567890123456\n"
    )
    redacted = redact_secrets(text)
    assert "[REDACTED]" in redacted
    assert "abcdef1234567890abcdef" not in redacted
    assert "my-secret-bearer-token-123456" not in redacted
    assert "SuperSecretPassword!" not in redacted


def test_path_traversal_detection(tmp_path: Path):
    safe_root = tmp_path / "safe"
    safe_root.mkdir()
    safe_child = safe_root / "subdir" / "file.txt"

    # Valid relative path inside root
    validated = validate_safe_path(safe_child, safe_root)
    assert validated == safe_child.resolve()

    # Path traversal outside root
    escape_path = safe_root / ".." / "secret.env"
    with pytest.raises(ValueError) as exc_info:
        validate_safe_path(escape_path, safe_root)
    assert "Path traversal detected" in str(exc_info.value)


def test_secure_permissions(tmp_path: Path):
    test_dir = tmp_path / "secure_dir"
    test_dir.mkdir()
    ensure_secure_permissions(test_dir)
    assert oct(test_dir.stat().st_mode)[-3:] == "700"

    test_file = test_dir / "secret.txt"
    test_file.write_text("classified", encoding="utf-8")
    ensure_secure_permissions(test_file)
    assert oct(test_file.stat().st_mode)[-3:] == "600"
