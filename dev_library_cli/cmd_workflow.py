# SPDX-FileCopyrightText: 2026 Edgar F. Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Workflow registry CLI commands.

A workflow is a single self-contained JavaScript file that deterministic
harness workflow runtimes execute. Submit reads the script from a .js file;
install writes it into the harness's workflow directory.
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import typer
from packaging.version import InvalidVersion, Version
from rich import print as rprint
from rich.table import Table

from dev_library_cli import client, config
from dev_library_cli.constants import VALID_HARNESSES
from dev_library_cli.errors import ErrorCategory, fail
from dev_library_cli.prompts import text_input
from dev_library_cli.render import (
    OutputMode,
    console,
    display_name,
    esc,
    handle,
    kv_panel,
    output_json,
    relative_time,
    spinner,
    status_badge,
)

workflow_app = typer.Typer(
    help=(
        "Workflow registry commands\n\n"
        "Examples:\n"
        "  dev-library registry workflow list\n"
        "  dev-library registry workflow show alice/cosmic-sizing\n"
        "  dev-library registry workflow submit --script-file cosmic-sizing.js"
    )
)


def register_workflow(app: typer.Typer):
    app.add_typer(workflow_app, name="workflow")


def _read_script_file(path: str) -> str:
    """Read the workflow script body from a .js file."""
    try:
        script = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError as error:
        fail(
            ErrorCategory.NOT_FOUND,
            "The workflow script file was not found.",
            operation="Submit workflow",
            resource=path,
            remediation="Provide an existing .js file and retry.",
            detail=repr(error),
        )
    except OSError as error:
        fail(
            ErrorCategory.UNAVAILABLE,
            "The workflow script file could not be read.",
            operation="Submit workflow",
            resource=path,
            remediation="Check file permissions and retry.",
            detail=repr(error),
        )
    stripped = script.strip()
    if not stripped:
        fail(
            ErrorCategory.VALIDATION,
            "The workflow script file is empty.",
            operation="Submit workflow",
            resource=path,
            remediation="Provide a non-empty JavaScript file and retry.",
        )
    return script


def _validate_version(version: str, operation: str) -> None:
    try:
        Version(str(version))
    except InvalidVersion as error:
        fail(
            ErrorCategory.VALIDATION,
            "The workflow version is invalid.",
            operation=operation,
            resource=str(version),
            remediation="Provide a valid version and retry.",
            detail=repr(error),
        )


@workflow_app.command(name="submit")
def workflow_submit(
    from_file: str | None = typer.Option(None, "--from-file", "-f", help="Create from JSON file (script_content or script_file)"),
    script_file: str | None = typer.Option(None, "--script-file", help="Read the workflow script from this .js file"),
    name: str | None = typer.Option(None, "--name", "-n", help="Workflow name"),
    version: str | None = typer.Option(None, "--version", "-v", help="Version (default: 1.0.0)"),
    description: str | None = typer.Option(None, "--description", "-d", help="Short description"),
    supported_harnesses: list[str] | None = typer.Option(None, "--harness", help="Supported harness (repeatable, default: pi)"),
    draft: bool = typer.Option(False, "--draft", help="Save as draft instead of submitting for review"),
    submit_draft: str | None = typer.Option(None, "--submit", help="Submit a draft for review (workflow ID)"),
    team: str | None = typer.Option(None, "--team", help="Teamspace UUID or handle"),
    visibility: str | None = typer.Option(None, "--visibility", help="Visibility: public or team"),
    output: OutputMode = typer.Option("table", "--output", "-o", help="Output format: table or json"),
):
    """Submit a new workflow for review.

    A workflow is a single self-contained JavaScript file (no imports, no
    filesystem or network access at submit time; determinism is the
    submitter's contract). The script body is read from --script-file or
    from script_content/script_file inside the --from-file JSON.

    Examples:
        dev-library registry workflow submit --script-file cosmic-sizing.js -n cosmic-sizing -d "COSMIC sizing"
        dev-library registry workflow submit --from-file workflow.json --team solution-design
    """
    if draft and submit_draft:
        fail(
            ErrorCategory.VALIDATION,
            "Draft creation and draft submission cannot be requested together.",
            operation="Submit workflow",
            resource="submit options",
            remediation="Choose either draft creation or draft submission and retry.",
        )
    if submit_draft:
        resolved = client.resolve_registry_reference("workflow", submit_draft)
        submit_context = nullcontext() if output == "json" else spinner("Submitting draft for review...")
        with submit_context:
            result = client.post(f"/api/v1/workflows/{resolved}/submit")
        if output == "json":
            output_json(result)
        else:
            rprint(f"[green]✓ Draft submitted for review![/green] ID: [bold]{esc(result['id'])}[/bold]")
        return

    payload: dict = {}
    if from_file:
        payload = _load_payload_file(from_file)
        if payload.get("script_file") and not payload.get("script_content"):
            payload["script_content"] = _read_script_file(str(payload.pop("script_file")))
        else:
            payload.pop("script_file", None)
    elif script_file or name or description or version:
        payload = {
            "name": name,
            "version": version or "1.0.0",
            "description": description,
            "owner": config.load().get("username", ""),
            "script_content": _read_script_file(script_file) if script_file else None,
            "supported_harnesses": supported_harnesses or ["pi"],
        }
    elif output != "json":
        payload = {
            "name": text_input("Workflow name"),
            "version": text_input("Version", default="1.0.0"),
            "description": text_input("Description"),
            "owner": config.load().get("username", ""),
            "script_content": _read_script_file(text_input("Script file (.js)")),
            "supported_harnesses": ["pi"],
        }
    else:
        fail(
            ErrorCategory.VALIDATION,
            "JSON mode requires explicit workflow fields.",
            operation="Submit workflow",
            resource="submit options",
            remediation="Provide name, description, and script file (or a JSON payload file).",
        )

    if not payload.get("owner"):
        payload["owner"] = config.load().get("username", "")
    if not (payload.get("name") and payload.get("description") and payload.get("script_content")):
        fail(
            ErrorCategory.VALIDATION,
            "Workflow name, description, and script content are required.",
            operation="Submit workflow",
            resource="workflow payload",
            remediation="Provide the required fields and retry.",
        )
    bad_harnesses = [h for h in payload.get("supported_harnesses", ["pi"]) if h not in VALID_HARNESSES]
    if bad_harnesses:
        fail(
            ErrorCategory.VALIDATION,
            f"Unknown harness: {bad_harnesses[0]}.",
            operation="Submit workflow",
            resource="supported harnesses",
            remediation=f"Choose from: {', '.join(VALID_HARNESSES)}.",
        )
    _validate_version(payload.get("version") or "1.0.0", "Submit workflow")

    client.add_publish_target(payload, team, visibility)
    submit_context = nullcontext() if output == "json" else spinner("Saving workflow...")
    with submit_context:
        endpoint = "/api/v1/workflows/draft" if draft else "/api/v1/workflows/submit"
        result = client.post(endpoint, payload)
    if output == "json":
        output_json(result)
        return
    message = "Draft saved" if draft else "Workflow submitted"
    rprint(f"[green]✓ {message}![/green] ID: [bold]{esc(result['id'])}[/bold]")
    rprint(f"  Install with: [cyan]dev-library registry workflow install {esc(result['id'])} --harness pi[/cyan]")


def _load_payload_file(from_file: str) -> dict:
    import json as _json

    try:
        with open(from_file) as f:
            payload = _json.load(f)
    except _json.JSONDecodeError as error:
        fail(
            ErrorCategory.VALIDATION,
            "The workflow submission file is not valid JSON.",
            operation="Submit workflow",
            resource=from_file,
            remediation="Correct the JSON and retry.",
            detail=repr(error),
        )
    except FileNotFoundError as error:
        fail(
            ErrorCategory.NOT_FOUND,
            "The workflow submission file was not found.",
            operation="Submit workflow",
            resource=from_file,
            remediation="Provide an existing JSON file and retry.",
            detail=repr(error),
        )
    if not isinstance(payload, dict):
        fail(
            ErrorCategory.VALIDATION,
            "The workflow submission file must contain a JSON object.",
            operation="Submit workflow",
            resource=from_file,
            remediation="Replace the file contents with a JSON object and retry.",
        )
    return payload


@workflow_app.command(name="list")
def workflow_list(
    search: str | None = typer.Option(None, "--search", "-s"),
    namespace: str | None = typer.Option(None, "--namespace", help="Filter by user or team namespace"),
    team: str | None = typer.Option(None, "--team", help="Only items owned by this teamspace"),
    output: OutputMode = typer.Option("table", "--output", "-o", help="Output format: table or json"),
):
    """List approved workflows in the registry.

    Shows only workflows with approved status. Row numbers from the output
    can be used as references in subsequent commands.

    Examples:
        dev-library registry workflow list
        dev-library registry workflow list --search "sizing" --output json
    """
    params = {}
    if search:
        params["search"] = search
    if namespace:
        params["namespace"] = namespace.lstrip("@").lower()
    if team:
        params["team_id"] = client.resolve_team_id(team)
    fetch_ctx = nullcontext() if output == "json" else spinner("Fetching workflows...")
    with fetch_ctx:
        data = client.get("/api/v1/workflows", params=params)
    if not data:
        config.save_last_results([], "workflow")
        if output == "json":
            output_json([])
        else:
            rprint("[dim]No workflows found.[/dim]")
        return
    config.save_last_results(data, "workflow")
    if output == "json":
        output_json(data)
        return
    table = Table(title=f"Workflows ({len(data)})", show_lines=False, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Version", style="green")
    table.add_column("Namespace", style="dim")
    table.add_column("Status")
    table.add_column("ID", style="dim", max_width=12)
    for i, item in enumerate(data, 1):
        table.add_row(
            str(i),
            esc(display_name(item)),
            esc(item.get("version", "")),
            esc(handle(item)),
            status_badge(item.get("status", "")),
            esc(str(item["id"])[:8] + "…"),
        )
    console.print(table)


@workflow_app.command(name="show")
def workflow_show(
    workflow_id: str = typer.Argument(..., help="ID, name, row number, or @alias"),
    output: OutputMode = typer.Option("table", "--output", "-o"),
):
    """Show detailed information about a workflow.

    Displays metadata, supported harnesses, and the first lines of the
    script body. Use --output json for the full script.

    Examples:
        dev-library registry workflow show solution-design/cosmic-sizing
        dev-library registry workflow show 1 --output json
    """
    resolved = client.resolve_registry_reference("workflow", workflow_id)
    fetch_ctx = nullcontext() if output == "json" else spinner()
    with fetch_ctx:
        item = client.get(f"/api/v1/workflows/{resolved}")
    if output == "json":
        output_json(item)
        return
    script = item.get("script_content") or ""
    preview = script.splitlines()[:3]
    preview_text = " ".join(preview)
    if len(script.splitlines()) > 3:
        preview_text += " …"
    console.print(
        kv_panel(
            f"{esc(display_name(item))} v{esc(item.get('version', '?'))}",
            [
                ("Status", status_badge(item.get("status", ""))),
                ("Namespace", esc(handle(item) or "N/A")),
                ("Description", esc(item.get("description", ""))),
                ("Harnesses", esc(", ".join(item.get("supported_harnesses", [])) or "N/A")),
                ("Script", esc(preview_text) if preview_text else "N/A"),
                ("Created", esc(relative_time(item.get("created_at")))),
                ("ID", f"[dim]{esc(item['id'])}[/dim]"),
            ],
            border_style="cyan",
        )
    )


@workflow_app.command(name="edit")
def workflow_edit(
    workflow_id: str = typer.Argument(..., help="ID, name, row number, or @alias"),
    from_file: str | None = typer.Option(None, "--from-file", "-f", help="Load updates from JSON file"),
    name: str | None = typer.Option(None, "--name", "-n", help="New listing name"),
    description: str | None = typer.Option(None, "--description", "-d", help="New description"),
    version: str | None = typer.Option(None, "--version", "-v", help="New version string"),
    script_file: str | None = typer.Option(None, "--script-file", help="Replace the script body from this .js file"),
    output: OutputMode = typer.Option("table", "--output", "-o", help="Output format: table or json"),
):
    """Edit a draft, rejected, or pending workflow submission.

    Updates fields on a workflow that has not yet been approved. Acquires
    an edit lock to prevent concurrent modifications.

    Examples:
        dev-library registry workflow edit my-workflow --script-file v2.js --version 2.0.0
        dev-library registry workflow edit abc123 --from-file updates.json
    """
    resolved = client.resolve_registry_reference("workflow", workflow_id)
    if from_file:
        updates = _load_payload_file(from_file)
        if updates.get("script_file") and not updates.get("script_content"):
            updates["script_content"] = _read_script_file(str(updates.pop("script_file")))
        else:
            updates.pop("script_file", None)
    else:
        updates = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if version is not None:
            updates["version"] = version
        if script_file is not None:
            updates["script_content"] = _read_script_file(script_file)

    if not updates:
        fail(
            ErrorCategory.VALIDATION,
            "No workflow changes were provided.",
            operation="Edit workflow",
            resource=workflow_id,
            remediation="Provide an update file or one or more field options.",
        )
    if updates.get("version") is not None:
        _validate_version(updates["version"], "Edit workflow")

    client.post(f"/api/v1/workflows/{resolved}/start-edit")
    save_context = nullcontext() if output == "json" else spinner("Saving changes...")
    with save_context:
        result = client.put(f"/api/v1/workflows/{resolved}/draft", updates)
    if output == "json":
        output_json(result)
    else:
        rprint(f"[green]✓ Updated {esc(result['name'])}[/green] (status: {esc(result.get('status', 'unknown'))})")


@workflow_app.command(name="install")
def workflow_install(
    workflow_id: str = typer.Argument(..., help="Workflow ID, name, row number, or @alias"),
    harness: str = typer.Option(..., "--harness", "-i", help="Target harness (pi)"),
    scope: str = typer.Option("project", "--scope", "-s", help="Install scope: project or user"),
    directory: str = typer.Option(".", "--dir", "-d", help="Target directory for project scope"),
    no_write: bool = typer.Option(False, "--no-write", help="Print the resolved path and snippet without writing"),
    version: str | None = typer.Option(None, "--version", "-V", help="Install a specific version"),
    output: OutputMode = typer.Option("table", "--output", "-o", help="Output format: table or json"),
):
    """Install a workflow into a harness by writing its script file.

    Resolves the install path from the harness registry (.pi/workflows/
    {name}.js for project scope, ~/.pi/agent/workflows/ for user scope)
    and writes the script body.

    Examples:
        dev-library registry workflow install solution-design/cosmic-sizing --harness pi
        dev-library registry workflow install 1 -i pi --scope user
    """
    if harness not in VALID_HARNESSES:
        fail(
            ErrorCategory.VALIDATION,
            f"Unknown harness: {harness}.",
            operation="Install workflow",
            resource="target harness",
            remediation=f"Choose from: {', '.join(VALID_HARNESSES)}.",
        )
    if scope not in ("project", "user"):
        fail(
            ErrorCategory.VALIDATION,
            f"Unknown install scope: {scope}.",
            operation="Install workflow",
            resource="install scope",
            remediation="Choose project or user.",
        )
    resolved = client.resolve_registry_reference("workflow", workflow_id)
    body: dict = {"harness": harness, "scope": scope}
    if version:
        _validate_version(version, "Install workflow")
        body["version"] = version
    fetch_ctx = nullcontext() if output == "json" else spinner("Fetching install config...")
    with fetch_ctx:
        result = client.post(f"/api/v1/workflows/{resolved}/install", body)
    files = (result.get("config_snippet") or {}).get("workflows") or []
    if not files:
        fail(
            ErrorCategory.UNAVAILABLE,
            "The server returned an empty workflow configuration.",
            operation="Install workflow",
            resource="generated workflow configuration",
            remediation="Check harness support for workflows and retry.",
        )
    entries = []
    for entry in files:
        raw_path = str(entry.get("path", ""))
        content = str(entry.get("content", ""))
        if scope == "user" or raw_path.startswith("~"):
            target = Path(raw_path).expanduser()
        else:
            target = (Path(directory).resolve() / raw_path).resolve()
        entries.append((target, content))
    if no_write:
        if output == "json":
            output_json({"workflow": resolved, "harness": harness, "files": [{"path": str(t)} for t, _ in entries]})
        else:
            rprint("[bold yellow]Dry run[/bold yellow] - no files written:")
            for target, _ in entries:
                rprint(f"  would write  [cyan]{esc(str(target))}[/cyan]")
        return
    for target, content in entries:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    if output == "json":
        output_json({"workflow": resolved, "harness": harness, "files": [{"path": str(t), "status": "created"} for t, _ in entries]})
        return
    for target, _ in entries:
        rprint(f"  [green]created[/green]  {esc(str(target))}")
    rprint(f"[green]✓ Workflow installed[/green] into [cyan]{esc(harness)}[/cyan]")
