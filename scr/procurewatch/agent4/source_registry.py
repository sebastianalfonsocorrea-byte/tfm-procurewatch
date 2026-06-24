from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

AGENT4_SOURCE_REGISTRY = "agent4_source_registry"
AGENT4_SOURCE_REGISTRY_VERSION = "0.1.0"
DEFAULT_AGENT4_SOURCE_REGISTRY_PATH = Path("data/processed/agent4_source_registry.json")

AGENT4_SCOPE = (
    "Agent4 es el agente documental/RAG del sistema. En el MVP trabaja sobre "
    "documentos locales, sinteticos o descargados de forma explicita, extrae texto, "
    "lo fragmenta, recupera evidencias y genera una ficha explicable con citas para "
    "revision humana."
)

DOCUMENT_SOURCE_POLICY: tuple[str, ...] = (
    "No hace crawling ni navegacion web automatizada en el MVP.",
    "No descarga pliegos ni anexos de PLACSP automaticamente.",
    "Solo descarga documentos remotos cuando se invoca un comando explicito.",
    "La descarga remota implementada se limita a anuncios BOE-B HTML individuales.",
    "El corpus por defecto sigue siendo local/sintetico para pruebas reproducibles.",
)

IMPLEMENTED_IN_MVP: tuple[str, ...] = (
    "Carga documentos locales .txt, .html y .md.",
    "Convierte HTML a texto con BeautifulSoup si esta disponible o html.parser como fallback.",
    "Divide documentos en chunks trazables.",
    "Genera embeddings deterministas offline para tests y ejecuciones reproducibles.",
    "Puede usar Ollama para embeddings/generacion si se activan servicios.",
    "Puede indexar y consultar Qdrant si esta disponible.",
    "Recupera evidencia textual relacionada con un contrato.",
    (
        "Genera ficha explicable con contrato, score, flags, metricas Agent3, "
        "evidencias, citas y warnings."
    ),
    "Registra fuentes oficiales BOE/PLACSP como hoja de ruta tecnica trazable.",
    "Descarga anuncios BOE-B HTML individuales cuando el usuario proporciona una URL concreta.",
)

NOT_IMPLEMENTED_IN_MVP: tuple[str, ...] = (
    "Scraping en vivo masivo de BOE o PLACSP.",
    "Navegacion automatizada por webs.",
    "Descarga automatica de pliegos, anexos o resoluciones desde PLACSP.",
    "Pipeline NLP principal cerrado con spaCy.",
    "Extraccion compleja de entidades juridicas en documentos reales.",
    "Evaluacion RAGAS completa sobre corpus documental amplio.",
    "Corpus documental real amplio mantenido por Agent4.",
)

OFFICIAL_SOURCE_ENTRIES: tuple[dict[str, object], ...] = (
    {
        "source_id": "boe_html_individual",
        "block": "BOE anuncios HTML",
        "resource": "Anuncio individual BOE-B",
        "url": "https://www.boe.es/diario_boe/txt.php?id=BOE-B-YYYY-NNNNN",
        "use_for_agent4": (
            "Scraping HTML puntual con BeautifulSoup/html.parser de anuncios concretos."
        ),
        "access_mode": "explicit_single_url_fetch",
        "mvp_status": "implemented_limited",
    },
    {
        "source_id": "boe_open_data_api",
        "block": "BOE API",
        "resource": "API de datos abiertos BOE",
        "url": "https://www.boe.es/datosabiertos/api/api.php",
        "use_for_agent4": "Descubrir sumarios y documentos BOE reutilizables.",
        "access_mode": "official_api_reference",
        "mvp_status": "registered_future_integration",
    },
    {
        "source_id": "boe_summary_by_date",
        "block": "BOE sumario por fecha",
        "resource": "Endpoint de sumario BOE",
        "url": "https://www.boe.es/datosabiertos/api/boe/sumario/AAAAMMDD",
        "use_for_agent4": (
            "Obtener documentos publicados un dia concreto y enlaces a HTML, XML y PDF."
        ),
        "access_mode": "official_api_reference",
        "mvp_status": "registered_future_integration",
    },
    {
        "source_id": "boe_section_v_a",
        "block": "BOE Seccion V.A",
        "resource": "Contratacion del Sector Publico en BOE",
        "url": "https://www.boe.es/",
        "use_for_agent4": "Fuente oficial de anuncios de contratacion publica.",
        "access_mode": "official_site_reference",
        "mvp_status": "registered_reference",
    },
    {
        "source_id": "placsp_open_data_general",
        "block": "PLACE/PLACSP datos abiertos",
        "resource": "Licitaciones publicadas en la Plataforma de Contratacion del Sector Publico",
        "url": (
            "https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/"
            "Paginas/licitaciones_plataforma_contratacion.aspx"
        ),
        "use_for_agent4": "Pagina madre de datos abiertos PLACSP.",
        "access_mode": "official_open_data_reference",
        "mvp_status": "registered_reference",
    },
    {
        "source_id": "placsp_buyer_profiles",
        "block": "PLACSP perfiles contratante",
        "resource": "Licitaciones publicadas en perfiles del contratante",
        "url": (
            "https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/"
            "Paginas/LicitacionesContratante.aspx"
        ),
        "use_for_agent4": "Dataset principal para licitaciones ordinarias publicadas en PLACSP.",
        "access_mode": "official_open_data_reference",
        "mvp_status": "registered_future_integration",
    },
    {
        "source_id": "placsp_aggregation",
        "block": "PLACSP agregacion",
        "resource": "Licitaciones publicadas mediante mecanismos de agregacion",
        "url": (
            "https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/"
            "Paginas/LicitacionesAgregacion.aspx"
        ),
        "use_for_agent4": "Dataset para entidades que publican mediante agregacion.",
        "access_mode": "official_open_data_reference",
        "mvp_status": "registered_future_integration",
    },
    {
        "source_id": "placsp_minor_contracts",
        "block": "PLACSP contratos menores",
        "resource": "Contratos menores publicados en perfiles del contratante",
        "url": (
            "https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/"
            "Paginas/ContratosMenores.aspx"
        ),
        "use_for_agent4": (
            "Fuente complementaria para contratos menores y patrones de baja cuantia."
        ),
        "access_mode": "official_open_data_reference",
        "mvp_status": "registered_future_integration",
    },
    {
        "source_id": "placsp_own_resources",
        "block": "PLACSP encargos a medios propios",
        "resource": "Encargos a medios propios publicados en perfiles del contratante",
        "url": (
            "https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/"
            "Paginas/EncargosMediosPropios.aspx"
        ),
        "use_for_agent4": "Fuente especifica para encargos a medios propios.",
        "access_mode": "official_open_data_reference",
        "mvp_status": "registered_future_integration",
    },
    {
        "source_id": "placsp_market_consultations",
        "block": "PLACSP consultas preliminares",
        "resource": "Consultas preliminares de mercado",
        "url": (
            "https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/"
            "Paginas/ConsultasPreliminaresMercado.aspx"
        ),
        "use_for_agent4": "Fuente complementaria para fases previas del ciclo de contratacion.",
        "access_mode": "official_open_data_reference",
        "mvp_status": "registered_future_integration",
    },
    {
        "source_id": "placsp_operational_web",
        "block": "PLACSP plataforma web",
        "resource": "Plataforma de Contratacion del Sector Publico",
        "url": "https://contrataciondelestado.es/",
        "use_for_agent4": "Consulta operativa de expedientes, anuncios, pliegos y resoluciones.",
        "access_mode": "manual_web_reference",
        "mvp_status": "registered_reference",
    },
    {
        "source_id": "placsp_syndication_spec",
        "block": "PLACSP especificacion tecnica",
        "resource": "Especificacion del mecanismo de sindicacion",
        "url": "https://contrataciondelsectorpublico.gob.es/datosabiertos/especificacion-sindicacion.pdf",
        "use_for_agent4": "Entender estructura Atom/XML y reutilizacion de datos PLACSP.",
        "access_mode": "official_pdf_reference",
        "mvp_status": "registered_reference",
    },
    {
        "source_id": "placsp_dataset_summary",
        "block": "PLACSP resumen datasets",
        "resource": "Resumen de contenido en conjuntos de datos abiertos",
        "url": (
            "https://www.hacienda.gob.es/DGPatrimonio/plataforma_contratacion/"
            "resumen-datos-abiertos.pdf"
        ),
        "use_for_agent4": (
            "Documentar campos disponibles: expediente, objeto, importe, CPV y pliegos."
        ),
        "access_mode": "official_pdf_reference",
        "mvp_status": "registered_reference",
    },
    {
        "source_id": "placsp_contracting_authorities",
        "block": "PLACSP organos contratantes",
        "resource": "Fichero de organos de contratacion alojados en PLACSP",
        "url": "https://contrataciondelsectorpublico.gob.es/datosabiertos/OrganosContratacion.xlsx",
        "use_for_agent4": "Listado XLSX de organos de contratacion alojados en PLACSP.",
        "access_mode": "official_xlsx_reference",
        "mvp_status": "registered_reference",
    },
    {
        "source_id": "datos_gob_placsp_catalog",
        "block": "datos.gob.es catalogo",
        "resource": "Catalogo de perfiles de contratante PLACSP",
        "url": (
            "https://datos.gob.es/es/catalogo/e05250001-perfiles-de-contratante-de-los-"
            "organos-de-contratacion-alojados-en-la-plataforma-de-contratacion-del-sector-publico"
        ),
        "use_for_agent4": "Catalogo reutilizable para dataset de organos/perfiles de contratante.",
        "access_mode": "official_catalog_reference",
        "mvp_status": "registered_reference",
    },
)


def build_agent4_capabilities() -> dict[str, object]:
    return {
        "scope": AGENT4_SCOPE,
        "document_source_policy": list(DOCUMENT_SOURCE_POLICY),
        "implemented_in_mvp": list(IMPLEMENTED_IN_MVP),
        "not_implemented_in_mvp": list(NOT_IMPLEMENTED_IN_MVP),
    }


def build_agent4_source_registry() -> dict[str, Any]:
    sources = copy.deepcopy(list(OFFICIAL_SOURCE_ENTRIES))
    return {
        "dataset": AGENT4_SOURCE_REGISTRY,
        "version": AGENT4_SOURCE_REGISTRY_VERSION,
        "source_count": len(sources),
        "capabilities": build_agent4_capabilities(),
        "sources": sources,
    }


def build_agent4_source_registry_summary() -> dict[str, object]:
    registry = build_agent4_source_registry()
    return {
        "dataset": registry["dataset"],
        "version": registry["version"],
        "source_count": registry["source_count"],
        "implemented_source_ids": [
            str(source["source_id"])
            for source in registry["sources"]
            if source.get("mvp_status") == "implemented_limited"
        ],
        "registered_source_ids": [str(source["source_id"]) for source in registry["sources"]],
    }


def write_agent4_source_registry(
    output_path: Path = DEFAULT_AGENT4_SOURCE_REGISTRY_PATH,
) -> dict[str, Any]:
    registry = build_agent4_source_registry()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return registry


__all__ = [
    "AGENT4_SCOPE",
    "AGENT4_SOURCE_REGISTRY",
    "AGENT4_SOURCE_REGISTRY_VERSION",
    "DEFAULT_AGENT4_SOURCE_REGISTRY_PATH",
    "DOCUMENT_SOURCE_POLICY",
    "IMPLEMENTED_IN_MVP",
    "NOT_IMPLEMENTED_IN_MVP",
    "OFFICIAL_SOURCE_ENTRIES",
    "build_agent4_capabilities",
    "build_agent4_source_registry",
    "build_agent4_source_registry_summary",
    "write_agent4_source_registry",
]
