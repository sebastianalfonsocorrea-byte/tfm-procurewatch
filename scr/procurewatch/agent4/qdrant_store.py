from __future__ import annotations

from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen


@dataclass(frozen=True, slots=True)
class QdrantStatus:
    url: str
    reachable: bool
    detail: str


def check_qdrant_health(url: str, *, timeout: float = 3.0) -> QdrantStatus:
    health_url = url.rstrip("/") + "/health"
    try:
        with urlopen(health_url, timeout=timeout) as response:
            detail = response.read().decode("utf-8", errors="replace").strip()
            return QdrantStatus(url=url, reachable=200 <= response.status < 300, detail=detail)
    except (OSError, URLError) as exc:
        return QdrantStatus(url=url, reachable=False, detail=str(exc))
