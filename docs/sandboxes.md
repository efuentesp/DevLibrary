<!-- SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Sandboxes

Sandboxes are versioned execution environments registered in Observal. When an agent has a sandbox component, Observal installs an `dev-library-sandbox` MCP server that exposes one callable tool per sandbox.

## Runtime support

| Runtime | Artifact field | Local requirement | Notes |
| --------- | ---------------- | ------------------- | ------- |
| `docker` | `image` | Docker daemon + Python Docker SDK | Supports any Docker/OCI image the local daemon can pull and run, for example `python:3.12-slim` or `ghcr.io/org/runner:1.0.0`. |
| `lxc` | `image` | local `lxc`/LXD CLI | Uses LXC/LXD image refs, not arbitrary OCI image refs. |
| `firecracker` | `runtime_config` | local `firecracker` binary | Requires `runtime_config.config_path` or `kernel_image_path` + `rootfs_path`. |
| `wasm` | `image` or `runtime_config.module` | local `wasmtime` or configured WASI runtime | Runs a WASI module, not a container image. |

Docker is the common path. The other runtimes are local-runtime dispatchers: Observal stores and installs the metadata, but the developer machine must have the corresponding runtime and artifact already available.

## Versioned fields

A sandbox version stores:

| Field | Description |
| ------- | ------------- |
| `runtime_type` | `docker`, `lxc`, `firecracker`, or `wasm` |
| `image` | Docker/OCI image, LXC image ref, or WASM module path/ref |
| `resource_limits` | JSON object such as `{"timeout": 60, "memory_mb": 512, "cpu_count": 1}` |
| `network_policy` | `none`, `host`, `bridge`, or `restricted` |
| `entrypoint` | Default command when the agent does not pass one |
| `runtime_config` | Runtime-specific JSON for Firecracker/WASM/LXC extras |
| `source_url`, `source_ref`, `sandbox_path` | Source metadata for humans/reviewers |

`source_url` + `source_ref` + `sandbox_path` can point at a Dockerfile or sandbox source tree, but Observal does not build or publish images from that path today. Publish a built image/artifact ref in `image`.

Local OCI setup example:

```bash
git clone https://github.com/acme/agent-sandboxes
cd agent-sandboxes/sandboxes/python-pytest
docker build -t ghcr.io/acme/python-pytest:1.0.0 .
```

Then submit:

```json
{
  "runtime_type": "docker",
  "image": "ghcr.io/acme/python-pytest:1.0.0",
  "source_url": "https://github.com/acme/agent-sandboxes",
  "source_ref": "main",
  "sandbox_path": "sandboxes/python-pytest"
}
```

## How it works

```text
dev-library agent pull my-agent --harness claude-code
    │
    ├── Registers "dev-library-sandbox" MCP server
    │   └── Exposes run_sandbox_<name> as a callable tool
    │
    └── Agent calls run_sandbox_python_pytest(command="pytest tests/")
        └── MCP server → dev-library-sandbox-run → local runtime → output
```

## Submit a sandbox

```bash
dev-library registry sandbox submit \
  --name python-pytest \
  --version 1.0.0 \
  --description "Run Python tests" \
  --runtime-type docker \
  --image python:3.12-slim \
  --resource-limits '{"timeout":60,"memory_mb":512}' \
  --entrypoint "pytest" \
  --output json
```

Sandbox submission returns the direct server result in JSON mode. Standalone Sandbox installation is not supported. Add the returned sandbox UUID to an agent with `dev-library agent add sandbox <sandbox-uuid>`.

From JSON:

```json
{
  "name": "python-pytest",
  "version": "1.0.0",
  "description": "Run Python tests in an isolated container",
  "owner": "your-name",
  "runtime_type": "docker",
  "image": "python:3.12-slim",
  "resource_limits": {"timeout": 60, "memory_mb": 512},
  "network_policy": "none",
  "entrypoint": "pytest"
}
```

## Publish a new sandbox version

```bash
dev-library registry version publish sandbox python-pytest \
  --version 1.1.0 \
  --description "Move to Python 3.12 slim" \
  --extra '{"runtime_type":"docker","image":"python:3.12-slim","resource_limits":{"timeout":60}}'
```

Like skills and MCPs, a new sandbox version is submitted for review. Approval moves the listing's `latest_version_id` to the approved version; older versions remain available for agents that pinned them.

## Manual runner examples

Docker:

```bash
dev-library-sandbox-run \
  --sandbox-id s-123 \
  --runtime-type docker \
  --image python:3.12-slim \
  --timeout 60 \
  --network-policy none \
  --command "python -c 'print(42)'"
```

WASM:

```bash
dev-library-sandbox-run \
  --sandbox-id s-123 \
  --runtime-type wasm \
  --image ./runner.wasm \
  --command "--help"
```

## Persistent sessions

Ephemeral runs lose all state between calls. Sessions keep a container alive
so consecutive commands share filesystem state:

```text
sandbox_session_start_python_pytest()   → session_id (container + /workspace volume)
run_sandbox_python_pytest(command="pytest -q", session_id="…")
sandbox_file_write(session_id, "src/main.py", content)
sandbox_file_read(session_id, "out/report.txt")
sandbox_session_stop(session_id)          → removes container and workspace
```

- Sessions survive MCP and harness restarts (registry in
  `~/.observal/sandbox_sessions.json`).
- Idle sessions are garbage collected automatically (~30 min default;
  override with `OBSERVAL_SANDBOX_SESSION_TTL` seconds).
- `sandbox_session_stop(session_id, keep_workspace=true)` keeps the volume
  for a future session.
- Docker runtime only; session exec emits the same telemetry as ephemeral runs.
- Manual runner access: `dev-library-sandbox-run --action start|exec|stop|list|files-get|files-put|gc`.

## Security notes

- Docker `network_policy: "none"` maps to Docker's no-network mode.
- `network_policy: "restricted"` is real egress control: the runner starts a
  loopback allowlist proxy, attaches the container to a dedicated bridge
  network, and routes HTTP(S) through `host.docker.internal`. Only hosts in
  `runtime_config.egress_allowlist` (exact or subdomain match) are reachable;
  an empty allowlist means total isolation. Restricted **sessions** use a
  dedicated internal network without the proxy — the proxy spans a single
  ephemeral run only, and the runner says so on stderr instead of silently
  claiming egress control.
- Docker `memory_mb` and `cpu_count` are passed to the local Docker daemon.
- Non-Docker isolation is only as strong as the local runtime configuration.
- No registry-side Dockerfile build service exists yet; use prebuilt image/artifact refs.

## Telemetry

Every `dev-library-sandbox-run` invocation reports one event to
`POST /api/v1/ingest/sandbox-exec` (exit code, OOM kill, timeout, latency,
 container id, 4KB output preview). Delivery is best-effort with a local
spool (`~/.observal/sandbox_spans.jsonl`) that retries on the next
execution when the server is unreachable; executions never block on
telemetry. Events land in the ClickHouse `sandbox_exec_events` table with
the authenticated user stamped server-side.
