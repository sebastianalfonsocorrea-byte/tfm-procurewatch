from __future__ import annotations

from urllib.error import URLError
from urllib.request import urlopen

from procurewatch.settings import Settings

from .chunking import chunk_text
from .qdrant_store import check_qdrant_health
from .schemas import DocumentRef


def check_ollama_health(url: str, *, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with urlopen(url.rstrip("/") + "/api/tags", timeout=timeout) as response:
            return 200 <= response.status < 300, response.read().decode("utf-8", errors="replace")
    except (OSError, URLError) as exc:
        return False, str(exc)


def run_agent4_smoke(*, check_services: bool = False) -> int:
    settings = Settings.from_env()
    sample = DocumentRef(
        document_id="agent4-smoke",
        source="synthetic",
        text="Contrato publico de servicios tecnicos. Evidencia documental para Agent4.",
        contract_key_canon="SMOKE-001",
    )
    chunks = chunk_text(sample, chunk_size=40, overlap=5)

    print("Agent4 smoke")
    print(f"- Modelo Ollama configurado: {settings.ollama_model}")
    print(f"- Chunks generados: {len(chunks)}")

    if not check_services:
        print("- Servicios: no comprobados (usa --check-services tras docker compose up -d)")
        return 0

    qdrant_url = settings.qdrant_url or "http://localhost:6333"
    qdrant_status = check_qdrant_health(qdrant_url)
    print(f"- Qdrant {qdrant_url}: {'OK' if qdrant_status.reachable else 'ERROR'}")

    ollama_url = settings.ollama_base_url or "http://localhost:11434"
    ollama_ok, _detail = check_ollama_health(ollama_url)
    print(f"- Ollama {ollama_url}: {'OK' if ollama_ok else 'ERROR'}")

    return 0 if qdrant_status.reachable and ollama_ok else 1
