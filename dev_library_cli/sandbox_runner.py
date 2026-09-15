# SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com>
# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-FileCopyrightText: 2026 Santhosh Raja <santhoshpkraja2004@gmail.com>
# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""observal-sandbox-run: local sandbox executor."""

from __future__ import annotations

import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

from dev_library_cli.config import load as load_config

MAX_LOG_BYTES = 64 * 1024  # 64KB truncation limit for logs


def _int_or(value, default: int = 0) -> int:
    """Best-effort int coercion for externally sourced values."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _send_span(server_url: str, access_token: str, span: dict):
    """Deliver execution telemetry through the spooling sender; never raises."""
    try:
        from dev_library_cli.sandbox_telemetry import send_and_spool

        send_and_spool([span], server_url=server_url or None, access_token=access_token or None)
    except Exception:
        pass


def _exec_span(
    *,
    sandbox_id: str,
    image: str,
    command: str | None,
    runtime_type: str,
    exit_code: int,
    status: str,
    start_time: str,
    latency_ms: int,
    output: str,
    container_id: str | None = None,
    oom_killed: bool = False,
    timed_out: bool = False,
) -> dict:
    """Build one event matching the /api/v1/ingest/sandbox-exec contract."""
    import os

    return {
        "sandbox_id": sandbox_id,
        "image": image,
        "runtime_type": runtime_type,
        "command": (command or "")[:512],
        "exit_code": exit_code,
        "oom_killed": oom_killed,
        "timed_out": timed_out,
        "status": status,
        "latency_ms": latency_ms,
        "container_id": container_id,
        "agent_id": os.environ.get("OBSERVAL_AGENT_ID") or None,
        "session_id": os.environ.get("OBSERVAL_SESSION_ID") or None,
        "harness": os.environ.get("OBSERVAL_HARNESS", ""),
        "output": output,
        "start_time": start_time,
        "end_time": _now_iso(),
    }


def _truncate(text: str) -> str:
    return text[:MAX_LOG_BYTES] + "\n... [truncated at 64KB]" if len(text) > MAX_LOG_BYTES else text


def _missing_runtime(name: str) -> NoReturn:
    print(f"local-runtime-missing: {name} is not installed or not on PATH", file=sys.stderr)
    sys.exit(127)


def _require_bin(name: str) -> str:
    path = shutil.which(name)
    if not path:
        _missing_runtime(name)
    return path


def _run_subprocess(argv: list[str], timeout: int) -> None:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    output = _truncate((result.stdout or "") + (f"\n[stderr]\n{result.stderr}" if result.stderr else ""))
    print(output, end="")
    sys.exit(result.returncode)


def _docker_run(
    sandbox_id: str,
    image: str,
    command: str | None,
    timeout: int,
    env: dict | None,
    network_policy: str,
    resource_limits: dict,
    mounts: list[str] | None = None,
    runtime_config: dict | None = None,
):
    try:
        import docker
    except ImportError:
        print(
            "local-runtime-missing: Docker SDK not found. Reinstall the CLI: pip install 'dev-library-cli'",
            file=sys.stderr,
        )
        sys.exit(127)

    from requests.exceptions import RequestException  # docker-py transport errors for container.wait deadlines

    client = docker.from_env()
    start_time = _now_iso()
    wall_start = time.monotonic()
    container = None
    proxy = None
    restricted_network = None
    try:
        run_kwargs = {
            "image": image,
            "detach": True,
            "environment": env or {},
            "stdout": True,
            "stderr": True,
        }
        if command:
            run_kwargs["command"] = command
        if network_policy in {"none", "host", "bridge"}:
            run_kwargs["network_mode"] = network_policy
        elif network_policy == "restricted":
            allowlist = [str(host) for host in (runtime_config or {}).get("egress_allowlist") or []]
            if allowlist:
                # Real egress control: dedicated bridge network plus a loopback
                # allowlist proxy the container reaches via host.docker.internal.
                from dev_library_cli.sandbox_proxy import RestrictedProxy

                proxy = RestrictedProxy(allowlist)
                proxy.start()
                restricted_network = client.networks.create(f"observal-sbx-{uuid.uuid4().hex[:8]}", driver="bridge")
                run_kwargs["network"] = restricted_network.name
                run_kwargs["extra_hosts"] = {"host.docker.internal": "host-gateway"}
                proxy_url = f"http://host.docker.internal:{proxy.port}"
                env = dict(env or {})
                env.setdefault("HTTP_PROXY", proxy_url)
                env.setdefault("HTTPS_PROXY", proxy_url)
                env.setdefault("NO_PROXY", "localhost,127.0.0.1")
                run_kwargs["environment"] = env
            else:
                # No allowlist declared: total isolation is the only honest default.
                run_kwargs["network_mode"] = "none"
        if resource_limits.get("memory_mb"):
            run_kwargs["mem_limit"] = f"{int(resource_limits['memory_mb'])}m"
        if resource_limits.get("cpu_count"):
            run_kwargs["nano_cpus"] = int(float(resource_limits["cpu_count"]) * 1_000_000_000)
        if mounts:
            # Docker accepts "host_path:container_path[:ro|:rw]" bind specs directly.
            run_kwargs["volumes"] = mounts

        container = client.containers.run(**run_kwargs)
        try:
            result = container.wait(timeout=timeout)
        except RequestException:
            # docker-py surfaces container.wait() deadlines as requests transport
            # errors. Only report a timeout when the container actually outlived
            # the deadline; otherwise let the generic handler report the failure.
            container.reload()
            if container.attrs.get("State", {}).get("Running"):
                wall_ms = int((time.monotonic() - wall_start) * 1000)
                container_id = container.short_id
                access_token = os.environ.get("OBSERVAL_KEY", "")
                server_url = os.environ.get("OBSERVAL_SERVER", "")
                if not access_token or not server_url:
                    cfg = load_config()
                    access_token = access_token or cfg.get("access_token", "")
                    server_url = server_url or cfg.get("server_url", "")
                _send_span(
                    server_url,
                    access_token,
                    _exec_span(
                        sandbox_id=sandbox_id,
                        image=image,
                        command=command,
                        runtime_type="docker",
                        exit_code=124,
                        status="timeout",
                        start_time=start_time,
                        latency_ms=wall_ms,
                        output="",
                        container_id=container_id,
                        timed_out=True,
                    ),
                )
                print(f"Sandbox timed out after {timeout}s (container killed)", file=sys.stderr)
                sys.exit(124)
            raise
        wall_ms = int((time.monotonic() - wall_start) * 1000)

        exit_code = result.get("StatusCode", -1)
        logs = container.logs(stdout=True, stderr=True)
        if isinstance(logs, bytes):
            logs = logs.decode("utf-8", errors="replace")
        logs = _truncate(logs)

        container.reload()
        oom_killed = container.attrs.get("State", {}).get("OOMKilled", False)
        container_id = container.short_id
        print(logs, end="")

        access_token = os.environ.get("OBSERVAL_KEY", "")
        server_url = os.environ.get("OBSERVAL_SERVER", "")
        if not access_token or not server_url:
            cfg = load_config()
            access_token = access_token or cfg.get("access_token", "")
            server_url = server_url or cfg.get("server_url", "")

        _send_span(
            server_url,
            access_token,
            _exec_span(
                sandbox_id=sandbox_id,
                image=image,
                command=command,
                runtime_type="docker",
                exit_code=exit_code,
                status="success" if exit_code == 0 else "error",
                start_time=start_time,
                latency_ms=wall_ms,
                output=logs,
                container_id=container_id,
                oom_killed=oom_killed,
            ),
        )
        sys.exit(exit_code)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
        if proxy is not None:
            proxy.stop()
        if restricted_network is not None:
            try:
                restricted_network.remove()
            except Exception:
                pass


def _lxc_run(sandbox_id: str, image: str, command: str | None, timeout: int) -> None:
    lxc = _require_bin("lxc")
    name = f"observal-{sandbox_id[:8]}-{uuid.uuid4().hex[:8]}"
    subprocess.run([lxc, "launch", image, name, "--ephemeral"], check=True, timeout=timeout)
    try:
        _run_subprocess([lxc, "exec", name, "--", "sh", "-lc", command or "sh"], timeout)
    finally:
        subprocess.run([lxc, "delete", name, "--force"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _firecracker_run(runtime_config: dict, timeout: int) -> None:
    firecracker = _require_bin("firecracker")
    config_path = runtime_config.get("config_path")
    cleanup_path = None
    if not config_path:
        kernel = runtime_config.get("kernel_image_path")
        rootfs = runtime_config.get("rootfs_path")
        if not (kernel and rootfs):
            print("Firecracker requires runtime_config.config_path or kernel_image_path/rootfs_path", file=sys.stderr)
            sys.exit(2)
        cfg = {
            "boot-source": {
                "kernel_image_path": kernel,
                "boot_args": runtime_config.get("boot_args", "console=ttyS0 reboot=k panic=1 pci=off"),
            },
            "drives": [
                {
                    "drive_id": "rootfs",
                    "path_on_host": rootfs,
                    "is_root_device": True,
                    "is_read_only": bool(runtime_config.get("rootfs_read_only", False)),
                }
            ],
            "machine-config": runtime_config.get("machine_config", {"vcpu_count": 1, "mem_size_mib": 256}),
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            json.dump(cfg, tmp)
            cleanup_path = tmp.name
        config_path = cleanup_path
    try:
        _run_subprocess([firecracker, "--config-file", str(config_path)], timeout)
    finally:
        if cleanup_path:
            try:
                os.unlink(cleanup_path)
            except OSError:
                pass


def _wasm_run(image: str, command: str | None, timeout: int, runtime_config: dict) -> None:
    wasmtime = _require_bin(runtime_config.get("runtime", "wasmtime"))
    module = runtime_config.get("module") or image
    if not module:
        print("WASM requires image or runtime_config.module", file=sys.stderr)
        sys.exit(2)
    argv = [wasmtime, "run"]
    for directory in runtime_config.get("preopen_dirs", ["."]):
        argv.extend(["--dir", str(directory)])
    argv.append(str(module))
    if command:
        argv.extend(shlex.split(command))
    _run_subprocess(argv, timeout)


def run_sandbox(
    sandbox_id: str,
    image: str,
    command: str | None = None,
    timeout: int = 300,
    env: dict | None = None,
    runtime_type: str = "docker",
    network_policy: str = "none",
    resource_limits: dict | None = None,
    runtime_config: dict | None = None,
    mounts: list[str] | None = None,
):
    """Dispatch to the configured local sandbox runtime."""
    resource_limits = resource_limits or {}
    runtime_config = runtime_config or {}
    if runtime_type == "docker":
        return _docker_run(
            sandbox_id, image, command, timeout, env, network_policy, resource_limits, mounts, runtime_config
        )
    if runtime_type == "lxc":
        return _lxc_run(sandbox_id, image, command, timeout)
    if runtime_type == "firecracker":
        return _firecracker_run(runtime_config, timeout)
    if runtime_type == "wasm":
        return _wasm_run(image, command, timeout, runtime_config)
    print(f"Unsupported sandbox runtime_type: {runtime_type}", file=sys.stderr)
    sys.exit(2)


# ── Persistent sessions ─────────────────────────────────────────────
#
# A session is a kept-alive container (tail -f /dev/null) with an optional
# named volume mounted at /workspace, so consecutive session_exec calls share
# filesystem state. The registry lives in ~/.observal/sandbox_sessions.json so
# sessions survive MCP/harness restarts; idle sessions are garbage collected.

DEFAULT_SESSION_TTL_SECONDS = 1800


def _sessions_path(home: Path | None = None) -> Path:
    base = home if home is not None else Path.home()
    return base / ".observal" / "sandbox_sessions.json"


def _load_sessions(home: Path | None = None) -> dict:
    try:
        data = json.loads(_sessions_path(home).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_sessions(sessions: dict, home: Path | None = None) -> None:
    path = _sessions_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(sessions), encoding="utf-8")
    temporary.replace(path)


def _docker_client():
    try:
        import docker
    except ImportError:
        print(
            "local-runtime-missing: Docker SDK not found. Reinstall the CLI: pip install 'dev-library-cli'",
            file=sys.stderr,
        )
        sys.exit(127)
    return docker.from_env()


def _session_env_kwargs(env: dict | None, network_policy: str, resource_limits: dict, mounts, volume_name: str | None):
    run_kwargs: dict = {"detach": True, "environment": env or {}, "stdout": True, "stderr": True}
    if network_policy in {"none", "host", "bridge"}:
        run_kwargs["network_mode"] = network_policy
    # restricted sessions get a dedicated internal network from the caller;
    # the allowlist proxy only spans a single ephemeral run.
    if _int_or(resource_limits.get("memory_mb"), 0) > 0:
        run_kwargs["mem_limit"] = f"{_int_or(resource_limits['memory_mb'])}m"
    if _int_or(resource_limits.get("cpu_count"), 0) > 0:
        try:
            run_kwargs["nano_cpus"] = int(float(resource_limits["cpu_count"]) * 1_000_000_000)
        except (TypeError, ValueError):
            pass
    volumes = list(mounts or [])
    if volume_name:
        volumes.append(f"{volume_name}:/workspace:rw")
    if volumes:
        run_kwargs["volumes"] = volumes
    return run_kwargs


def _parse_iso(value: str) -> datetime:
    """Parse a registry timestamp; naive stamps are treated as UTC (see _now_iso)."""
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _session_ttl() -> int:
    try:
        return max(60, int(os.environ.get("OBSERVAL_SANDBOX_SESSION_TTL", DEFAULT_SESSION_TTL_SECONDS)))
    except ValueError:
        return DEFAULT_SESSION_TTL_SECONDS


def _gc_opportunistic(home: Path | None = None) -> None:
    """Stop idle sessions on every session action; never raises."""
    try:
        session_gc(_session_ttl(), home=home)
    except Exception:
        pass


def session_start(
    *,
    sandbox_id: str,
    image: str,
    runtime_type: str = "docker",
    env: dict | None = None,
    network_policy: str = "none",
    resource_limits: dict | None = None,
    mounts: list[str] | None = None,
    workspace: bool = True,
    home: Path | None = None,
) -> NoReturn:
    """Start a kept-alive container and register the session."""
    if runtime_type != "docker":
        print(f"Persistent sessions require the docker runtime (requested: {runtime_type}).", file=sys.stderr)
        sys.exit(2)

    _gc_opportunistic(home)
    client = _docker_client()
    session_id = str(uuid.uuid4())
    volume_name = f"observal-ws-{session_id[:12]}" if workspace else None
    if volume_name:
        client.volumes.create(name=volume_name)
    restricted_network = None
    if network_policy == "restricted":
        # Sessions outlive a single runner process, so the ephemeral allowlist
        # proxy cannot cover them: isolate on a dedicated internal network and
        # say so instead of silently claiming egress control.
        print(
            "restricted session: dedicated internal network, no egress proxy "
            "(the allowlist proxy covers ephemeral runs only)",
            file=sys.stderr,
        )
        restricted_network = client.networks.create(f"observal-sbx-{session_id[:12]}", driver="bridge", internal=True)
    try:
        container = client.containers.run(
            image,
            ["tail", "-f", "/dev/null"],
            name=f"observal-session-{session_id[:12]}",
            working_dir="/workspace" if volume_name else None,
            **{
                **_session_env_kwargs(env, network_policy, resource_limits or {}, mounts, volume_name),
                **({"network": restricted_network.name} if restricted_network else {}),
            },
        )
    except Exception as exc:
        if volume_name:
            try:
                client.volumes.get(volume_name).remove(force=True)
            except Exception:
                pass
        if restricted_network is not None:
            try:
                restricted_network.remove()
            except Exception:
                pass
        print(f"Error starting session: {exc}", file=sys.stderr)
        sys.exit(1)

    sessions = _load_sessions(home)
    sessions[session_id] = {
        "container_id": container.short_id,
        "sandbox_id": sandbox_id,
        "image": image,
        "runtime_type": runtime_type,
        "network_policy": network_policy,
        "volume": volume_name,
        "network": restricted_network.name if restricted_network else None,
        "started_at": _now_iso(),
        "last_used": _now_iso(),
    }
    _save_sessions(sessions, home)
    print(session_id)
    sys.exit(0)


def _get_session_container(sessions: dict, session_id: str, home: Path | None = None):
    entry = sessions.get(session_id)
    if entry is None:
        print(f"Unknown session: {session_id}", file=sys.stderr)
        sys.exit(1)
    try:
        return entry, _docker_client().containers.get(entry["container_id"])
    except Exception:
        sessions.pop(session_id, None)
        _save_sessions(sessions, home)
        print(f"Session container is gone (it was stopped or removed): {session_id}", file=sys.stderr)
        sys.exit(1)


def session_exec(session_id: str, command: str, timeout: int = 300, home: Path | None = None) -> NoReturn:
    """Run a command inside a session container; filesystem state persists."""
    _gc_opportunistic(home)
    sessions = _load_sessions(home)
    entry, container = _get_session_container(sessions, session_id, home)
    start_time = _now_iso()
    wall_start = time.monotonic()
    try:
        exit_code, (stdout, stderr) = container.exec_run(["sh", "-lc", command], demux=True)
    except Exception as exc:
        print(f"Error executing in session: {exc}", file=sys.stderr)
        sys.exit(1)
    wall_ms = _int_or((time.monotonic() - wall_start) * 1000)

    text = ""
    for stream in (stdout, stderr):
        if isinstance(stream, bytes):
            text += stream.decode("utf-8", errors="replace")
        elif isinstance(stream, str):
            text += stream
    print(_truncate(text), end="")

    sessions[session_id]["last_used"] = _now_iso()
    _save_sessions(sessions, home)

    _send_span(
        os.environ.get("OBSERVAL_SERVER", ""),
        os.environ.get("OBSERVAL_KEY", ""),
        _exec_span(
            sandbox_id=str(entry.get("sandbox_id") or session_id),
            image=str(entry.get("image") or ""),
            command=command,
            runtime_type="docker",
            exit_code=_int_or(exit_code),
            status="success" if exit_code == 0 else "error",
            start_time=start_time,
            latency_ms=wall_ms,
            output=_truncate(text),
            container_id=str(entry.get("container_id") or "") or None,
        ),
    )
    sys.exit(_int_or(exit_code))


def _session_target(entry: dict, path: str) -> str:
    """Resolve a user path inside the session, rooted at /workspace when present."""
    target = path.lstrip("/")
    if not target or ".." in Path(target).parts:
        print(f"Refusing unsafe path: {path!r}", file=sys.stderr)
        sys.exit(2)
    base = "/workspace" if entry.get("volume") else ""
    return f"{base}/{target}" if base else f"/{target}"


def session_files_get(session_id: str, path: str, home: Path | None = None) -> NoReturn:
    """Print a single file's content from a session container."""
    sessions = _load_sessions(home)
    entry, container = _get_session_container(sessions, session_id, home)
    full_path = _session_target(entry, path)
    try:
        stream, _stat = container.get_archive(full_path)
        tar_bytes = b"".join(chunk for chunk in stream)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as archive:
            member = next(iter(archive.getmembers()), None)
            if member is None or not member.isfile():
                raise ValueError(f"not a regular file: {path}")
            fileobj = archive.extractfile(member)
            if fileobj is None:
                raise ValueError(f"cannot extract: {path}")
            content = fileobj.read()
    except Exception as exc:
        print(f"Error reading {path!r}: {exc}", file=sys.stderr)
        sys.exit(1)
    print(content.decode("utf-8", errors="replace"), end="")
    sessions[session_id]["last_used"] = _now_iso()
    _save_sessions(sessions, home)
    sys.exit(0)


def session_files_put(session_id: str, path: str, content: str, home: Path | None = None) -> NoReturn:
    """Write a single file into a session container (workspace path)."""
    sessions = _load_sessions(home)
    entry, container = _get_session_container(sessions, session_id, home)
    full_path = _session_target(entry, path)
    directory, _, name = full_path[1:].rpartition("/")
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo(name=name)
        data = content.encode("utf-8")
        info.size = len(data)
        info.mtime = _int_or(time.time())
        archive.addfile(info, io.BytesIO(data))
    try:
        container.put_archive(f"/{directory}", io.BytesIO(payload.getvalue()))
    except Exception as exc:
        print(f"Error writing {path!r}: {exc}", file=sys.stderr)
        sys.exit(1)
    sessions[session_id]["last_used"] = _now_iso()
    _save_sessions(sessions, home)
    sys.exit(0)


def _stop_session_entry(entry: dict, keep_workspace: bool) -> None:
    """Stop containers/volumes/networks for a registry entry; best-effort, never raises."""
    client = _docker_client()
    try:
        client.containers.get(entry["container_id"]).remove(force=True)
    except Exception:
        pass
    volume = entry.get("volume")
    if volume and not keep_workspace:
        try:
            client.volumes.get(volume).remove(force=True)
        except Exception:
            pass
    network = entry.get("network")
    if network:
        try:
            client.networks.get(network).remove()
        except Exception:
            pass


def session_stop(session_id: str, keep_workspace: bool = False, home: Path | None = None) -> NoReturn:
    """Stop a session: remove container, drop the workspace volume unless kept."""
    sessions = _load_sessions(home)
    entry = sessions.get(session_id)
    if entry is None:
        print(f"Unknown session: {session_id}", file=sys.stderr)
        sys.exit(1)
    _stop_session_entry(entry, keep_workspace)
    sessions.pop(session_id, None)
    _save_sessions(sessions, home)
    print(f"stopped {session_id}")
    sys.exit(0)


def session_list(home: Path | None = None) -> NoReturn:
    """Print the live session registry as JSON."""
    sessions = _load_sessions(home)
    now = datetime.now(UTC)
    listing = []
    for session_id, entry in sessions.items():
        try:
            idle = int((now - _parse_iso(entry["last_used"])).total_seconds())
        except (KeyError, ValueError):
            idle = -1
        listing.append(
            {
                "session_id": session_id,
                "sandbox_id": entry.get("sandbox_id"),
                "image": entry.get("image"),
                "started_at": entry.get("started_at"),
                "last_used": entry.get("last_used"),
                "idle_seconds": idle,
            }
        )
    print(json.dumps(listing, indent=2))
    sys.exit(0)


def session_gc(ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS, home: Path | None = None) -> list[str]:
    """Stop sessions idle for longer than the TTL; returns stopped ids."""
    sessions = _load_sessions(home)
    now = datetime.now(UTC)
    stopped: list[str] = []
    for session_id, entry in list(sessions.items()):
        try:
            idle = (now - _parse_iso(entry["last_used"])).total_seconds()
        except (KeyError, ValueError):
            continue
        if idle > ttl_seconds:
            _stop_session_entry(entry, keep_workspace=False)
            sessions.pop(session_id, None)
            stopped.append(session_id)
    if stopped:
        _save_sessions(sessions, home)
    return stopped


def main():
    """CLI entry point for observal-sandbox-run."""
    args = sys.argv[1:]
    sandbox_id = ""
    image = ""
    command = None
    timeout = 300
    env = {}
    mounts: list[str] = []
    runtime_type = "docker"
    network_policy = "none"
    resource_limits = {}
    runtime_config = {}
    action = None
    session_id = ""
    path = ""
    content = ""
    keep_workspace = False

    i = 0
    while i < len(args):
        if args[i] == "--sandbox-id" and i + 1 < len(args):
            sandbox_id = args[i + 1]
            i += 2
        elif args[i] == "--image" and i + 1 < len(args):
            image = args[i + 1]
            i += 2
        elif args[i] == "--runtime-type" and i + 1 < len(args):
            runtime_type = args[i + 1]
            i += 2
        elif args[i] == "--command" and i + 1 < len(args):
            command = args[i + 1]
            i += 2
        elif args[i] == "--timeout" and i + 1 < len(args):
            try:
                timeout = int(args[i + 1])
            except ValueError:
                print(f"Invalid --timeout value: {args[i + 1]!r}", file=sys.stderr)
                sys.exit(2)
            i += 2
        elif args[i] == "--network-policy" and i + 1 < len(args):
            network_policy = args[i + 1]
            i += 2
        elif args[i] == "--resource-limits" and i + 1 < len(args):
            try:
                resource_limits = json.loads(args[i + 1] or "{}")
            except json.JSONDecodeError:
                print(f"Invalid --resource-limits JSON: {args[i + 1]!r}", file=sys.stderr)
                sys.exit(2)
            i += 2
        elif args[i] == "--runtime-config" and i + 1 < len(args):
            try:
                runtime_config = json.loads(args[i + 1] or "{}")
            except json.JSONDecodeError:
                print(f"Invalid --runtime-config JSON: {args[i + 1]!r}", file=sys.stderr)
                sys.exit(2)
            i += 2
        elif args[i] == "--env" and i + 1 < len(args):
            k, _, v = args[i + 1].partition("=")
            env[k] = v.strip("\"'")
            i += 2
        elif args[i] == "--mount" and i + 1 < len(args):
            mounts.append(args[i + 1])
            i += 2
        elif args[i] == "--action" and i + 1 < len(args):
            action = args[i + 1]
            i += 2
        elif args[i] == "--session-id" and i + 1 < len(args):
            session_id = args[i + 1]
            i += 2
        elif args[i] == "--path" and i + 1 < len(args):
            path = args[i + 1]
            i += 2
        elif args[i] == "--content" and i + 1 < len(args):
            content = args[i + 1]
            i += 2
        elif args[i] == "--keep-workspace":
            keep_workspace = True
            i += 1
        elif args[i] == "--":
            command = " ".join(args[i + 1 :])
            break
        else:
            i += 1

    if action:
        valid_actions = {"start", "exec", "stop", "list", "files-get", "files-put", "gc"}
        if action not in valid_actions:
            print(f"Unknown --action: {action}. Choose from: {', '.join(sorted(valid_actions))}", file=sys.stderr)
            sys.exit(2)
        if action == "start":
            if not image:
                print("session start requires --image", file=sys.stderr)
                sys.exit(1)
            session_start(
                sandbox_id=sandbox_id or "adhoc",
                image=image,
                runtime_type=runtime_type,
                env=env,
                network_policy=network_policy,
                resource_limits=resource_limits,
                mounts=mounts,
                workspace=True,
            )
        if action == "exec":
            if not session_id or not command:
                print("exec requires --session-id and --command", file=sys.stderr)
                sys.exit(1)
            session_exec(session_id, command, timeout)
        if action == "stop":
            if not session_id:
                print("stop requires --session-id", file=sys.stderr)
                sys.exit(1)
            session_stop(session_id, keep_workspace=keep_workspace)
        if action == "list":
            session_list()
        if action == "files-get":
            if not session_id or not path:
                print("files-get requires --session-id and --path", file=sys.stderr)
                sys.exit(1)
            session_files_get(session_id, path)
        if action == "files-put":
            if not session_id or not path:
                print("files-put requires --session-id, --path and --content", file=sys.stderr)
                sys.exit(1)
            session_files_put(session_id, path, content)
        if action == "gc":
            stopped = session_gc(_session_ttl())
            print(json.dumps({"stopped": stopped}))
            sys.exit(0)

    if not image and runtime_type in {"docker", "lxc", "wasm"} and not runtime_config.get("module"):
        print(
            "Usage: observal-sandbox-run --sandbox-id <id> --image <image> [--runtime-type docker|lxc|firecracker|wasm] [--command <cmd>] [--timeout <s>]",
            file=sys.stderr,
        )
        sys.exit(1)

    run_sandbox(
        sandbox_id, image, command, timeout, env, runtime_type, network_policy, resource_limits, runtime_config, mounts
    )


if __name__ == "__main__":
    main()
