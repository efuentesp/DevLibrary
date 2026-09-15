<!-- SPDX-FileCopyrightText: 2026 DevLibrary Contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Discovery and installation

## Contents

- Search and inspect
- Personalized recommendations
- Install components
- Verification

## Search and inspect

Start broad with natural-language search, then narrow only when needed.

```bash
dev-library registry mcp list --search 'github docker' --output json
dev-library registry mcp list --category developer-tools --output json
dev-library registry skill list --search 'frontend design' --harness claude-code --output json
dev-library registry skill list --team platform-tools --output json
dev-library registry hook list --event UserPromptSubmit --output json
dev-library registry prompt list --category code-generation --output json
dev-library registry sandbox list --runtime docker --output json
dev-library registry models --harness kiro --output json
```

Summarize matches by `qualified_name`, description, version, supported harnesses, and why they match the request. If no result appears, retry once with fewer keywords.

Inspect a selected component with its canonical identity:

```bash
dev-library registry mcp show NAMESPACE/SLUG --output json
dev-library registry skill show NAMESPACE/SLUG --output json
dev-library registry hook show NAMESPACE/SLUG --output json
dev-library registry prompt show NAMESPACE/SLUG --output json
dev-library registry sandbox show NAMESPACE/SLUG --output json
```

## Trying a sandbox locally

`registry sandbox run` executes a registered sandbox through the same local runner an installed agent uses — no agent or harness required. Requires the matching local runtime (a Docker daemon for docker sandboxes). Exit code mirrors the container.

```bash
dev-library registry sandbox run python-pytest                      # runs the registered entrypoint
dev-library registry sandbox run python-pytest -- pytest -q tests/   # explicit command after --
dev-library registry sandbox run @env --timeout 120 --env API_TOKEN   # bare KEY resolves from the shell, skipped when unset
```

Registered `env_vars` and `allowed_mounts` apply automatically; `--timeout` and `--network-policy` override the registered values for this run.

## Personalized recommendations

Use recommendations for open-ended requests such as "what should I install?" or "what am I missing?"

```bash
dev-library registry recommend --output json
dev-library registry recommend --limit 12 --type mcp --refresh --output json
```

Interpret fields precisely:

- `personalized: true`: ranked from this user's sessions.
- `personalized: false`: popularity fallback because no usable personal profile exists.
- Low `profile_sessions`: answer, but say evidence is thin.
- Empty `items`: successful result, not an error.
- `items[].reason`: quote or summarize this reason without inventing another.

Dismiss only after user confirmation because the preference is durable:

```bash
dev-library registry recommend dismiss skill NAMESPACE/SLUG --action not_relevant --output json
```

## Install components

Choose the exact harness and scope before writing files.

```bash
dev-library registry mcp install NAMESPACE/SLUG --harness kiro --no-prompt --output json
dev-library registry mcp install NAMESPACE/SLUG --harness cursor --version 2.1.0 --no-prompt --output json
dev-library registry skill install NAMESPACE/SLUG --harness claude-code --scope project --output json
dev-library registry skill install NAMESPACE/SLUG --harness kiro --scope user --version 1.2.0 --output json
dev-library registry hook install NAMESPACE/SLUG --harness kiro --output json
dev-library registry hook install NAMESPACE/SLUG --harness claude-code --platform darwin --dir . --output json
```

Use raw output only when the user explicitly asks for a config snippet or raw response:

```bash
dev-library registry mcp install NAMESPACE/SLUG --harness claude-code --raw
```

Never combine raw and JSON modes. Never print supplied environment or header values.

## Verification

Inspect returned files, setup instructions, warnings, and version. For harness writes, verify with:

```bash
dev-library scan --harness kiro --output json
```

If installation reports a failed setup command or file write, report partial failure rather than success.
