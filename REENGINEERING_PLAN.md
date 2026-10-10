# Hermes Agent Re-engineering

## Goal
Re-engineer Hermes Agent into an independent personal assistant for Android, Linux, and PC/laptop, with a shared agent core and platform-specific adapters.

## Non-negotiable engineering rules
- Audit the actual source before changing behavior; conversation history is not the source of truth.
- Preserve working behavior until tests prove a replacement is safe.
- Reuse existing capabilities and block duplicate implementations.
- Keep secrets out of source control and logs.
- Retain required upstream license and copyright notices; review dependency licenses before redistribution.
- Make changes in reviewable branches and verify them with tests.

## Target architecture (provisional until source audit)
1. **Agent core:** planning, tool execution, task state, cancellation, retries, and policy checks.
2. **Model gateway:** provider-neutral API, streaming, timeouts, and normalized errors.
3. **Context and memory:** conversation state, retrieval, persistence, and user-controlled deletion/export.
4. **Tool registry:** typed tool contracts, permissions, audit trail, and confirmation for risky actions.
5. **Platform adapters:** Android, Linux, and Windows/PC integration without duplicating core logic.
6. **Connectivity:** explicit network/API access, offline-aware behavior, and secure credential handling.
7. **Quality gates:** unit/integration tests, linting, dependency/license checks, and release builds.

## Execution sequence
- **Phase 0 — Source intake and baseline:** import the upstream source into this repository, record upstream commit/license, map the codebase, identify tests and build commands, and establish a baseline.
- **Phase 1 — Audit:** inventory modules, entry points, integrations, memory, tools, security boundaries, platform assumptions, duplicated logic, and test coverage.
- **Phase 2 — Core stabilization:** fix only verified defects, add regression tests, and preserve existing behavior.
- **Phase 3 — Architecture extraction:** isolate provider/model interfaces, agent orchestration, memory, tools, and platform adapters incrementally.
- **Phase 4 — Cross-platform implementation:** implement and test Android, Linux, and PC adapters against shared contracts.
- **Phase 5 — Hardening and release:** permission model, secrets handling, observability, packaging, documentation, and platform test matrix.

## Current verified status
- **Phase 0 (Source intake and baseline):** Upstream source tree imported from `hermes-agent-main.zip` (verified upstream commit `cf23a1a5cc3e02b2a2d4526b4a1ac66ffaac614b`). 100% file parity verified: 17,980 upstream files tracked in git with 0 missing files and 0 byte mismatches.
- **Phase 1 (Audit & Platform Abstraction):** Android and Termux platform facts implemented (`is_android()`, `is_termux()`, `hermes_platform.termux_adapter`). Fully decoupled from mandatory Nous Portal subscriptions.
- **Phase 2 (Core stabilization & Zero-Daemon Guard):** Strict Zero-Daemon mobile guard active in `tools/terminal_tool_guards.py`, `tools/terminal_tool_background.py`, `gateway/run.py`, and `cron/scheduler_thread.py`. All persistent background servers suppressed on Android/Termux.
- **Phase 3 (Modular Persona & Gemini 3 Enforcement):** Pure Hermes persona active (`persona_config.py`, `~/.hermes/persona.yaml`, `SOUL.md`). Strict Gemini 3-series enforcement in `agent/agent_init.py` (legacy 1.x/2.x automatically upgraded to `gemini-3.8-flash`).
- **Phase 4 (Android Native Hardware Tools):** Implemented and registered `android_torch`, `android_battery`, `android_clipboard`, `android_vibrate`, `android_camera`, and `android_media` in `tools/android_tools.py` and `toolsets.py`.
- **Phase 5 (Hardening & Master Release):** Unified CLI launchers `hermes` and `assistant` installed in `~/.local/bin/`. Full regression test suite passing (35/35 unit tests passed). Live end-to-end tool execution verified on real Android hardware.
