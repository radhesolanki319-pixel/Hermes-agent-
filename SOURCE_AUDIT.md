# Initial Source Audit

## Intake
- Source received as an uploaded ZIP: `hermes-agent-main.zip`.
- Upstream identity declared by the package metadata: `NousResearch/hermes-agent`.
- License in the supplied source: MIT; copyright notice names Nous Research (2025). Preserve the license and attribution.
- This archive is a source snapshot; no upstream Git commit SHA was established from the archive itself.

## Inventory (ZIP snapshot)
- 17,980 files (excluding directory entries).
- Approximately 210.7 MB uncompressed.
- Major areas include `agent/`, `tools/`, `gateway/`, `hermes_cli/`, `apps/`, `ui-tui/`, `web/`, `skills/`, `plugins/`, `pm/`, and a large `tests/` suite.
- `pyproject.toml` declares Python `>=3.11,<3.15`; dependency policy emphasizes exact pins.
- `package.json` declares Node workspaces for desktop, TUI, web, and JS tests.
- Root `AGENTS.md` identifies the shared agent core, gateway, TUI, and Electron desktop as existing surfaces and says new capability should generally extend existing tools/plugins/skills rather than duplicate core features.

## Initial architectural conclusion
Hermes already has a broad multi-surface architecture. Re-engineering should be incremental: preserve the existing agent loop, model/provider adapters, tool registry, memory/session persistence, gateway, skills/plugins, and desktop/TUI capabilities until a source-level dependency map and tests justify changes. Do not create parallel replacements for features already present.

## Verification status
This is an inventory-level audit only. No build, test suite, runtime behavior, or security review has been verified yet. The supplied ZIP is not yet imported as the full source tree into this GitHub repository, and its exact upstream commit is unknown.

## Next gates
1. Identify the archive's exact upstream release/commit and compare with the live upstream repository.
2. Map agent turn loop, model/provider interfaces, tool execution/approval, memory/session state, gateway, and desktop/mobile integration points.
3. Establish test/build commands and baseline results in a suitable environment.
4. Make the first code change only after the target behavior and existing implementation are verified.
