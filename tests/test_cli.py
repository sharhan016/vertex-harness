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
