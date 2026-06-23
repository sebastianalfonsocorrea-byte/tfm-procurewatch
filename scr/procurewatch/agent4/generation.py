from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from .embeddings import DEFAULT_OLLAMA_BASE_URL

DEFAULT_OLLAMA_LLM_MODEL = "qwen3:8b"


@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    provider: str
    model: str


class OllamaGenerationClient:
    provider = "ollama"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_LLM_MODEL,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> GenerationResult:
        response = self._post_json(
            "/api/generate",
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                },
            },
        )
        text = str(response.get("response") or "").strip()
        if not text:
            raise ValueError("Ollama returned an empty response")
        return GenerationResult(text=text, provider=self.provider, model=self.model)

    def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError) as exc:
            raise ConnectionError(f"Ollama generation endpoint is not reachable: {exc}") from exc
