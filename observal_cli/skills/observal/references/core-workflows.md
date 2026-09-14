<!-- SPDX-FileCopyrightText: 2026 DevLibrary Contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Core workflows

## Contents

- Authentication and account
- CLI configuration
- Local inventory and update checks
- Diagnosis and telemetry setup
- Inbox
- API escape hatch
- Error handling

## Authentication and account

Do not run an authentication probe before every command. Execute the requested read operation first. If authentication fails, inspect identity and then log in.

```bash
dev-library auth whoami --output json
dev-library auth login
dev-library auth login --sso --output json
dev-library auth logout --output json
dev-library auth status --output json
dev-library auth set-username new-handle --output json
```

For noninteractive password authentication, keep passwords out of arguments:

```bash
DEVLIBRARY_PASSWORD_FILE=/path/to/password dev-library auth login --server https://observal.example.com --email me@example.com --name 'Example User' --output json
OBSERVAL_CURRENT_PASSWORD_FILE=/path/to/current DEVLIBRARY_NEW_PASSWORD_FILE=/path/to/new dev-library auth change-password --output json
```

Fresh-server JSON bootstrap can require `--name`. SSO JSON emits an authorization event followed by an authenticated event. A username becomes the Registry namespace and can become immutable after ownership is established.

At every CLI startup, bundled DevLibrary skill trees are hash-checked against the packaged copies. Drift causes complete replacement of only the six DevLibrary-managed skill directories, including stale extra files.

## CLI configuration

```bash
dev-library config show --output json
dev-library config path --output json
dev-library config set server_url https://observal.example.com --output json
dev-library config set timeout 60 --output json
dev-library config aliases --output json
dev-library config alias MY_AGENT namespace/slug --output json
```

Only use keys accepted by `config set`. Authentication fields are managed by `auth`. Config output must not contain token values or fragments.

## Local inventory and update checks

`scan` is read-only and never writes harness files.

```bash
dev-library scan --output json
dev-library scan --harness kiro --output json
dev-library outdated --output json
dev-library outdated --harness claude-code --no-report --output json
```

For scan results, report detected harnesses, installed components, Agents, and unregistered items. For outdated results, inspect `items`, `summary`, and `report`. `--no-report` suppresses inbox reporting, not the Registry check.

## Diagnosis and telemetry setup

Diagnosis does not mutate unless the user explicitly requests a fix option.

```bash
dev-library doctor --output json
dev-library doctor patch --all-harnesses --dry-run --output json
dev-library doctor patch --all-harnesses --output json
dev-library doctor patch --harness kiro --output json
dev-library doctor cleanup --dry-run --output json
dev-library doctor cleanup --yes --output json
```

Patch requires at least one harness or `--all-harnesses`. Cleanup removes only DevLibrary-managed artifacts. JSON cleanup requires confirmation. For Pi, patch installs the bundled extension directly.

Support bundles are sensitive diagnostic artifacts:

```bash
dev-library doctor support bundle --file /tmp/observal-support.tar.gz --output json
dev-library doctor support inspect /tmp/observal-support.tar.gz --output json
```

Verify `healthy`, `issues`, `warnings`, and per-harness results. Exit status zero means checks ran, not necessarily that every check is healthy.

## Inbox

```bash
dev-library inbox count --output json
dev-library inbox list --state open --action-required --output json
dev-library inbox show ITEM_UUID --output json
dev-library inbox read ITEM_UUID --output json
dev-library inbox done ITEM_UUID --output json
dev-library inbox dismiss ITEM_UUID --output json
dev-library inbox reopen ITEM_UUID --output json
dev-library inbox read-all --kind update_available --yes --output json
```

Use item UUIDs from JSON. Reading does not resolve an item. Confirm an `action_command` against the user's request before executing it. `read-all` affects every item matching its filters.

## API escape hatch

Use only when no dedicated command exists. It preserves raw endpoint JSON and uses configured authentication.

```bash
dev-library api GET /api/v1/teams --output json
dev-library api GET /api/v1/agents --param limit=10 --output json
dev-library api POST /api/v1/teams --from-file team.json --output json
```

Mutation bodies come from one JSON object in a file or standard input. Full URLs and arbitrary authorization headers are rejected. Prefer dedicated commands for validation and confirmations.

## Error handling

- Authentication: run `auth whoami`, then login only when needed.
- Permission: report the role or ownership requirement.
- Not found: re-list and use the returned UUID or canonical name.
- Conflict: inspect current state and server detail before choosing an action.
- Version mismatch: use `observal-advanced` for CLI version recovery.
- Unavailable or not configured: stop. Use explicit local fallback only if the user requests it after the failure.
