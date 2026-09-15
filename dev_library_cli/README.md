<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Observal CLI

Command-line interface for the Observal platform. Authenticate with a server, manage registry components, configure harnesses, and collect telemetry.

## Install

The CLI is packaged as a Python project. From the repo root:

```bash
uv pip install -e .
```

This installs three entry points:

| Command                | Purpose                                  |
| ---------------------- | ---------------------------------------- |
| `observal`             | Main CLI                                 |
| `dev-library-sandbox-run` | Sandbox execution runner                 |
| `dev-library-sandbox-mcp` | MCP interface for configured sandboxes   |

## Quick Start

```bash
dev-library auth login                  # connect to your Observal server
dev-library scan                        # discover what's installed across your harnesses (read-only)
dev-library doctor patch --all-harnesses        # install session telemetry hooks
dev-library agent pull my-agent --harness cursor  # fetch agent config for Cursor
dev-library doctor                      # check harness compatibility
```

## Commands

### Authentication

```
dev-library auth login       # connect to server (initializes admin on first run)
dev-library auth register    # create a new account
dev-library auth logout      # clear saved credentials
dev-library auth whoami      # show current user
dev-library auth status      # check connectivity and buffer status
```

### Agent Workflow

```
dev-library agent init              # scaffold dev-library-agent.yaml
dev-library agent add mcp <id>      # add a component to the agent definition
dev-library agent build             # validate the definition
dev-library agent publish           # push to the server
dev-library agent list              # list active agents
dev-library agent show <id>         # show agent details
dev-library agent install <id> --harness <harness>  # get harness config snippet
```

### Component Registry

Each component type (mcp, skill, hook, prompt, sandbox) shares the same subcommand pattern:

```
dev-library registry <type> submit      # submit for review
dev-library registry <type> list        # list approved items
dev-library registry <type> show <id>   # show details
dev-library registry <type> install <id> --harness <harness>  # get harness config
```

Hooks have an extra `sync` subcommand. Prompts have an extra `render` subcommand for variable substitution.

### Operations

```
dev-library ops telemetry status --output json       # check telemetry flow
dev-library ops top --type agent --output json        # most-downloaded agents
dev-library ops traces --output json                   # current session summaries
dev-library ops traces --span --output json            # current session details
dev-library ops insights list <agent> --output json    # agent insight reports
```

### Administration

```
dev-library admin diagnostics --output json             # server health
dev-library admin users --output json                   # user management
dev-library admin security-events --output json         # security events
dev-library admin audit-log --output json               # compliance audit events
dev-library admin review list --output json             # pending submissions
```

### Utilities

```
dev-library agent pull <agent> --harness <harness>             # write agent config to harness files
dev-library scan [--harness <harness>]                          # discover what's installed (read-only)
dev-library reconcile --dry-run --output json                    # preview recoverable sessions
dev-library doctor patch --all-harnesses --output json         # install hooks for every harness
dev-library doctor patch --harness <harness> --output json      # install hooks for a specific harness
observal use <profile>                               # swap harness config from a profile
dev-library doctor --output json                        # diagnose harness/Observal issues
dev-library doctor support bundle --output json         # create a redacted support archive
dev-library config show                                 # show current config
```

## Supported harnesses

| harness / Tool | Support Level |
| --------------------------- | ---------------------------- |
| Claude Code | Fully supported |
| Kiro CLI | Supported (next most tested) |
| Cursor, VS Code | Untested |

The `--harness` flag controls which config format is generated. Each harness has its own config paths and JSON structure.

## Config Files

All CLI state lives in `~/.observal/`:

| File                     | Contents                                  |
| ------------------------ | ----------------------------------------- |
| `config.json`            | Server URL, tokens, user ID               |
| `aliases.json`           | User-defined name-to-UUID aliases         |
| `last_results.json`      | Cached list results for numeric shorthand |

## Telemetry

Hook scripts in `dev_library_cli/hooks/` locate local harness session transcripts and deliver new JSONL records to the session ingest endpoint. `dev-library reconcile` recovers records that were not delivered during the original hook run. MCP commands and remote URLs are left unchanged.

## Directory Layout

```
dev_library_cli/
├── main.py                  # Root app, command registration
├── config.py                # Config file I/O
├── client.py                # HTTP client with auth and token refresh
├── constants.py             # Valid harnesses, categories, component types
├── render.py                # Rich output formatting
├── analyzer.py              # Repo analysis for MCP submission
├── settings_reconciler.py   # Non-destructive Claude Code settings merge
├── cmd_auth.py              # Auth commands
├── cmd_agent.py             # Agent commands
├── cmd_mcp.py               # MCP commands
├── cmd_skill.py             # Skill commands
├── cmd_hook.py              # Hook commands
├── cmd_prompt.py            # Prompt commands
├── cmd_sandbox.py           # Sandbox commands
├── cmd_pull.py              # Pull command
├── cmd_scan.py              # Scan command
├── cmd_doctor.py            # Doctor command
├── cmd_ops.py               # Operations commands
├── cmd_profile.py           # Profile swapping
├── sandbox_runner.py        # dev-library-sandbox-run entrypoint
└── hooks/                   # Telemetry hook scripts
```
