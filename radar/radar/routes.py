"""Table-driven HTTP route matching. Handlers stay in server.py."""

from __future__ import annotations

import re
from typing import Any, Callable, NamedTuple


class Match(NamedTuple):
    auth: str
    fn: Callable[..., Any]
    params: dict[str, str]


class Router:
    def __init__(self) -> None:
        self._rows: list[tuple[str, re.Pattern[str], str, Callable[..., Any]]] = []

    def add(self, method: str, path: str, auth: str, fn: Callable[..., Any]) -> None:
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path)
        self._rows.append((method.upper(), re.compile("^" + pattern + "$"), auth, fn))

    def match(self, method: str, path: str) -> Match | None:
        upper = method.upper()
        for meth, rx, auth, fn in self._rows:
            if meth != upper:
                continue
            hit = rx.match(path)
            if hit:
                return Match(auth, fn, hit.groupdict())
        return None
