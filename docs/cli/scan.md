<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 tsitu0 <tomsitu0102@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# dev-library scan

Discover MCP servers, hooks, and telemetry configuration across your harness configs. `scan` is **read-only** -- it shows what you have without modifying any files.

To install session telemetry hooks, use [`dev-library doctor patch`](doctor.md). MCP commands and URLs are never rewritten.

## Synopsis

```bash
dev-library scan [--harness <harness>]
```

## Options

| Option | Description |
| --- | --- |
| `--harness <harness>` | Scope to one harness: `cursor`, `kiro`, `claude-code`, `codex`, `copilot`, `copilot-cli`, `opencode`, `antigravity`, `goose`, `pi` |

If you run `dev-library scan` with no flags, it auto-detects every installed harness and scans each in turn.

## What it does

1. Finds MCP config files:
   * Claude Code: `~/.claude/settings.json`
   * Kiro: `.kiro/settings/mcp.json` (project) or `~/.kiro/settings/mcp.json` (home)
   * Cursor: `.cursor/mcp.json`
   * Copilot: `.vscode/mcp.json`
   * Antigravity: `.agents/mcp_config.json` or `~/.gemini/antigravity-cli/mcp_config.json`
   * Goose: `~/.config/goose/config.yaml` (the `extensions` key)
   * Copilot CLI: `~/.copilot/mcp-config.json`
2. Lists every MCP server found and its direct command or URL.
3. Reports installed session telemetry hooks.

No files are written. No servers are contacted. No registration happens.

## Example

```bash
dev-library scan
```

Output:

```
Claude Code (~/.claude/settings.json)
  filesystem        npx @modelcontextprotocol/server-filesystem   not wrapped
  github            npx @modelcontextprotocol/server-github       not wrapped

Kiro (.kiro/settings/mcp.json)
  mcp-obsidian      mcp-obsidian                                  not wrapped

2 harness(s) found, 3 MCP server(s) total, 0 wrapped.
```

## Scoping to a single harness

```bash
dev-library scan --harness claude-code
```

## What to do next

Once you see what's installed, instrument it:

```bash
# Install session telemetry hooks across all harnesses
dev-library doctor patch --all-harnesses

# Or target a specific harness
dev-library doctor patch --harness kiro

# Preview changes without writing anything
dev-library doctor patch --all-harnesses --dry-run
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | At least one harness config found |
| 1 | Server unreachable / auth failed |
| 3 | No harness configs found |

## Related

* [`dev-library doctor patch`](doctor.md): instrument your harnesses (hooks, shims)
* [`dev-library agent pull`](pull.md): install a full agent (also wires up MCP servers)
* [`dev-library doctor`](doctor.md): diagnose instrumentation end-to-end
* [Use Cases -- Observe MCP traffic](../use-cases/observe-mcp-traffic.md): narrative walkthrough
