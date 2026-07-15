from __future__ import annotations

import json
from typing import Any

CASE_CONTEXT_PROMPT = """Responde solo con evidencia recuperada.
Si no hay evidencia suficiente, indicalo explicitamente.
No declares fraude; describe senales documentales para revision humana.
"""


def build_case_context_prompt(
    *,
    question: str,
    contract_context: dict[str, object],
    evidences: list[dict[str, object]],
    citations: list[str],
) -> str:
    payload: dict[str, Any] = {
        "question": question,
        "contract_context": contract_context,
        "evidences": evidences,
        "citations": citations,
        "required_output": (
            "Redacta un resumen breve para revision humana. Usa solo las evidencias. "
            "Incluye las citas document_id/chunk_id/contract_key_canon relevantes."
        ),
    }
    return (
        CASE_CONTEXT_PROMPT.strip()
        + "\n\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )
