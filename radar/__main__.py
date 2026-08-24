from __future__ import annotations

import sys


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "ingest":
        from .pipeline import RadarService

        result = RadarService().refresh()
        print(f"fetched={result['fetched']} work={len(result['work'])} personal={len(result['personal'])}")
        return
    if cmd == "serve":
        from .server import HOST, PORT, serve

        serve(HOST, PORT)
        return
    raise SystemExit("usage: python -m radar [serve|ingest]")


if __name__ == "__main__":
    main()
