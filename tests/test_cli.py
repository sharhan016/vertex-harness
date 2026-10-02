import json

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
