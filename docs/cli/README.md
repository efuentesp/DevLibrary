<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Naraen Rammoorthi <naraen13@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 tsitu0 <tomsitu0102@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Nithin-Bhargav-07 <gaddamnithinbhargav@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Overview

Complete reference for the `observal` CLI. Every subcommand has its own page; this overview is the index.

> **New to Observal?** Start with [Quickstart](../getting-started/quickstart.md) and come back here when you need a specific command.

## Command groups

| Command                                                                                    | What it does                                                                          |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| [`dev-library api`](api.md)                                                                   | Call authenticated JSON endpoints without a dedicated command                         |
| [`dev-library auth`](auth.md)                                                                 | Authentication and account management                                                 |
| [`dev-library config`](config.md)                                                             | Local CLI configuration, aliases                                                      |
| [`dev-library scan`](scan.md)                                                                 | Discover what's installed across your harnesses (read-only)                           |
| [`dev-library outdated`](outdated.md)                                                         | Compare installed agent and component versions with the active registry               |
| [`dev-library reconcile`](reconcile.md)                                                       | Backfill sessions missed by automatic telemetry delivery                              |
| [`dev-library inbox`](inbox.md)                                                               | Read and update the signed-in user's work and event feed                               |
| [`dev-library agent pull`](pull.md)                                                           | Install a published agent into a harness                                               |
| [`dev-library registry`](registry.md)                                                         | Publish and manage components (MCP / skill / hook / prompt / sandbox)                 |
| [`dev-library registry recommend`](recommend.md)                                              | Get personalized component recommendations                                            |
| [`dev-library registry version`](component.md)                                                | Publish and inspect component versions                                                |
| [`dev-library registry models`](models.md)                                                    | Inspect packaged harness model catalogs                                               |
| [`dev-library agent`](agent.md)                                                               | Create, install, and manage agents                                                     |
| [`dev-library team`](team.md)                                                                 | Manage teamspaces, members, join requests, and invitations                            |
| [`dev-library ops`](ops.md)                                                                   | Observability and operations (sessions, telemetry, logs, insights)                    |
| [`dev-library admin`](admin.md)                                                               | Core administration and submission review                                             |
| [`dev-library doctor support`](support.md)                                                   | Generate and inspect redacted diagnostic bundles                                      |
| [`dev-library doctor`](doctor.md)                                                             | Diagnose harness compatibility; `doctor patch` applies instrumentation                |
| [`dev-library server migrate`](https://github.com/Observal/Observal/blob/main/docs/cli/migrate.md) | Export/import PostgreSQL registry (shallow copy) and ClickHouse telemetry (deep copy) |
| [`dev-library self`](self.md)                                                                 | Upgrade or downgrade the CLI                                                          |
| [`dev-library registry prompt`](prompt.md)                                                    | Manage reusable prompts in the registry                                               |
| [`dev-library server`](server.md)                                                             | Manage the embedded server (start, stop, upgrade, rollback)                           |
| [`dev-library registry skill`](skill.md)                                                      | Submit, browse, and install portable skill packages                                   |

## Global options

Any subcommand accepts these.

| Option      | Short | Description                             |
| ----------- | ----- | --------------------------------------- |
| `--version` | `-V`  | Print the CLI version and exit          |
| `--verbose` | `-v`  | Verbose output                          |
| `--debug`   | -     | Debug-level logging (extremely verbose) |
| `--help`    | -     | Show help for any command or subcommand |

## JSON list contract

Every dedicated list command returns the same envelope:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 0
}
```

Paginated commands preserve server totals and requested pages. Unpaginated commands use page 1 and the returned item count as `page_size`. Detail and mutation commands return direct objects. `dev-library api` intentionally preserves raw endpoint JSON.

## Exit codes

Consistent across all commands:

| Code | Meaning                                      |
| ---- | -------------------------------------------- |
| 0    | Success                                      |
| 1    | Unexpected or uncategorized failure          |
| 2    | Usage error                                  |
| 3    | Authentication required or failed            |
| 4    | Permission denied                            |
| 5    | Resource not found                           |
| 6    | Conflict with current state                  |
| 7    | Validation failure                           |
| 8    | Rate limit reached                           |
| 9    | Network, service, or dependency unavailable  |
| 10   | CLI and server version mismatch              |

Errors identify the failed operation, resource, remediation, and server request ID when available. Internal details appear only with `--debug`.

When JSON output is selected, errors are written to stderr as one JSON object and stdout remains clean:

```json
{
  "error": {
    "category": "not_found",
    "message": "The requested resource was not found.",
    "operation": "Show agent",
    "resource": "agent registry",
    "remediation": "Check the identifier or list available agents.",
    "request_id": "01J...",
    "http_status": 404,
    "exit_code": 5
  }
}
```

## Non-interactive mode

For scripts and CI, pair flags with environment variables:

```bash
export OBSERVAL_SERVER_URL=https://observal.your-company.internal
export OBSERVAL_API_KEY=<your-key>

dev-library ops traces --limit 100 --output json | jq
```

Full env var reference: [Environment variables](../reference/environment-variables.md).

## Output formats

Read-heavy commands (`list`, `show`, `traces`, `spans`) support `--output`:

```bash
dev-library registry mcp list --output table    # default, TTY-friendly
dev-library registry mcp list --output json     # machine-readable
```

## Aliases

IDs get long fast. Create shortcuts:

```bash
dev-library config alias my-mcp 498c17ac-1234-4567-89ab-cdef01234567
dev-library registry mcp show @my-mcp
```

See [`dev-library config`](config.md) for details.

## Next

→ [`dev-library auth`](auth.md): you'll need to log in first.
