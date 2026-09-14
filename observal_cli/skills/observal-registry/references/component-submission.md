<!-- SPDX-FileCopyrightText: 2026 DevLibrary Contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Component submission

## Contents

- Common workflow
- Mixed bulk submission
- MCP server
- Skill
- Hook
- Prompt
- Sandbox
- Drafts and review status

Submit only content the user owns or is authorized to publish. Use `--team TEAM_HANDLE --visibility team` for private teamspace ownership, or `--visibility public` for reviewable public content.

## Common workflow

1. Run the leaf command's help and validate required fields.
2. Prefer a prepared file for structured or long content when supported.
3. Submit in JSON mode.
4. Capture UUID, `qualified_name`, version, and status.
5. Verify with `show` or the owner's list. Pending is not approved.

## Mixed bulk submission

Use one typed JSON file for up to 200 mixed components. Dry run performs local structural validation. Execution requires confirmation in JSON mode.

```bash
dev-library registry bulk submit --from-file components.json --dry-run --output json
dev-library registry bulk submit --from-file components.json --yes --output json
```

Each entry contains `type` plus the normal API submission fields. Supported types are `mcp`, `skill`, `hook`, `prompt`, and `sandbox`. Inspect `submitted`, `skipped`, `errors`, and every result. Authentication and service failures stop the batch. After an uncertain failure, verify by UUID or `qualified_name` before rerunning.

## MCP server

`mcp submit` reads MCP JSON from standard input. It does not support `--from-file`.

```bash
printf '%s\n' '{"command":"npx","args":["-y","@example/mcp-server"]}' | dev-library registry mcp submit --name my-mcp --category developer-tools --yes --output json
dev-library registry mcp submit --git https://github.com/org/mcp-server --name my-mcp --category developer-tools --yes --output json
printf '%s\n' '{"command":"npx","args":["internal-mcp"]}' | dev-library registry mcp submit --name internal-mcp --category developer-tools --team platform-tools --visibility team --yes --output json
```

If the response includes setup instructions, report them as required follow-up. Do not invent wrappers or telemetry environment variables.

## Skill

Git delivery is preferred for public multi-file skills:

```bash
dev-library registry skill submit --skill-md ./SKILL.md --git-url https://github.com/org/repo --git-ref main --name my-skill --description 'What it does' --task-type general --output json
```

Registry-direct delivery stores the supplied SKILL.md and optional script:

```bash
dev-library registry skill submit --skill-md ./SKILL.md --delivery-mode registry_direct --name my-skill --description 'What it does' --task-type general --harness claude-code --output json
dev-library registry skill submit --skill-md ./SKILL.md --script ./run.sh --delivery-mode registry_direct --name my-skill --description 'What it does' --task-type general --output json
```

Multi-file skills carry scripts, templates, and other resources. `--from-dir`
packages a whole skill directory (SKILL.md plus every resource, ignoring
`.git`, caches, and OS noise); `--extra-file` adds individual files (repeatable,
paths relative to the SKILL.md directory, or `dest=path` for files elsewhere;
binary files are stored base64). Caps: 100 files, 2 MB each, 8 MB total.

```bash
dev-library registry skill submit --from-dir ./my-skill --delivery-mode registry_direct --name my-skill --description 'What it does' --task-type general --output json
dev-library registry skill submit --skill-md ./SKILL.md --extra-file ./templates/x.md --extra-file 'assets/logo.png=/tmp/logo.png' --delivery-mode registry_direct --name my-skill --description 'What it does' --task-type general --output json
```

Choose one delivery mode deliberately. Verify installed paths and script metadata after approval.

## Hook

```bash
dev-library registry hook submit --name guard --description 'Guard prompts' --event UserPromptSubmit --handler-command './guard.sh' --execution-mode sync --timeout 10 --scope agent --harness claude-code --output json
dev-library registry hook submit --from-file hook.json --output json
```

Valid execution modes and limits are server-defined. If uncertain, read help before submission. Blocking behavior is fragile, so preserve the requested event, timeout, scope, and harness exactly.

## Prompt

```bash
dev-library registry prompt submit --name frontend-brief --description 'Frontend design brief' --category general --template 'Design {{component}} accessibly' --output json
dev-library registry prompt submit --from-file prompt.json --output json
```

Keep template variables intact and verify the stored template with `prompt show` or `prompt render`.

## Sandbox

```bash
dev-library registry sandbox submit --name node-runner --description 'Node sandbox' --runtime-type docker --image node:22-alpine --resource-limits '{"memory_mb":512}' --runtime-config '{}' --network-policy none --entrypoint node --harness claude-code --output json
dev-library registry sandbox submit --from-file sandbox.json --output json
```

Treat runtime, image, network policy, limits, entrypoint, and harness support as security-relevant fields. Do not weaken them silently.

## Drafts and review status

Submission commands support draft workflows where documented. Use local help for the exact leaf:

```bash
dev-library registry skill submit --skill-md ./SKILL.md --delivery-mode registry_direct --name my-skill --description 'What it does' --task-type general --draft --output json
dev-library registry skill submit --submit NAMESPACE/SLUG --output json
```

After any submit, report whether the item is draft, pending, approved, rejected, or archived. Never collapse pending into published.
