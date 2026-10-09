import typer

app = typer.Typer(help="Job tracker CLI", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Job tracker CLI."""


@app.command()
def ingest(
    all_sources: bool = typer.Option(False, "--all", help="Ingest every enabled source"),
) -> None:
    """Pull jobs from the configured sources (implemented in S1-08)."""
    typer.echo("ingest is not implemented yet (S1-08)")
    raise typer.Exit(code=1)
