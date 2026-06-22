# Arquitectura objetivo para actualizaciones y grafo de relaciones

Objetivo: definir como evolucionar el sistema para que el mantenimiento futuro sea sistematico y escalable.

## Enfoque recomendado: arquitectura por capas (actual = no cambiar)

1. Layer 0 - Fuente de origen (`data/raw`)
2. Layer 1 - Normalizacion tabular (`data/processed`)
3. Layer 2 - Canonicos analíticos (`data/processed/canonical`)
4. Layer 3 - Almacenamiento analítico (PostgreSQL/DuckDB)
5. Layer 4 - Capa de relaciones (Neo4j)
6. Layer 5 - Indicadores y documentos para agentes

Importante: los cambios propuestos no sustituyen el trabajo actual de Agent1; lo ordenan para escalar.

Estado de implementación:
- `procurewatch run-batch --run-mode weekly|monthly` es la frontera operativa inicial.
- la corrida persiste `source_snapshots`, `changed_sources` y estado de ejecución en
  `data/processed/run_batch_state.json`.

## Batch total de todas las fuentes (propuesta de diseño)

### Alcance total de fuentes

- BOE (full histórico descargado o recarga controlada).
- PLACE:
  - Perfiles de contratante.
  - Agregación.
  - Perfiles de órgano.
- OpenTender OCDS.
- datos.gob.es (catálogo de contratos/organismos/CPV, según priorización).

### Frecuencia y lógica

- Batch semanal:
  - check de cambios por manifiesto/hash en todas las fuentes.
  - refresco de catálogos auxiliares de datos.gob.es cuando cambian.
  - no forzar re-normalizacion completa si no hay cambios.
- Batch mensual:
  - reconstrucción controlada de Layer 1/2 para periodos afectados.
  - carga de cambios en Layer 3 y luego en grafo Layer 4.
- Batch anual (o trimestral) opcional:
  - ventana de calidad profunda y re-procesado total de BOE si varía versión oficial.

### Contratos contractuales para la arquitectura

- `run-batch` -> `run-agent1` sigue siendo el estado base inicial de cobertura.
- `run-batch` publica un objeto `batch_state` con:
  - `batch_id`, `run_mode` (weekly|monthly),
  - `source_snapshot_id` por fuente,
  - `hash`, `rows_in`, `rows_out`, `rejected_rows`,
  - `drift_metrics` contra corrida anterior,
  - `depends_on` (run report anterior).
- `batch_state` es el mensaje de frontera que llega al LangGraph.

## Integracion de Neo4j: cómo hacerlo correctamente

Sí, usar Neo4j para relaciones es una decisión eficiente si la consulta central es transversal por entidad.

### Modelo recomendado (mínimo viable)

Nodos:
- `:Buyer`
- `:Supplier`
- `:Contract`
- `:Procedure`
- `:CPV`
- `:Source`

Relaciones:
- `(:Buyer)-[:PUBLISHED]->(:Contract)`
- `(:Contract)-[:AWARDED_TO]->(:Supplier)`
- `(:Contract)-[:HAS_CPV]->(:CPV)`
- `(:Supplier)-[:PARTNERS_WITH]->(:Supplier)` (si se comparten lotes/compromisos)
- `(:Contract)-[:FROM_SOURCE]->(:Source)`

### Flujo de carga en grafo

1) El contrato pasa a `canonical_parquet`.
2) Se calcula una tabla de `nodes_edges`
   - `nodes_*` y `edges_*`.
3) Se upserta en Neo4j:
   - `MERGE` por clave estable.
   - deduplicado por `source_snapshot_id` y `contract_key_canon`.

### Regla de eficiencia

- No cargar archivo entero en cada corrida.
- Cargar solo cambios incrementales por `batch_id` o por `updated_at`.
- Hacer refresh completo solo en batch mensual profundo o si hay rebase de esquema.

## Riesgo y control de calidad (vigilancia)

- No pasar a scoring ni dashboard con grafo incompleto.
- Toda carga nueva debe validar:
  - nodos creados sin nulos obligatorios,
  - idempotencia por `source_snapshot_id`,
  - consistencia de `contract_key_canon`.

## Cambios recomendados en documentación

- Marcar en AGENTS y PLAN_AGENTE1 que el batch total incluye todas las fuentes.
- Mantener datos.gob.es como fase de enriquecimiento, pero incluido en ciclo de batch.
- Incluir estado de grafo en `agent1_run_report.json` y en reporte de orquestación.

## Estado actualizado 31/05/2026

- Agent1 ya produce una tabla canonica de entrada a siguientes capas:
  - `data/processed/agent2_contracts_canonical.parquet`
  - `data/processed/agent2_contracts_canonical_schema.json`
- La tabla canonica actual tiene 51.720 filas y estado de calidad `ok`.
- La actualizacion incremental de grafo debe construirse sobre esta salida, no sobre los Parquet por fuente.
- Antes de cargar Neo4j conviene resolver el matching entre fuentes: las intersecciones actuales por `contract_key_canon` son 0.
- La proxima capa recomendada es generar `nodes_*` y `edges_*` desde `agent2_contracts_canonical.parquet`, incluyendo `source` y futura `source_snapshot_id`.
- El documento canonico del agente de grafos es [Plan Agent3 grafos](../04_agentes/PLAN_AGENTE3_GRAFOS.md).
