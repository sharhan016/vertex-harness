import json
import sys

from vertex_harness import __version__
from vertex_harness.cli import main


def test_cli_shows_help_when_no_command_is_given(capsys):
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "usage: vertex" in output
    assert "verifiable, recoverable software work" in output


def test_cli_reports_package_version(capsys):
    try:
        main(["--version"])
    except SystemExit as error:
        assert error.code == 0
    else:
        raise AssertionError("argparse version action did not exit")

    assert capsys.readouterr().out.strip() == f"vertex {__version__}"


def test_cli_drives_repository_workflow(tmp_path, capsys):
    assert main(["init", str(tmp_path), "--objective", "Ship a useful tool"]) == 0
    assert main(
        [
            "task",
            "add",
            str(tmp_path),
            "--id",
            "T-1",
            "--title",
            "Build the slice",
            "--outcome",
            "The slice works",
            "--criterion",
            "AC-1=The behavior is observable",
        ]
    ) == 0
    assert main(["task", "start", str(tmp_path), "T-1"]) == 0
    assert main(
        [
            "task",
            "block",
            str(tmp_path),
            "T-1",
            "--reason",
            "Awaiting a decision",
        ]
    ) == 0
    assert main(["task", "resume", str(tmp_path), "T-1"]) == 0
    capsys.readouterr()

    assert main(["status", str(tmp_path), "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["objective"] == "Ship a useful tool"
    assert status["revision"] == 4
    assert status["tasks"][0]["status"] == "active"
    assert status["tasks"][0]["acceptance_criteria"][0]["id"] == "AC-1"


def test_cli_reports_domain_errors_without_traceback(tmp_path, capsys):
    main(["init", str(tmp_path), "--objective", "Ship a useful tool"])
    capsys.readouterr()

    assert main(["task", "start", str(tmp_path), "missing"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error: task 'missing' does not exist" in captured.err
    assert "Traceback" not in captured.err


def test_cli_configures_runs_and_lists_verification(tmp_path, capsys):
    main(["init", str(tmp_path), "--objective", "Ship verified work"])
    main(
        [
            "task",
            "add",
            str(tmp_path),
            "--id",
            "T-1",
            "--title",
            "Verify it",
            "--outcome",
            "It is verified",
            "--criterion",
            "AC-1=The command passes",
        ]
    )
    assert main(
        [
            "check",
            "add",
            str(tmp_path),
            "T-1",
            "--id",
            "smoke",
            "--criterion",
            "AC-1",
            "--command",
            sys.executable,
            "-c",
            "print('ok')",
        ]
    ) == 0
    main(["task", "start", str(tmp_path), "T-1"])
    capsys.readouterr()

    assert main(["verify", str(tmp_path), "T-1"]) == 0
    verification = capsys.readouterr()
    assert "smoke: passed" in verification.out
    assert "completed task T-1" in verification.out

    assert main(["evidence", str(tmp_path), "--task", "T-1", "--json"]) == 0
    evidence = json.loads(capsys.readouterr().out)
    assert evidence[0]["check_id"] == "smoke"
    assert evidence[0]["outcome"] == "passed"


def test_cli_creates_and_lists_checkpoints(tmp_path, capsys):
    main(["init", str(tmp_path), "--objective", "Pause safely"])
    capsys.readouterr()

    assert main(
        [
            "checkpoint",
            "create",
            str(tmp_path),
            "--note",
            "Research is complete",
        ]
    ) == 0
    capsys.readouterr()

    assert main(["checkpoint", "list", str(tmp_path), "--json"]) == 0
    checkpoints = json.loads(capsys.readouterr().out)
    assert checkpoints[0]["note"] == "Research is complete"


def test_cli_builds_and_queries_python_index(tmp_path, capsys):
    source = tmp_path / "sample.py"
    source.write_text("def useful_name():\n    return 1\n", encoding="utf-8")

    assert main(["index", str(tmp_path)]) == 0
    assert "indexed 1 Python files" in capsys.readouterr().out

    assert main(["query", str(tmp_path), "search", "useful", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stale"] is False
    assert payload["results"][0]["path"] == "sample.py"


def test_cli_emits_bounded_agent_context(tmp_path, capsys):
    main(["init", str(tmp_path), "--objective", "Give context"])
    main(
        [
            "task",
            "add",
            str(tmp_path),
            "--id",
            "T-1",
            "--title",
            "Context task",
            "--outcome",
            "Context exists",
            "--criterion",
            "AC-1=The packet names the task",
        ]
    )
    capsys.readouterr()

    assert main(["context", str(tmp_path), "--task", "T-1"]) == 0
    packet = json.loads(capsys.readouterr().out)
    assert packet["task"]["id"] == "T-1"
    assert packet["bytes"] <= 8_000
