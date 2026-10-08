from __future__ import annotations

from typing import Any

CONTRACT_REQUIRED_FIELDS = (
    "id_contrato",
    "id_licitacion",
    "organismo_contratante",
    "codigo_organismo",
    "nivel_administracion",
    "tipo_contrato",
    "procedimiento",
    "cpv_codigo",
    "cpv_descripcion",
    "importe_estimado",
    "importe_adjudicado",
    "ratio_desviacion_importe",
    "fecha_publicacion",
    "fecha_adjudicacion",
    "dias_resolucion",
    "numero_ofertas_recibidas",
    "id_adjudicatario",
    "nif_adjudicatario",
    "nombre_adjudicatario",
    "score_red_flags_total",
    "red_flags_activados",
    "nivel_riesgo",
    "score_centralidad_red",
    "comunidad_red",
    "fragmentos_documentales_recuperados",
    "fuentes_cruzadas",
    "estado_revision",
)

SUPPLIER_REQUIRED_FIELDS = (
    "nif",
    "nombre",
    "forma_juridica",
    "sector_actividad",
    "total_contratos",
    "total_importe_adjudicado",
    "organismos_distintos",
    "procedimientos_menores_ratio",
    "tasa_adjudicacion_licitacion",
    "score_riesgo_agregado",
    "nivel_centralidad_red",
    "comunidades_participacion",
    "red_flags_recurrentes",
)


def _field(
    data_type: str,
    owner: str,
    *,
    nullable: bool = True,
    allowed_values: tuple[str, ...] = (),
    description: str,
) -> dict[str, Any]:
    return {
        "type": data_type,
        "owner": owner,
        "nullable": nullable,
        "allowed_values": list(allowed_values),
        "description": description,
    }


CONTRACT_SCHEMA = {
    "id_contrato": _field(
        "string",
        "agent1",
        nullable=False,
        description="Identificador canónico y trazable del contrato o adjudicación.",
    ),
    "id_licitacion": _field(
        "string",
        "agent1",
        description="Identificador de la licitación o expediente de origen.",
    ),
    "organismo_contratante": _field(
        "string",
        "agent1",
        nullable=False,
        description="Nombre normalizado del organismo contratante.",
    ),
    "codigo_organismo": _field(
        "string",
        "agent1",
        description="DIR3, NIF u otro identificador oficial disponible.",
    ),
    "nivel_administracion": _field(
        "string",
        "agent1",
        allowed_values=("central", "autonomica", "local"),
        description="Nivel administrativo normalizado.",
    ),
    "tipo_contrato": _field(
        "string",
        "agent1",
        allowed_values=("obras", "servicios", "suministros", "concesion"),
        description="Naturaleza contractual normalizada.",
    ),
    "procedimiento": _field(
        "string",
        "agent1",
        allowed_values=("abierto", "restringido", "negociado", "menor", "emergencia"),
        description="Procedimiento de contratación normalizado.",
    ),
    "cpv_codigo": _field(
        "string",
        "agent1",
        description="Código CPV principal, conservado como texto.",
    ),
    "cpv_descripcion": _field(
        "string",
        "agent1",
        description="Descripción oficial o disponible del código CPV.",
    ),
    "importe_estimado": _field(
        "float",
        "agent1",
        description="Importe estimado normalizado en euros.",
    ),
    "importe_adjudicado": _field(
        "float",
        "agent1",
        description="Importe adjudicado normalizado en euros.",
    ),
    "ratio_desviacion_importe": _field(
        "float",
        "agent1",
        description="Diferencia relativa entre importe adjudicado y estimado.",
    ),
    "fecha_publicacion": _field(
        "date",
        "agent1",
        description="Fecha de publicación en formato ISO 8601.",
    ),
    "fecha_adjudicacion": _field(
        "date",
        "agent1",
        description="Fecha de adjudicación en formato ISO 8601.",
    ),
    "dias_resolucion": _field(
        "integer",
        "agent1",
        description="Días entre publicación y adjudicación.",
    ),
    "numero_ofertas_recibidas": _field(
        "integer",
        "agent1",
        description="Número de ofertas cuando la fuente lo publica.",
    ),
    "id_adjudicatario": _field(
        "string",
        "agent1",
        description="Identificador canónico del adjudicatario.",
    ),
    "nif_adjudicatario": _field(
        "string",
        "agent1",
        description="NIF, NIE o CIF normalizado cuando esté disponible.",
    ),
    "nombre_adjudicatario": _field(
        "string",
        "agent1",
        description="Nombre normalizado del adjudicatario.",
    ),
    "score_red_flags_total": _field(
        "float",
        "agent2",
        description="Puntuación de riesgo entre 0 y 100.",
    ),
    "red_flags_activados": _field(
        "list[string]",
        "agent2",
        description="Códigos de indicadores activados con versión de regla.",
    ),
    "nivel_riesgo": _field(
        "string",
        "agent2",
        allowed_values=("bajo", "medio", "alto", "critico"),
        description="Nivel derivado del score para priorización humana.",
    ),
    "score_centralidad_red": _field(
        "float",
        "agent3",
        description="Métrica de centralidad normalizada calculada sobre el grafo.",
    ),
    "comunidad_red": _field(
        "string",
        "agent3",
        description="Identificador de comunidad del grafo.",
    ),
    "fragmentos_documentales_recuperados": _field(
        "list[string]",
        "agent4",
        description="Referencias trazables a fragmentos documentales recuperados.",
    ),
    "fuentes_cruzadas": _field(
        "list[string]",
        "agent1",
        description="Fuentes en las que se ha identificado el contrato.",
    ),
    "estado_revision": _field(
        "string",
        "frontend",
        allowed_values=("pendiente", "en_revision", "cerrado"),
        description="Estado de revisión humana del caso.",
    ),
}

SUPPLIER_SCHEMA = {
    "nif": _field(
        "string",
        "agent1",
        description="NIF, NIE o CIF normalizado del adjudicatario.",
    ),
    "nombre": _field(
        "string",
        "agent1",
        nullable=False,
        description="Nombre normalizado del adjudicatario.",
    ),
    "forma_juridica": _field(
        "string",
        "agent1",
        description="Forma jurídica cuando exista una fuente fiable.",
    ),
    "sector_actividad": _field(
        "string",
        "agent1",
        description="Sector de actividad disponible o derivado de fuente documentada.",
    ),
    "total_contratos": _field(
        "integer",
        "agent1",
        nullable=False,
        description="Número de contratos asociados al adjudicatario.",
    ),
    "total_importe_adjudicado": _field(
        "float",
        "agent1",
        description="Importe adjudicado acumulado en euros.",
    ),
    "organismos_distintos": _field(
        "integer",
        "agent1",
        nullable=False,
        description="Número de organismos contratantes distintos.",
    ),
    "procedimientos_menores_ratio": _field(
        "float",
        "agent2",
        description="Proporción de contratos menores del adjudicatario.",
    ),
    "tasa_adjudicacion_licitacion": _field(
        "float",
        "agent2",
        description="Tasa de adjudicación sobre licitaciones observables.",
    ),
    "score_riesgo_agregado": _field(
        "float",
        "agent2",
        description="Score agregado del adjudicatario en escala 0-100.",
    ),
    "nivel_centralidad_red": _field(
        "float",
        "agent3",
        description="Nivel de centralidad normalizado del adjudicatario.",
    ),
    "comunidades_participacion": _field(
        "list[string]",
        "agent3",
        description="Comunidades del grafo en las que participa.",
    ),
    "red_flags_recurrentes": _field(
        "list[string]",
        "agent2",
        description="Indicadores recurrentes asociados al adjudicatario.",
    ),
}

ANALYTICAL_SCHEMA = {
    "version": "1.0.0",
    "source": "Propuesta Técnica_SASM.pdf, apartado 5.4",
    "null_policy": (
        "Los campos se declaran aunque la fuente no permita rellenarlos. "
        "Los valores ausentes se conservan como null y su cobertura se mide; no se imputan datos."
    ),
    "entities": {
        "contrato": {
            "primary_key": ["id_contrato"],
            "fields": CONTRACT_SCHEMA,
        },
        "adjudicatario": {
            "primary_key": ["nif", "nombre"],
            "fields": SUPPLIER_SCHEMA,
        },
    },
}
