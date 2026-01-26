"""Entry point for running the package via `python -m`."""

from snekrpc import cli


def main() -> None:
    """Delegate to the CLI runner while swallowing Ctrl+C noise."""
    try:
        cli.main()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
