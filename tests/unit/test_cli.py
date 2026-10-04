from typer.testing import CliRunner

from forum_assist.cli import app


def test_help_exits_zero() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "forum-assist" in result.output
