# ADR 0010: Real AGY Execution, Explicit Dispatch Support, and Honest Task Lifecycle

## Status
Accepted

## Context

`pab run dispatch --agent agy` reported success without running anything.

Observed behaviour (Sentinel Ops, 2026-11-20):

- `dispatch.status = settled` returned in ~0.1 s
- `result_summary` was a fixed template string
  (`"Google Antigravity CLI (agy) executed review/task '<title>'"`)
- the orchestration task flipped to `completed`
- **no AGY process was spawned**, no conversation was created

The root cause was in `OrchestrationEngine.dispatch_task()`: only the Pi adapter had a
real execution path. Every other provider fell into a branch that fabricated a PID
(`1000 + uuid % 9000`), a `settled` status and a success message.

Two further defects were found while fixing this:

1. **Profile isolation was path-fragile.** The AGY shell wrapper (`~/.agy-wrapper.sh`)
   selects an isolated profile HOME (`~/.agy-<profile>`) by matching the literal
   process CWD against `/root/projects/sentinel_ops/agents/<worker>`. The real worker
   tree is bind-mounted, so canonicalising an absolute worktree path
   (`Path.resolve()`) yields
   `/root/.openclaw/workspace/projects/sentinel_ops/agents/<worker>`, which matches no
   wrapper case and silently falls back to the **default (shared) profile**.
2. **Task lifecycle conflated acceptance with completion.** A dispatch that was merely
   accepted marked the orchestration task `completed`.

## Decision

1. **AGY gets a real execution adapter.**
   `AgyAdapter.launch()` executes the AGY CLI in print mode
   (`agy --output-format json --print <prompt>`) as a managed OS process, in the
   worker's working directory, with the worker's isolated profile HOME exported into
   the child environment. The JSON result is parsed and normalised into an
   `AgyExecutionResult` (conversation id / trace id, response, usage, duration,
   transcript path, profile log artefact).

2. **Profile isolation is resolved by PAB, not by CWD matching.**
   `AgyWorkerRegistry` maps a worker id (`automation`, `delivery`, `qa`, `research`,
   `sales`) to its workdir, AGY profile and profile home. The profile home is applied
   through the `HOME` environment variable, so it is correct for *every* path form of
   the same worker directory. Worker resolution accepts absolute paths, mirrored
   absolute paths and relative paths.

3. **Unsupported providers fail explicitly.**
   Only providers with a verified execution implementation (`agy`, `pi`) may be
   dispatched. `claude`, `codex`, `openclaw` (and any other provider without an
   implementation) raise `UnsupportedOperationError` instead of reporting a fabricated
   success. They remain explicitly unsupported until they are implemented and tested
   separately.

4. **Failures are never silent.** Missing executable, missing workdir, missing profile
   home, timeout (the whole process group is terminated), non-zero exit code,
   unparsable JSON, AGY status other than `SUCCESS`, empty response and missing
   conversation id are all hard failures with an explicit error message.

5. **Task lifecycle follows the execution, not the dispatch.**
   - `completed` only after a verified execution returned a valid result
   - `failed` when the execution failed
   - `dispatched` when the execution was accepted but is still running (Pi)
   - `pending` for dry runs — a dry run executes nothing

6. **Records mirror reality.** The dispatch record, the task record and the PAB
   execution record all carry the same conversation id, profile, workdir, exit code and
   response, and are persisted in the PAB database.

## Consequences

### Positive
- `pab run dispatch --agent agy` really runs AGY, with per-worker profile isolation,
  verifiable through the conversation id, the transcript path and the profile-local
  AGY CLI log.
- No provider can report a success it did not achieve.
- The Sentinel Ops five-worker chain (OpenClaw → PAB → AGY) works end to end.

### Negative / Limitations
- Claude, Codex and OpenClaw dispatch is now rejected instead of silently "succeeding".
  This is intentional: the previous behaviour was a false success.
- AGY print mode is a single turn; long-running multi-turn work is not modelled yet.
- AGY print mode requires `--dangerously-skip-permissions` (headless mode cannot
  prompt), matching the behaviour of the machine's AGY wrapper.
- Profile-local conversation stores are shared through AGY's single-folder mode, so
  profile isolation is proven by the profile-local CLI log and the exported `HOME`,
  not by the shared transcript store.
