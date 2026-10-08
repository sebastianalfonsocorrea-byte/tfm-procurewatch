# Plan de Agent2: red flags y scoring

Objetivo: plantear Agent2 como motor determinista y explicable de red flags, usando el dataset
canonico producido por Agent1 y preparando su posterior uso con PostgreSQL y Neo4j.

## Estado de partida

Entrada actual:

- `data/processed/agent2_contracts_canonical.parquet`
- `data/processed/agent2_contracts_canonical_schema.json`
- `data/processed/agent1_data_quality_summary.json`

Codigo base:

- `src/procurewatch/agent2/schemas.py`
- `src/procurewatch/agent2/rules.py`
- `src/procurewatch/agent2/scoring.py`
- `src/procurewatch/agent2/pipeline.py`
- `src/procurewatch/agent2/state.py`

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

Unificacion del scoring (v3.0.0, 09/10/2026):

- Agent2 tiene un unico modelo: `run-agent2` (alias `run-agent2-mvp`) ejecuta RF-01..RF-06 con
  score 0-100 (pesos RF-01=15, RF-02=20, RF-03=20, RF-04=20, RF-05=25, RF-06=15; suma 115,
  recortada a 100) y niveles `bajo` (<25), `medio` (25-49), `alto` (50-74) y `critico` (>=75).
- Se elimina el scoring v1 (0-1, `missing_supplier`/`risky_procedure`/`awarded_above_estimate`).
  Agent4 usa la misma funcion `score_contract`, que evalua las reglas locales del contrato
  (RF-01, RF-02, RF-05, RF-06); RF-03/RF-04 requieren el lote completo.
- DQ-01 (adjudicatario ausente) se separa del riesgo: se publica en `agent2_risk_flags` con
  severidad `calidad_dato` y en la columna `data_quality_flags`, pero no suma al score.
  RF-01 queda reservado a expedientes con un unico adjudicatario.
- Salidas: `agent2_risk_scores.parquet`, `agent2_risk_flags.parquet` y `agent2_run_report.json`.

Integracion `integration/multiagent` (historico):

- Se conserva `run-agent2` como contrato estable de `sebas`, usado por Agent4 para scoring
  determinista compatible.
- Se incorpora el MVP de `Satu` como `run-agent2-mvp`, con reglas RF-01..RF-06, scoring 0-100,
  umbral configurable para RF-05 y salidas trazables en los mismos artefactos de riesgo.
- La separacion evita romper imports y consumidores existentes mientras se valida el encaje entre
  Agent1/2 y Agent3/4 en la rama de laboratorio.

Regla de estructura: `data/` guarda datasets y artefactos; `src/procurewatch/data_sources/`
guarda conectores/parsers externos; `src/procurewatch/agent2/` guarda la logica de scoring.

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
- RF-02: procedimiento negociado, menor o de emergencia recurrente para el comprador.
- RF-03: recurrencia comprador-proveedor.
- RF-04: concentracion de importe por proveedor y comprador.
- RF-05: importe adjudicado superior al estimado en mas del umbral (10 % por defecto).
- RF-06: patrones temporales anomalos.
- RF-07: repeticion de CPV, titulos o importes entre contratos cercanos.

Senal de calidad adicional:

- DQ-01: proveedor/adjudicatario ausente. Se informa como calidad del dato y no suma al score.

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
- `python -m ruff check src\procurewatch\agent2 src\procurewatch\agent4 tests\test_agent2.py tests\test_agent4.py src\procurewatch\cli.py`
- `python -m pytest tests`: 122 pruebas superadas y 1 omitida en el entorno minimo por faltar
  SQLAlchemy para la integracion PostgreSQL opcional; con SQLAlchemy disponible se observan
  123 pruebas superadas sin omisiones.
- `python -m ruff check api src tests frontend`: sin errores.

## Evaluacion de sensibilidad 15/07/2026

El comando `evaluate-agent2` ejecuta RF-01 a RF-06 sobre la muestra reproducible de 3.437
contratos. Compara los umbrales numericos con factores 0,9, 1,0 y 1,1 y publica artefactos en
`data/processed_sample/agent2_evaluation/`.

Resultados del escenario base (regenerados con el scoring unificado v3.0.0, 09/10/2026):

- 3.437 contratos puntuados; 3.425 parcialmente evaluables, 12 no evaluables y ninguno
  completamente evaluable.
- 1.250 contratos con alguna senal de riesgo y 1.316 flags de riesgo, mas 1.104 senales DQ-01 de
  calidad del dato (adjudicatario ausente) que no puntuan.
- Frecuencias: RF-01=0, RF-02=12, RF-03=730, RF-04=34, RF-05=540 y RF-06=0.
- Cobertura de evaluabilidad: RF-01=0 % (la muestra no conserva `source_tender_id`), RF-02=99,65 %,
  RF-03=67,88 %, RF-04=42,04 %, RF-05=52,25 % y RF-06=0 %.
- Distribucion: 2.187 contratos sin flags de riesgo, 684 en riesgo bajo positivo, 553 en medio,
  13 en alto y ninguno en critico.
- Score medio: 8,44 sobre 100.
- Frente a la version 2.0.0, los niveles de riesgo no cambian: las 1.104 activaciones de RF-01
  eran todas por adjudicatario ausente y ahora se reportan como DQ-01.
- Score sin cambios frente al escenario base: 99,80 % con factor 0,9 y 95,11 % con factor 1,1.

RF-06 no es evaluable en la muestra porque ninguna fila conserva simultaneamente fecha de
publicacion y fecha de adjudicacion validas. La evaluacion es proxy, no usa etiquetas de fraude y
queda pendiente repetirla sobre el canonico completo de 51.720 contratos.

## Diez fichas cualitativas 15/07/2026

La evaluacion complementaria genera diez fichas desde el escenario base: cinco casos de score
maximo, tres de riesgo medio y dos controles. Las 21 activaciones de reglas seleccionadas tienen
evidencia trazable y los diez casos incorporan contexto relacional de Agent3. La falta de documentos
asociados en el corpus actual se publica como limitacion y no se interpreta como fallo del scoring
ni como ausencia de riesgo.
