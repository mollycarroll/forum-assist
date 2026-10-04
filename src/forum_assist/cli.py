import typer

app = typer.Typer(
    name="forum-assist",
    help="Human-in-the-loop forum reply drafting tool.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """forum-assist: human-in-the-loop forum reply drafting tool."""


if __name__ == "__main__":
    app()
