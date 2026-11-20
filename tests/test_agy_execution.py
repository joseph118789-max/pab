"""Tests for the real AGY subprocess runner (fake `agy` binary)."""

import json
import os
import stat
from pathlib import Path

import pytest

from pab.providers.agy.execution import AgyRunner
from pab.providers.agy.workers import AgyWorkerProfile


FAKE_AGY = """#!/usr/bin/env bash
echo "ARGS:$@" >> "$FAKE_AGY_LOG"
case "${FAKE_AGY_MODE:-success}" in
  success)
    echo '{"conversation_id":"conv-1234","status":"SUCCESS","response":"Hello from AGY","num_turns":1,"usage":{"total_tokens":42}}'
    ;;
  notsuccess)
    echo '{"conversation_id":"conv-1234","status":"ERROR","response":"boom"}'
    ;;
  empty)
    echo '{"conversation_id":"conv-1234","status":"SUCCESS","response":"   "}'
    ;;
  notrace)
    echo '{"status":"SUCCESS","response":"no trace id"}'
    ;;
  badjson)
    echo 'this is not json'
    ;;
  fail)
    echo "agy exploded" >&2
    exit 3
    ;;
  hang)
    sleep 30
    ;;
esac
"""


@pytest.fixture
def fake_agy(tmp_path: Path) -> Path:
    script = tmp_path / "fake_agy.sh"
    script.write_text(FAKE_AGY, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.fixture
def worker(tmp_path: Path) -> AgyWorkerProfile:
    workdir = tmp_path / "agents" / "sales"
    workdir.mkdir(parents=True)
    profile_home = tmp_path / ".agy-seekn"
    profile_home.mkdir()
    return AgyWorkerProfile(
        worker_id="sales",
        label="AGY-Sales",
        profile="seekn",
        workdir=workdir,
        profile_home=profile_home,
    )


def _runner(fake_agy: Path, monkeypatch) -> AgyRunner:
    monkeypatch.setenv("FAKE_AGY_LOG", str(fake_agy.parent / "agy.log"))
    return AgyRunner(executable_path=str(fake_agy))


def test_successful_execution_captures_result(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "success")
    runner = _runner(fake_agy, monkeypatch)

    result = runner.run(worker, prompt="say hello", timeout=30)

    assert result.ok is True
    assert result.conversation_id == "conv-1234"
    assert result.response == "Hello from AGY"
    assert result.status == "SUCCESS"
    assert result.exit_code == 0
    assert result.error is None
    assert result.num_turns == 1
    assert result.usage["total_tokens"] == 42
    assert result.profile == "seekn"
    assert result.workdir == str(worker.workdir)


def test_command_places_output_format_before_print(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "success")
    runner = _runner(fake_agy, monkeypatch)
    runner.run(worker, prompt="say hello", timeout=30)

    log = (fake_agy.parent / "agy.log").read_text(encoding="utf-8")
    args = log.strip().splitlines()[-1]
    assert args.index("--output-format") < args.index("--print")
    assert args.index("--print") < args.index("say hello")


def test_profile_home_is_exported_to_the_child_process(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "success")
    runner = _runner(fake_agy, monkeypatch)

    env = runner.build_env(worker.profile_home)
    assert env["HOME"] == str(worker.profile_home)
    assert env["GEMINI_CONFIG_DIR"] == str(worker.profile_home / ".gemini" / "config")


def test_non_zero_exit_is_a_failure(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "fail")
    runner = _runner(fake_agy, monkeypatch)

    result = runner.run(worker, prompt="explode", timeout=30)

    assert result.ok is False
    assert result.exit_code == 3
    assert "non-zero" in (result.error or "")
    assert "agy exploded" in result.stderr_tail


def test_invalid_json_is_a_failure(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "badjson")
    runner = _runner(fake_agy, monkeypatch)

    result = runner.run(worker, prompt="garbage", timeout=30)

    assert result.ok is False
    assert "JSON" in (result.error or "")
    assert result.conversation_id is None


def test_non_success_status_is_a_failure(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "notsuccess")
    runner = _runner(fake_agy, monkeypatch)

    result = runner.run(worker, prompt="boom", timeout=30)

    assert result.ok is False
    assert "ERROR" in (result.error or "")


def test_empty_response_is_a_failure(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "empty")
    runner = _runner(fake_agy, monkeypatch)

    result = runner.run(worker, prompt="nothing", timeout=30)

    assert result.ok is False
    assert "empty response" in (result.error or "")


def test_missing_trace_id_is_a_failure(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "notrace")
    runner = _runner(fake_agy, monkeypatch)

    result = runner.run(worker, prompt="no trace", timeout=30)

    assert result.ok is False
    assert "conversation_id" in (result.error or "")


def test_timeout_is_a_failure(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "hang")
    runner = _runner(fake_agy, monkeypatch)

    result = runner.run(worker, prompt="hang", timeout=2)

    assert result.ok is False
    assert "timed out" in (result.error or "")


def test_missing_workdir_is_a_failure(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "success")
    runner = _runner(fake_agy, monkeypatch)

    result = runner.run(worker, prompt="hello", timeout=30, workdir=worker.workdir.parent / "nope")

    assert result.ok is False
    assert "workdir does not exist" in (result.error or "")


def test_missing_profile_home_is_a_failure(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "success")
    runner = _runner(fake_agy, monkeypatch)

    broken = AgyWorkerProfile(
        worker_id=worker.worker_id,
        label=worker.label,
        profile=worker.profile,
        workdir=worker.workdir,
        profile_home=worker.profile_home.parent / ".agy-missing",
    )
    result = runner.run(broken, prompt="hello", timeout=30)

    assert result.ok is False
    assert "profile home does not exist" in (result.error or "")


def test_empty_prompt_is_rejected(fake_agy: Path, worker: AgyWorkerProfile, monkeypatch):
    runner = _runner(fake_agy, monkeypatch)
    result = runner.run(worker, prompt="   ", timeout=30)
    assert result.ok is False
    assert "empty prompt" in (result.error or "")


def test_missing_executable_is_a_failure(worker: AgyWorkerProfile, monkeypatch):
    runner = AgyRunner(executable_path=None)
    monkeypatch.setattr("pab.providers.agy.execution.get_agy_bin", lambda: None)
    result = runner.run(worker, prompt="hello", timeout=30)
    assert result.ok is False
    assert "executable not found" in (result.error or "")
