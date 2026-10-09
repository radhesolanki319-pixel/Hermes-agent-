# Initial Source Audit

## Intake
- Source received as an uploaded ZIP: `hermes-agent-main.zip`.
- Upstream identity declared by the package metadata: `NousResearch/hermes-agent`.
- License in the supplied source: MIT; copyright notice names Nous Research (2025). Preserve the license and attribution.
- Upstream Git commit SHA identified from archive metadata: `cf23a1a5cc3e02b2a2d4526b4a1ac66ffaac614b`.

## Inventory (ZIP snapshot)
- 17,980 files (excluding directory entries) / 19,198 entries total.
- Approximately 210.7 MB uncompressed.
- Major areas include `agent/`, `tools/`, `gateway/`, `hermes_cli/`, `apps/`, `ui-tui/`, `web/`, `skills/`, `plugins/`, `pm/`, and a large `tests/` suite.
- `pyproject.toml` declares Python `>=3.11,<3.15`; dependency policy emphasizes exact pins.
- `package.json` declares Node workspaces for desktop, TUI, web, and JS tests.
- Root `AGENTS.md` identifies the shared agent core, gateway, TUI, and Electron desktop as existing surfaces and says new capability should generally extend existing tools/plugins/skills rather than duplicate core features.

## Initial architectural conclusion
Hermes already has a broad multi-surface architecture. Re-engineering should be incremental: preserve the existing agent loop, model/provider adapters, tool registry, memory/session persistence, gateway, skills/plugins, and desktop/TUI capabilities until a source-level dependency map and tests justify changes. Do not create parallel replacements for features already present.

## Verification status
Phase 0 source import complete. The complete official NousResearch/Hermes-Agent source tree (commit `cf23a1a5cc3e02b2a2d4526b4a1ac66ffaac614b`) has been extracted from `hermes-agent-main.zip` and imported into `reengineering/phase-0-bootstrap`.

## Next gates
1. Compare imported tree against live upstream repository if necessary.
2. Map agent turn loop, model/provider interfaces, tool execution/approval, memory/session state, gateway, and desktop/mobile integration points.
3. Establish test/build commands and baseline results in a suitable environment.
4. Make the first code change only after the target behavior and existing implementation are verified.
