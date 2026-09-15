# SPDX-FileCopyrightText: 2026 Edgar F. Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Workflow registry CLI: submit, list, show, edit, and install."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import dev_library_cli.cmd_workflow as workflow
from dev_library_cli.main import app

runner = CliRunner()

SCRIPT = (
    "// sizing workflow\n"
    "const rounds = args.maxRounds ?? 3;\n"
    "const result = agent('counter', 'count the requirements', {});\n"
    "return {status: 'done', rounds};\n"
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(workflow, "spinner", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(workflow.config, "load", MagicMock(return_value={"username": "alice"}))
    monkeypatch.setattr(workflow.config, "save_last_results", MagicMock())
    monkeypatch.chdir(tmp_path)


def _item(**overrides) -> dict:
    item = {
        "id": "workflow-1",
        "name": "cosmic-sizing",
        "namespace": "acme",
        "slug": "cosmic-sizing",
        "qualified_name": "acme/cosmic-sizing",
        "version": "1.0.0",
        "status": "approved",
        "description": "Deterministic COSMIC sizing",
        "supported_harnesses": ["pi"],
        "script_content": SCRIPT,
    }
    item.update(overrides)
    return item


def test_submit_with_script_file_posts_payload(monkeypatch, tmp_path):
    script = tmp_path / "cosmic-sizing.js"
    script.write_text(SCRIPT)
    post = MagicMock(return_value={"id": "workflow-1", "name": "cosmic-sizing", "status": "pending"})
    monkeypatch.setattr(workflow.client, "post", post)
    monkeypatch.setattr(workflow.client, "add_publish_target", MagicMock())

    result = runner.invoke(
        app,
        [
            "registry",
            "workflow",
            "submit",
            "--script-file",
            str(script),
            "--name",
            "cosmic-sizing",
            "--description",
            "Deterministic COSMIC sizing",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = post.call_args.args[1]
    assert payload["script_content"] == SCRIPT
    assert payload["name"] == "cosmic-sizing"
    assert payload["supported_harnesses"] == ["pi"]
    assert "Workflow submitted" in result.output


def test_submit_rejects_missing_script_file():
    result = runner.invoke(
        app,
        [
            "registry",
            "workflow",
            "submit",
            "--script-file",
            "does-not-exist.js",
            "--name",
            "cosmic-sizing",
            "--description",
            "x",
        ],
    )

    assert result.exit_code != 0
    assert "was not found" in result.output


def test_submit_rejects_empty_script_file(tmp_path):
    empty = tmp_path / "empty.js"
    empty.write_text("   \n")
    result = runner.invoke(
        app,
        [
            "registry",
            "workflow",
            "submit",
            "--script-file",
            str(empty),
            "--name",
            "cosmic-sizing",
            "--description",
            "x",
        ],
    )

    assert result.exit_code != 0
    assert "is empty" in result.output


def test_submit_rejects_unknown_harness(tmp_path):
    script = tmp_path / "wf.js"
    script.write_text(SCRIPT)
    result = runner.invoke(
        app,
        [
            "registry",
            "workflow",
            "submit",
            "--script-file",
            str(script),
            "--name",
            "cosmic-sizing",
            "--description",
            "x",
            "--harness",
            "not-a-harness",
        ],
    )

    assert result.exit_code != 0
    assert "Unknown harness" in result.output


def test_submit_from_json_with_inline_script(monkeypatch, tmp_path):
    payload_file = tmp_path / "wf.json"
    payload_file.write_text(
        '{"name": "cosmic-sizing", "version": "1.0.0", "description": "d", "script_content": "// js\\n"}'
    )
    post = MagicMock(return_value={"id": "workflow-1", "name": "cosmic-sizing", "status": "pending"})
    monkeypatch.setattr(workflow.client, "post", post)
    monkeypatch.setattr(workflow.client, "add_publish_target", MagicMock())

    result = runner.invoke(app, ["registry", "workflow", "submit", "--from-file", str(payload_file)])

    assert result.exit_code == 0, result.output
    payload = post.call_args.args[1]
    assert payload["script_content"] == "// js\n"
    assert payload["owner"] == "alice"


def test_list_renders_rows(monkeypatch):
    get = MagicMock(return_value=[_item()])
    monkeypatch.setattr(workflow.client, "get", get)

    result = runner.invoke(app, ["registry", "workflow", "list"])

    assert result.exit_code == 0, result.output
    assert "cosmic-sizing" in result.output
    assert "acme" in result.output


def test_list_empty_state_is_quiet(monkeypatch):
    monkeypatch.setattr(workflow.client, "get", MagicMock(return_value=[]))

    result = runner.invoke(app, ["registry", "workflow", "list"])

    assert result.exit_code == 0, result.output
    assert "No workflows found" in result.output


def test_list_json_outputs_items(monkeypatch):
    monkeypatch.setattr(workflow.client, "get", MagicMock(return_value=[_item()]))
    result = runner.invoke(app, ["registry", "workflow", "list", "--output", "json"])

    assert result.exit_code == 0, result.output
    assert '"qualified_name": "acme/cosmic-sizing"' in result.output


def test_show_renders_script_preview(monkeypatch):
    monkeypatch.setattr(workflow.client, "get", MagicMock(return_value=_item()))

    result = runner.invoke(app, ["registry", "workflow", "show", "acme/cosmic-sizing"])

    assert result.exit_code == 0, result.output
    assert "cosmic-sizing" in result.output
    assert "sizing workflow" in result.output


def test_edit_posts_updates_with_script(monkeypatch, tmp_path):
    script = tmp_path / "v2.js"
    script.write_text("// v2 workflow\n")
    post = MagicMock(return_value={"id": "workflow-1", "name": "cosmic-sizing", "status": "pending"})
    monkeypatch.setattr(workflow.client, "post", post)
    put = MagicMock(return_value={"id": "workflow-1", "name": "cosmic-sizing", "status": "pending"})
    monkeypatch.setattr(workflow.client, "put", put)
    monkeypatch.setattr(workflow.client, "resolve_registry_reference", MagicMock(return_value="workflow-1"))

    result = runner.invoke(
        app,
        [
            "registry",
            "workflow",
            "edit",
            "acme/cosmic-sizing",
            "--script-file",
            str(script),
            "--version",
            "2.0.0",
        ],
    )

    assert result.exit_code == 0, result.output
    assert put.call_args.args[1] == {"version": "2.0.0", "script_content": "// v2 workflow\n"}


def test_edit_without_changes_fails(monkeypatch):
    monkeypatch.setattr(workflow.client, "resolve_registry_reference", MagicMock(return_value="workflow-1"))
    result = runner.invoke(app, ["registry", "workflow", "edit", "acme/cosmic-sizing"])

    assert result.exit_code != 0
    assert "No workflow changes" in result.output


def test_install_writes_the_workflow_file(monkeypatch, tmp_path):
    snippet = {"workflows": [{"path": ".pi/workflows/cosmic-sizing.js", "content": SCRIPT}]}
    post = MagicMock(return_value={"config_snippet": snippet, "warnings": []})
    monkeypatch.setattr(workflow.client, "post", post)
    resolve = MagicMock(return_value="workflow-1")
    monkeypatch.setattr(workflow.client, "resolve_registry_reference", resolve)

    result = runner.invoke(app, ["registry", "workflow", "install", "acme/cosmic-sizing", "--harness", "pi"])

    assert result.exit_code == 0, result.output
    written = tmp_path / ".pi" / "workflows" / "cosmic-sizing.js"
    assert written.read_text() == SCRIPT
    assert "installed" in result.output


def test_install_user_scope_uses_home(monkeypatch, tmp_path):
    snippet = {"workflows": [{"path": "~/.pi/agent/workflows/cosmic-sizing.js", "content": SCRIPT}]}
    post = MagicMock(return_value={"config_snippet": snippet, "warnings": []})
    monkeypatch.setattr(workflow.client, "post", post)
    monkeypatch.setattr(workflow.client, "resolve_registry_reference", MagicMock(return_value="workflow-1"))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    result = runner.invoke(
        app, ["registry", "workflow", "install", "acme/cosmic-sizing", "--harness", "pi", "--scope", "user"]
    )

    assert result.exit_code == 0, result.output
    assert (home / ".pi" / "agent" / "workflows" / "cosmic-sizing.js").exists()


def test_install_dry_run_does_not_write(monkeypatch):
    snippet = {"workflows": [{"path": ".pi/workflows/cosmic-sizing.js", "content": SCRIPT}]}
    monkeypatch.setattr(workflow.client, "post", MagicMock(return_value={"config_snippet": snippet, "warnings": []}))
    monkeypatch.setattr(workflow.client, "resolve_registry_reference", MagicMock(return_value="workflow-1"))

    result = runner.invoke(
        app, ["registry", "workflow", "install", "acme/cosmic-sizing", "--harness", "pi", "--no-write"]
    )

    assert result.exit_code == 0, result.output
    assert "would write" in result.output
    assert not Path(".pi/workflows/cosmic-sizing.js").exists()


def test_install_rejects_unknown_harness(monkeypatch):
    result = runner.invoke(app, ["registry", "workflow", "install", "acme/cosmic-sizing", "-i", "bogus"])

    assert result.exit_code != 0
    assert "Unknown harness" in result.output


def test_install_rejects_empty_snippet(monkeypatch):
    monkeypatch.setattr(workflow.client, "post", MagicMock(return_value={"config_snippet": {}, "warnings": []}))
    monkeypatch.setattr(workflow.client, "resolve_registry_reference", MagicMock(return_value="workflow-1"))

    result = runner.invoke(app, ["registry", "workflow", "install", "acme/cosmic-sizing", "-i", "pi"])

    assert result.exit_code != 0
    assert "empty workflow configuration" in result.output
