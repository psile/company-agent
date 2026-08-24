from __future__ import annotations

import sys


def _print_push_results(pushed: list[dict]) -> None:
    if not pushed:
        print("pushed=0 reason=no candidate reached push threshold")
        return
    print(f"pushed={len(pushed)}")
    for row in pushed:
        ok = row.get("ok")
        channel = row.get("channel") or ""
        title = row.get("title") or row.get("id") or ""
        reason = row.get("reason") or "sent"
        print(f"- ok={ok} channel={channel} title={title} reason={reason}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "ingest":
        from .pipeline import RadarService

        result = RadarService().refresh()
        print(f"fetched={result['fetched']} work={len(result['work'])} personal={len(result['personal'])}")
        _print_push_results(result.get("pushed") or [])
        return
    if cmd == "push":
        from .pipeline import RadarService

        result = RadarService().push_top_work()
        _print_push_results([result])
        return
    if cmd == "serve":
        from .server import HOST, PORT, serve

        serve(HOST, PORT)
        return
    if cmd == "feishu-test":
        from .feishu import feishu_status, push_text

        print(feishu_status())
        result = push_text("【测试】办公秘书助手一对一飞书推送已接入。")
        print(result)
        return
    raise SystemExit("usage: python -m radar [serve|ingest|push|feishu-test]")


if __name__ == "__main__":
    main()
