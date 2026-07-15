from __future__ import annotations

import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .document_loader import load_html_document
from .schemas import DocumentRef

DEFAULT_BOE_HTML_OUTPUT_DIR = Path("data/raw/agent4/boe_html")
BOE_HTML_SOURCE = "boe_html"
BOE_HTML_SOURCE_ID = "boe_html_individual"
BOE_HTML_NETLOC = "www.boe.es"
BOE_HTML_PATH = "/diario_boe/txt.php"
BOE_B_ID_RE = re.compile(r"^BOE-B-\d{4}-\d{1,6}$")


def extract_boe_b_id(url: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != BOE_HTML_NETLOC
        or parsed.path != BOE_HTML_PATH
    ):
        raise ValueError(
            "La URL debe apuntar a https://www.boe.es/diario_boe/txt.php?id=BOE-B-YYYY-NNNNN"
        )

    query = parse_qs(parsed.query, keep_blank_values=False)
    if set(query) != {"id"} or len(query["id"]) != 1:
        raise ValueError("La URL BOE debe contener un unico parametro id.")

    boe_id = query["id"][0]
    if not BOE_B_ID_RE.fullmatch(boe_id):
        raise ValueError("El parametro id debe tener formato BOE-B-YYYY-NNNNN.")
    return boe_id


def fetch_boe_html_document(
    *,
    url: str,
    contract_key_canon: str,
    output_dir: Path = DEFAULT_BOE_HTML_OUTPUT_DIR,
    timeout: float = 30.0,
) -> DocumentRef:
    boe_id = extract_boe_b_id(url)
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "ProcureWatch-Agent4/0.1 TFM",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            charset = _response_charset(response)
    except (HTTPError, URLError, OSError) as exc:
        raise RuntimeError(f"No se pudo descargar el anuncio BOE {boe_id}: {exc}") from exc

    html = body.decode(charset or "utf-8", errors="replace")
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{boe_id}.html"
    html_path.write_text(html, encoding="utf-8")

    document = load_html_document(
        html_path,
        source=BOE_HTML_SOURCE,
        contract_key_canon=contract_key_canon,
        source_record_id=boe_id,
    )
    return DocumentRef(
        document_id=document.document_id,
        source=document.source,
        text=document.text,
        contract_key_canon=document.contract_key_canon,
        source_record_id=document.source_record_id,
        document_type=document.document_type,
        text_hash=document.text_hash,
        metadata={
            **document.metadata,
            "boe_id": boe_id,
            "source_url": url,
            "source_registry_id": BOE_HTML_SOURCE_ID,
            "downloaded_bytes": str(len(body)),
        },
    )


def build_boe_html_fetch_report(document: DocumentRef) -> dict[str, object]:
    return {
        "dataset": "agent4_boe_html_fetch",
        "source": document.source,
        "source_registry_id": document.metadata.get("source_registry_id"),
        "source_url": document.metadata.get("source_url"),
        "source_record_id": document.source_record_id,
        "contract_key_canon": document.contract_key_canon,
        "document_id": document.document_id,
        "document_type": document.document_type,
        "text_hash": document.text_hash,
        "path": document.metadata.get("path"),
        "downloaded_bytes": document.metadata.get("downloaded_bytes"),
        "html_parser": document.metadata.get("html_parser"),
    }


def _response_charset(response: object) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is not None and hasattr(headers, "get_content_charset"):
        charset = headers.get_content_charset()
        if charset:
            return str(charset)
    return None


__all__ = [
    "BOE_B_ID_RE",
    "BOE_HTML_SOURCE",
    "BOE_HTML_SOURCE_ID",
    "DEFAULT_BOE_HTML_OUTPUT_DIR",
    "build_boe_html_fetch_report",
    "extract_boe_b_id",
    "fetch_boe_html_document",
]
