<!-- SPDX-FileCopyrightText: 2026 Edgar F. Fuentes Perea <efuentesp@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Submitting a Workflow

A workflow is a single self-contained JavaScript file that deterministic harness
workflow runtimes execute. Today pi is the supported harness: install writes
the script to `.pi/workflows/{name}.js` (project scope) or
`~/.pi/agent/workflows/{name}.js` (user scope).

## What a workflow is

- **One `.js` file.** No imports, no filesystem access, no network at submit
  time. The script runs in a sandboxed interpreter; the runtime injects
  helpers (`agent`, `shell`, `parallel`, `log`) and `args`.
- **Deterministic orchestration.** The script decides control flow and any
  consensus math itself. Decisions that must be reproducible never belong in
  an LLM prompt.
- **Versioned by the registry.** The whole script body is stored on each
  version; edits publish a new version.

## Submitting

```bash
dev-library registry workflow submit \
  --script-file cosmic-sizing.js \
  --name cosmic-sizing \
  --description "Deterministic COSMIC sizing pipeline" \
  --team solution-design
```

Or from a JSON file:

```json
{
  "name": "cosmic-sizing",
  "version": "1.0.0",
  "description": "Deterministic COSMIC sizing pipeline",
  "owner": "solution-design",
  "script_file": "cosmic-sizing.js",
  "supported_harnesses": ["pi"]
}
```

`script_file` is read client-side and sent as `script_content`; the server
never fetches anything.

## Installing

```bash
dev-library registry workflow install solution-design/cosmic-sizing --harness pi
dev-library registry workflow install solution-design/cosmic-sizing -i pi --scope user
```

`--no-write` previews the resolved path without writing.

## Harness support

Workflow install paths come from the harness registry. Only harnesses that
declare the `workflows` capability accept installs; others answer a clean
400. Adding a harness means adding its `workflows` paths to the shared
registry, nothing else.
