# Plan de Agent2: red flags y scoring

Objetivo: plantear Agent2 como motor determinista y explicable de red flags, usando el dataset
canonico producido por Agent1 y preparando su posterior uso con PostgreSQL y Neo4j.

## Estado de partida

Entrada actual:

- `data/processed/agent2_contracts_canonical.parquet`
- `data/processed/agent2_contracts_canonical_schema.json`
- `data/processed/agent1_data_quality_summary.json`

Codigo base:

- `scr/procurewatch/agent2/schemas.py`
- `scr/procurewatch/agent2/rules.py`
- `scr/procurewatch/agent2/scoring.py`
- `scr/procurewatch/agent2/pipeline.py`
- `scr/procurewatch/agent2/state.py`

Estado actualizado 23/06/2026:

- Agent2 v1 local implementado.
- Comando disponible:

```powershell
procurewatch run-agent2 --input data/processed/agent2_contracts_canonical.parquet
```

- Salidas locales:
  - `data/processed/agent2_risk_scores.parquet`
  - `data/processed/agent2_risk_flags.parquet`
  - `data/processed/agent2_scoring_report.json`
  - schemas JSON y previews CSV asociados.

Regla de estructura: `data/` guarda datasets y artefactos; `scr/procurewatch/data_sources/`
guarda conectores/parsers externos; `scr/procurewatch/agent2/` guarda la logica de scoring.

El dataset canonico tiene 51.720 filas y estado de calidad `ok`. La ausencia actual de
intersecciones entre BOE/PLACE/OpenTender por `contract_key_canon` no bloquea Agent2, pero limita
las afirmaciones de contraste entre fuentes.

## Alcance v1

Agent2 queda planteado como motor incremental. La v1 local queda cerrada con reglas deterministas
minimas y salidas versionadas; las senales relacionales avanzadas quedan para integrar features de
Agent3.

Entregables minimos:

- Catalogo v1 de red flags, implementado parcialmente.
- Esquema de entrada/salida, implementado en JSON local.
- Decision de columnas obligatorias, derivada del canonico Agent1/Agent2.
- Plan de carga a PostgreSQL.
- Plan de derivacion a Neo4j para relaciones.

## Red flags v1

Prioridad inicial:

- RF-01: concurrencia baja o adjudicatario unico cuando exista dato.
- RF-02: procedimiento restringido, negociado o menor recurrente. Implementado como
  `risky_procedure`.
- RF-03: recurrencia comprador-proveedor.
- RF-04: concentracion de importe por proveedor y comprador.
- RF-05: desviacion entre importe estimado y adjudicado. Implementado como
  `awarded_above_estimate`.
- RF-06: patrones temporales anomalos.
- RF-07: repeticion de CPV, titulos o importes entre contratos cercanos.

Senal de calidad adicional:

- DQ-01: proveedor/adjudicatario ausente. Implementado como `missing_supplier`.

Cada red flag debe producir:

- `risk_flag_id`
- `contract_key_canon`
- `flag_code`
- `severity`
- `confidence`
- `evidence_fields`
- `evidence_text`
- `rule_version`
- `created_at`

## Scoring

El score no declara fraude. Prioriza revision humana.

Salidas minimas:

- `contract_key_canon`
- `risk_score`
- `risk_level`
- `flags_count`
- `top_flags`
- `score_version`
- `source_snapshot_id`

## Uso de PostgreSQL

Tablas destino:

- `risk_flags`
- `risk_scores`
- `agent_outputs`

Mientras PostgreSQL no este cargado, Agent2 puede leer Parquet, pero la salida debe disenar ya
con el esquema relacional final.

## Uso de Neo4j

Neo4j entra cuando haya que calcular patrones relacionales:

- compradores con adjudicatarios recurrentes;
- proveedores conectados por contratos/lotes;
- comunidades de entidades;
- centralidad o concentracion.

## Criterios de aceptacion

- Agent2 puede ejecutarse sobre el canonico sin depender de documentos. Implementado.
- Cada flag es trazable a columnas o evidencias concretas. Implementado.
- El score incluye version de regla y no borra historico. Implementado como artefactos appendables
  por `source_snapshot_id`; la persistencia historica queda para PostgreSQL.
- Las limitaciones de datos faltantes quedan registradas como `confidence` menor o flag no aplicable.

Validacion:

- `python -m pytest tests\test_agent2.py tests\test_agent4.py`
- `python -m ruff check scr\procurewatch\agent2 scr\procurewatch\agent4 tests\test_agent2.py tests\test_agent4.py scr\procurewatch\cli.py`
- `python -m pytest tests`: 57 tests pasados y 5 fallos en Agent1/Batch por permisos de
  `TemporaryDirectory` bajo `C:\Users\salfo\AppData\Local\Temp`; no afecta a Agent2.
