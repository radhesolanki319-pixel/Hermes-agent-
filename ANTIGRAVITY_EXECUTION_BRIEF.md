# Antigravity Execution Brief — Hermes Personal Assistant Re-engineering

## Mission
Work directly in this repository and complete a source-driven re-engineering of the existing Hermes Agent into the user's personal assistant across Android/Termux, Linux, Windows PC/laptop, and existing desktop/TUI/gateway surfaces. Do not merely produce a plan. Implement changes, run checks in the available environment, and commit each coherent verified increment to `reengineering/phase-0-bootstrap`. Never modify `main` directly.

## Required operating rules
1. Inspect the actual current branch, git status, recent commits, all applicable `AGENTS.md` files, `REENGINEERING_PLAN.md`, and `SOURCE_AUDIT.md` before editing. Treat source code as truth; update stale docs.
2. Preserve existing working behavior and upstream MIT license/copyright. Do not replace Hermes with a toy app or rewrite existing working components without evidence.
3. Extend existing agent/provider/tool/plugin/skill/platform abstractions. Do not duplicate capabilities already implemented.
4. Never hardcode API keys or commit secrets. Reuse existing credential/config flows. Redact secrets from logs.
5. Do not perform destructive device actions, send messages, purchase, or execute risky external actions without the existing permission/confirmation controls.
6. Every behavior change requires focused regression tests. Run tests and lint/type/build checks where feasible. Clearly mark checks that could not run and why. Never claim a check passed without captured output.
7. Keep changes small and reviewable. Commit working increments with clear messages. Do not merge to `main` or change repository visibility/settings.

## Scope and completion criteria
A. Baseline & audit
- Confirm source commit, branch, Python/Node requirements, install and test commands.
- Map agent loop, model/provider interfaces, streaming/errors, conversation state/memory, tool permissions, skills/plugins, scheduler, gateway, CLI/TUI, Electron desktop, Android/Termux support.
- Correct the contradictory/stale status text in `REENGINEERING_PLAN.md` and `SOURCE_AUDIT.md` based on the actual tree and measured results.

B. Platform abstraction
- Verify the new `hermes_platform.host.runtime.is_android()` and exports from `hermes_platform.host`; maintain distinct Android-vs-Termux predicates and follow `hermes_platform/AGENTS.md`.
- Trace every relevant host decision to the shared platform layer; avoid scattered environment checks.
- Identify real Android/Termux incompatibilities (native dependencies, subprocesses, paths, background execution, permissions, browser/device APIs) and implement only source-verified fixes with tests.
- Keep Linux, macOS and Windows behavior intact.

C. Personal-assistant reliability
- Audit model/provider configuration and API credential setup, stream handling, retry/timeout/error reporting.
- Audit memory persistence, export/deletion, and per-user/session isolation.
- Audit tool execution, approval boundaries, command/file operations, network access and auditability.
- Reuse existing features; add missing functionality only when proven absent and needed.

D. User experience and packaging
- Check existing CLI/TUI/Electron/gateway surfaces before adding a new UI.
- Provide a realistic Android/Termux launch/install path only if supported by dependencies and platform constraints. Do not claim a native Android APK exists unless a real build is produced and verified.
- Update docs with exact tested commands and known limitations.

E. Verification
- Run focused platform tests first, then the broadest feasible Python tests, formatting/lint/type checks, JS tests/builds, and relevant security/config checks.
- Inspect the final diff for accidental deletions, duplicated logic, secret leakage, licensing issues and unrelated edits.
- Record exact commands, pass/fail counts, skipped checks and environment limits in `REENGINEERING_VERIFICATION.md`.

## Immediate known work
- Branch: `reengineering/phase-0-bootstrap`
- Recent commits added `is_android()` in `hermes_platform/host/runtime.py`, five tests in `tests/hermes_platform/test_runtime.py`, and exports in `hermes_platform/host/__init__.py`.
- These tests have not yet been executed; verify their correctness and run them before building on them.
- Main branch must remain untouched.

## Definition of done
Do not stop after writing another plan. Continue implementation until the verified scope above is complete or a genuine external blocker prevents further work. If blocked, finish all unblocked work and document the exact blocker, evidence, completed changes, test output, and the single action required from the user. Do not claim “complete” if core acceptance criteria or tests remain outstanding.
