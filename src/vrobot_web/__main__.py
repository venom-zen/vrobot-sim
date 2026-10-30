"""``python -m vrobot_web`` entry point."""

from __future__ import annotations

import argparse
from typing import Sequence

from vrobot_web.app import create_app

BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m vrobot_web",
        description="Serve the VirtualRobot live visualization on the loopback interface.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP port on {BIND_HOST} (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(create_app(), host=BIND_HOST, port=args.port)


if __name__ == "__main__":
    main()
