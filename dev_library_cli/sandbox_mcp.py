# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""DevLibrary Sandbox MCP Server.

A lightweight MCP server that exposes registered sandboxes as tools.
When an agent has sandbox components, this server is auto-injected into
the agent's MCP config - giving the agent a `run_sandbox` tool it can
call naturally without prompt engineering.

Usage:
    dev-library-sandbox-mcp --sandboxes '<json>'

The --sandboxes arg is a JSON array of sandbox specs:
    [{"id": "uuid", "name": "python-pytest", "image": "python:3.12-slim",
      "timeout": 60, "entrypoint": "pytest", "network_policy": "none"}]
"""

from __future__ import annotations

import json
import subprocess
import sys

# Minimal JSON-RPC stdio MCP implementation (no dependencies beyond stdlib)


def _read_message() -> dict | None:
    """Read a JSON-RPC message from stdin (Content-Length framing).

    Returns None on EOF or on any malformed frame: a long-lived MCP server
    must survive a corrupt message instead of dying mid-conversation.
    """
    try:
        headers = {}
        while True:
            line = sys.stdin.buffer.readline()
            if not line or line == b"\r\n" or line == b"\n":
                break
            if b":" in line:
                key, value = line.decode().split(":", 1)
                headers[key.strip().lower()] = value.strip()
        content_length = int(headers.get("content-length", 0))
        if content_length == 0:
            return None
        body = sys.stdin.buffer.read(content_length)
        return json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None


def _send_message(msg: dict) -> None:
    """Send a JSON-RPC message to stdout."""
    body = json.dumps(msg).encode()
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode())
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _make_response(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _make_error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _invoke_runner(req_id, argv: list[str], timeout_s: int) -> None:
    """Run dev-library-sandbox-run and answer the MCP request with its output."""
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        _send_message(
            _make_response(
                req_id,
                {"content": [{"type": "text", "text": output or "(no output)"}], "isError": result.returncode != 0},
            )
        )
    except subprocess.TimeoutExpired:
        _send_message(
            _make_response(
                req_id,
                {"content": [{"type": "text", "text": f"Sandbox timed out after {timeout_s}s"}], "isError": True},
            )
        )
    except FileNotFoundError:
        _send_message(
            _make_response(
                req_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": "dev-library-sandbox-run not found. Reinstall the CLI: pip install 'dev-library-cli'",
                        }
                    ],
                    "isError": True,
                },
            )
        )
    except Exception as e:
        _send_message(_make_response(req_id, {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}))


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sandboxes", required=True, help="JSON array of sandbox specs")
    args = parser.parse_args()

    try:
        sandboxes = json.loads(args.sandboxes)
    except json.JSONDecodeError:
        print(f"Invalid --sandboxes JSON argument: {args.sandboxes[:200]!r}", file=sys.stderr)
        sys.exit(2)

    # Build tool definitions + direct tool_name -> sandbox map
    tool_to_sandbox: dict[str, dict] = {}
    start_tool_to_sandbox: dict[str, dict] = {}
    tools = []
    for sb in sandboxes:
        tool_name = f"run_sandbox_{sb['name'].replace('-', '_')}"
        tool_to_sandbox[tool_name] = sb
        tools.append(
            {
                "name": tool_name,
                "description": (
                    f"Run a command in the '{sb['name']}' sandbox "
                    f"({sb.get('runtime_type', 'docker')}: {sb['image']}, timeout: {sb.get('timeout', 300)}s, "
                    f"network: {sb.get('network_policy', 'none')}). "
                    f"Default command: {sb.get('entrypoint', 'bash')}. "
                    "Pass session_id to execute inside a persistent session (shared filesystem between calls)"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": f"Command to run inside the container. Default: {sb.get('entrypoint', 'bash')}",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Execute inside this session (from sandbox_session_start_*) instead of a fresh ephemeral container",
                        },
                    },
                    "required": [],
                },
            }
        )
        start_name = f"sandbox_session_start_{sb['name'].replace('-', '_')}"
        start_tool_to_sandbox[start_name] = sb
        tools.append(
            {
                "name": start_name,
                "description": (
                    f"Start a persistent '{sb['name']}' session: a kept-alive container with a /workspace volume, "
                    "so consecutive calls with this session_id share filesystem state. Idle sessions stop after ~30 minutes"
                ),
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            }
        )

    # Session lifecycle tools are global: sessions are referenced by id.
    tools.extend(
        [
            {
                "name": "sandbox_session_stop",
                "description": "Stop a persistent sandbox session and delete its workspace volume",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Session id from sandbox_session_start_*"},
                        "keep_workspace": {
                            "type": "boolean",
                            "description": "Keep the workspace volume for a future session",
                        },
                    },
                    "required": ["session_id"],
                },
            },
            {
                "name": "sandbox_session_list",
                "description": "List active sandbox sessions with idle times",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "sandbox_file_read",
                "description": "Read a file from a sandbox session workspace",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "path": {
                            "type": "string",
                            "description": "Path inside the session container (e.g. /workspace/out.txt)",
                        },
                    },
                    "required": ["session_id", "path"],
                },
            },
            {
                "name": "sandbox_file_write",
                "description": "Write a file into a sandbox session workspace",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "path": {"type": "string", "description": "Path inside the session container"},
                        "content": {"type": "string"},
                    },
                    "required": ["session_id", "path", "content"],
                },
            },
        ]
    )

    while True:
        msg = _read_message()
        if msg is None:
            break

        method = msg.get("method", "")
        req_id = msg.get("id")

        if method == "initialize":
            _send_message(
                _make_response(
                    req_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "dev-library-sandbox", "version": "1.0.0"},
                    },
                )
            )
        elif method == "notifications/initialized":
            pass  # no response needed
        elif method == "tools/list":
            _send_message(_make_response(req_id, {"tools": tools}))
        elif method == "tools/call":
            params = msg.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            import os

            # ── Global session lifecycle tools ─────────────────────
            if tool_name == "sandbox_session_stop":
                session_id = str(arguments.get("session_id") or "")
                if not session_id:
                    _send_message(
                        _make_response(
                            req_id,
                            {"content": [{"type": "text", "text": "session_id is required"}], "isError": True},
                        )
                    )
                    continue
                argv = ["dev-library-sandbox-run", "--action", "stop", "--session-id", session_id]
                if arguments.get("keep_workspace"):
                    argv.append("--keep-workspace")
                _invoke_runner(req_id, argv, 60)
                continue
            if tool_name == "sandbox_session_list":
                _invoke_runner(req_id, ["dev-library-sandbox-run", "--action", "list"], 60)
                continue
            if tool_name == "sandbox_file_read":
                session_id = str(arguments.get("session_id") or "")
                path = str(arguments.get("path") or "")
                if not session_id or not path:
                    _send_message(
                        _make_response(
                            req_id,
                            {
                                "content": [{"type": "text", "text": "session_id and path are required"}],
                                "isError": True,
                            },
                        )
                    )
                    continue
                _invoke_runner(
                    req_id,
                    ["dev-library-sandbox-run", "--action", "files-get", "--session-id", session_id, "--path", path],
                    120,
                )
                continue
            if tool_name == "sandbox_file_write":
                session_id = str(arguments.get("session_id") or "")
                path = str(arguments.get("path") or "")
                content = arguments.get("content")
                if not session_id or not path or not isinstance(content, str):
                    _send_message(
                        _make_response(
                            req_id,
                            {
                                "content": [{"type": "text", "text": "session_id, path and content are required"}],
                                "isError": True,
                            },
                        )
                    )
                    continue
                _invoke_runner(
                    req_id,
                    [
                        "dev-library-sandbox-run",
                        "--action",
                        "files-put",
                        "--session-id",
                        session_id,
                        "--path",
                        path,
                        "--content",
                        content,
                    ],
                    120,
                )
                continue

            # ── Per-sandbox tools ───────────────────────────────────
            start_sb = start_tool_to_sandbox.get(tool_name)
            if start_sb:
                env_args: list[str] = []
                for entry in start_sb.get("env_vars", []) or []:
                    if "=" in entry:
                        env_args.extend(["--env", entry])
                    elif os.environ.get(entry):
                        env_args.extend(["--env", f"{entry}={os.environ[entry]}"])
                argv = [
                    "dev-library-sandbox-run",
                    "--action",
                    "start",
                    "--sandbox-id",
                    start_sb["id"],
                    "--image",
                    start_sb["image"],
                    "--runtime-type",
                    start_sb.get("runtime_type", "docker"),
                    "--network-policy",
                    start_sb.get("network_policy", "none"),
                    "--resource-limits",
                    json.dumps(start_sb.get("resource_limits", {}) or {}),
                    "--runtime-config",
                    json.dumps(start_sb.get("runtime_config", {}) or {}),
                ]
                argv.extend(env_args)
                for mount in start_sb.get("allowed_mounts", []) or []:
                    argv.extend(["--mount", mount])
                _invoke_runner(req_id, argv, 120)
                continue

            sb = tool_to_sandbox.get(tool_name)
            if not sb:
                _send_message(
                    _make_response(
                        req_id,
                        {
                            "content": [{"type": "text", "text": f"Unknown sandbox tool: {tool_name}"}],
                            "isError": True,
                        },
                    )
                )
                continue

            command = arguments.get("command") or sb.get("entrypoint") or "bash"
            timeout = sb.get("timeout", 300)
            session_id = str(arguments.get("session_id") or "")

            # Session-scoped execution: reuse a kept-alive container.
            if session_id:
                _invoke_runner(
                    req_id,
                    [
                        "dev-library-sandbox-run",
                        "--action",
                        "exec",
                        "--session-id",
                        session_id,
                        "--command",
                        command,
                        "--timeout",
                        str(timeout),
                    ],
                    timeout + 10,
                )
                continue

            # Ephemeral execution (original behavior).
            image = sb["image"]
            sandbox_id = sb["id"]
            runtime_type = sb.get("runtime_type", "docker")
            resource_limits = sb.get("resource_limits", {}) or {}
            network_policy = sb.get("network_policy", "none")
            runtime_config = sb.get("runtime_config", {}) or {}
            env_vars = sb.get("env_vars", []) or []
            allowed_mounts = sb.get("allowed_mounts", []) or []

            # Author-declared env entries: "KEY=value" is literal, a bare "KEY"
            # passes the harness environment value through (skipped when unset).
            env_args = []
            for entry in env_vars:
                if "=" in entry:
                    env_args.extend(["--env", entry])
                elif os.environ.get(entry):
                    env_args.extend(["--env", f"{entry}={os.environ[entry]}"])

            argv = [
                "dev-library-sandbox-run",
                "--sandbox-id",
                sandbox_id,
                "--image",
                image,
                "--runtime-type",
                runtime_type,
                "--timeout",
                str(timeout),
                "--network-policy",
                network_policy,
                "--resource-limits",
                json.dumps(resource_limits),
                "--runtime-config",
                json.dumps(runtime_config),
            ]
            argv.extend(env_args)
            for mount in allowed_mounts:
                argv.extend(["--mount", mount])
            argv.extend(["--command", command])
            _invoke_runner(req_id, argv, timeout + 10)
        elif req_id is not None:
            _send_message(_make_error(req_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    main()
