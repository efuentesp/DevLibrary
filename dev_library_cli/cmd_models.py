# SPDX-FileCopyrightText: 2026 Aryan Iyappan <aryaniyappan2006@gmail.com>
# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""``dev-library registry models`` - list registry-backed harness models."""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from dev_library_cli import model_catalog
from dev_library_cli.render import OutputMode, esc, output_json

models_app = typer.Typer(
    name="models",
    help=(
        "Inspect registry-backed harness model data.\n\n"
        "Examples:\n"
        "  dev-library registry models\n"
        "  dev-library registry models --harness claude-code\n"
        "  dev-library registry models list --output json"
    ),
    no_args_is_help=False,
)


def _emit_models(harness: str | None, output: OutputMode) -> None:
    try:
        catalog = model_catalog.fetch_catalog(harness=harness)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="harness") from exc
    rows = catalog.get("models") or []
    if output == "json":
        output_json(catalog)
        return
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("harness")
    table.add_column("model_id", overflow="fold")
    table.add_column("kind")
    table.add_column("display")
    for row in rows:
        table.add_row(
            esc(row["harness"]),
            esc(row["model_id"]),
            esc(row.get("kind", "exact")),
            esc(row.get("display_name", "")),
        )
    rprint(table)
    rprint(f"[dim]source: {esc(catalog.get('source', 'harness-registry'))}, count: {len(rows)}[/dim]")


@models_app.callback(invoke_without_command=True)
def models(
    ctx: typer.Context,
    harness: str | None = typer.Option(None, "--harness", help="Filter to one harness."),
    output: OutputMode = typer.Option("table", "--output", "-o", help="Output format: table or json"),
):
    if ctx.invoked_subcommand is None:
        _emit_models(harness, output)


@models_app.command("list")
def list_models(
    harness: str | None = typer.Option(None, "--harness", help="Filter to one harness."),
    output: OutputMode = typer.Option("table", "--output", "-o", help="Output format: table or json"),
):
    """List registry-backed harness models.

    Examples:
      dev-library registry models list
      dev-library registry models list --harness pi
      dev-library registry models list --output json
    """
    _emit_models(harness, output)
