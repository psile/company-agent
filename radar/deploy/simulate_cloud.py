"""本机模拟云主机：0.0.0.0 监听 + 探活。不依赖 Docker。"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("PORT") or 8766)


def lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def wait_health(url: str, tries: int = 20) -> str:
    last = ""
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last = str(exc)
            time.sleep(0.4)
    raise SystemExit(f"health check failed: {last}")


def main() -> None:
    ip = lan_ip()
    env = os.environ.copy()
    env["RADAR_HOST"] = "0.0.0.0"
    env["PORT"] = str(PORT)
    env["PYTHONPATH"] = str(ROOT)
    print("模拟云主机启动")
    print(f"  bind     0.0.0.0:{PORT}  （云上安全组放行该端口）")
    print(f"  探活     http://127.0.0.1:{PORT}/api/health")
    print(f"  局域网   http://{ip}:{PORT}/")
    print(f"  公网形态 http://<云服务器公网IP>:{PORT}/")
    proc = subprocess.Popen(
        [sys.executable, "-m", "radar", "serve"],
        cwd=str(ROOT),
        env=env,
    )
    try:
        body = wait_health(f"http://127.0.0.1:{PORT}/api/health")
        print("探活通过", body)
        print("浏览器打开上面的局域网地址即可，当作已部署到一台云 VM。")
        print("Ctrl+C 结束模拟。")
        proc.wait()
    except KeyboardInterrupt:
        print("停止模拟")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
