# Plan operativo de ingesta batch para Agent1

Objetivo: definir una estrategia repetible de actualizacion de todas las fuentes (bases + referencia)
sin romper la estabilidad del pipeline.

## Alcance total

El batch cubre:

- BOE: `data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv` y derivados históricos.
- PLACE: perfiles + agregación + perfiles de contratante.
- OpenTender: OCDS zip español.
- Datos de apoyo de `datos.gob.es` seleccionados (catálogos de organismo, CPV, convocatorias, adjudicaciones si aplica).

## Regla de arquitectura

1. `data/raw` siempre inmutable por corrida.
2. Cada corrida escribe `manifest/batches/<periodo>/manifest.json` con:
   - fuente,
   - url,
   - hash,
   - fecha de captura,
   - estado (`ok`/`error`),
   - filas parseadas,
   - `source_snapshot_id`.
3. `run-agent1` consume metadatos desde raw o el manifest.
4. Re-procesamiento completo de capa analítica solo cuando cambia hash o cambia esquema.
5. La salida incluye `source_snapshot_id` para permitir seguimiento de derivaciones (por ejemplo, carga en grafo).

## Frecuencia sugerida

### Batch semanal (vigilancia + cobertura de cambios)

- Objetivo: detectar cambios y cubrir deriva temprano.
- Tareas:
  - Revisar cambios en manifest/hash de BOE/PLACE/OpenTender/datos.gob.es.
  - Descargar únicamente si hay cambios.
- `procurewatch place-sources --year <Y> --inspect`.
- `python -m procurewatch doctor`.
- Generar `manifest/batches/<semana>/manifest.json`.
- No reescribir completamente `agent1` si no hay cambios.
- Implementación actual:
  - `procurewatch run-batch --run-mode weekly --year <Y> --cpv-prefix 71`.
  - guarda estado en `data/processed/run_batch_state.json` y `data/manifest/batches/<run_mode>/<batch_id>/manifest.json`.

### Batch mensual (sincronización analítica)

- Objetivo: regenerar base de analisis y cobertura.
- Tareas:
  1. Sincronizar raw de todas las fuentes activas.
  2. Ejecutar normalizacion por fuente (BOE/PLACE/OpenTender).
  3. Ejecutar `run-agent1 --year <Y> --cpv-prefix 71`.
 4. Ejecutar normalizador de datos.gob.es de referencia (catálogos de organismo/CPV/sumarios).
 5. Ejecutar joins de corroboración con catálogos de datos.gob.es en dataset canónico.
 6. Cargar cambios en capa analítica (PostgreSQL/DuckDB).
 7. Ejecutar actualización incremental de Neo4j (solo nodos/capas tocadas).
- Implementación actual:
  - `procurewatch run-batch --run-mode monthly --year <Y> --cpv-prefix 71 --place-download`.
  - el flujo mensual fuerza ejecución de `run-agent1` para regenerar cobertura.

### Batch trimestral (calidad profunda)

- Revisión de deduplicación global.
- Re-calculo completo de `contract_key_canon`.
- Revisión de estabilidad de cobertura y cobertura cruzada.

## Criterios de cierre por batch

- Si no hay cambios de raw, no se valida ni reescribe toda la capa analítica.
- Si hay cambio:
  - `agent1_contract_key_coverage.parquet` y reportes regenerados.
  - validado `agent1_run_report.json`.
  - validación de Neo4j (nodos y relaciones no duplicadas por `batch_id`).

## Diseño de estado para LangGraph

La salida final debe ser tratada como frontera entre agentes:

- `run-agent1` produce:
  - `agent1_run_report.json`
  - `agent1_contract_key_coverage.parquet`
  - `data_quality_report.json`
  - `batch_state` resumido (fuente y snapshot id).
- `batch_state` y `source_snapshot_id` viajan al orquestador LangGraph para decidir:
  - recalcular grafos,
  - recalcular red flags,
  - refrescar fichas de caso.
- Hoy:
  - `run-batch` genera `data/processed/run_batch_state.json` con `changed_sources`,
    `agent1_executed`, y `source_snapshots` por archivo/tabla de entrada.

## Diseño propuesto de Neo4j (etapa 2)

Modelo mínimo recomendado:

- Nodos: `Buyer`, `Supplier`, `Contract`, `CPV`, `Source`, `Award`.
- Relaciones:
  - `(:Buyer)-[:PUBLISHED]->(:Contract)`
  - `(:Contract)-[:AWARDED_TO]->(:Supplier)`
  - `(:Contract)-[:HAS_CPV]->(:CPV)`
  - `(:Contract)-[:FROM_SOURCE]->(:Source)`

Carga eficiente:

- Construir nodos/edges sobre `contracts_*_canonical.parquet`.
- Upsert con `contract_key_canon` + `source_snapshot_id` para idempotencia.
- No reinyectar todo en cada corrida; modo incremental.

## Integracion de datos.gob.es como corroboración

- Etapa 1: usar como referencia de entidades (organos, códigos, catálogos).
- Etapa 2: usar datos de contratación complementaria solo donde haya keys compatibles.
- Evitar mezclar sin normalización contractual: primero armoniza identificadores y solo entonces cruza.

## Criterios de aceptacion de cada batch

- Reproducibilidad:
  - dos corridas sin cambios de raw deben producir mismo esquema y coverage estable.
- Trazabilidad:
  - cada corrida tiene manifest + `agent1_run_report.json` + métricas de deriva.
- Integridad de grafo:
  - no hay duplicados por clave de contrato y batch.
- Cobertura:
  - el enriquecimiento con datos.gob.es no reduce cobertura base.

## Cierre de sesion 31/05/2026

- Agent1 queda optimizado para ejecuciones recurrentes: el flujo normal no reprocesa fuentes ya materializadas.
- La frontera operativa recomendada para la siguiente sesion es:
  - `procurewatch run-agent1 --year 2024 --cpv-prefix 71` para control rapido.
  - `procurewatch run-agent1 --year 2024 --cpv-prefix 71 --force-rebuild` para reconstruccion completa.
- El batch semanal debe apoyarse en esta cache y reservar reconstrucciones completas para cambios de hash, cambios de esquema o auditoria mensual.
- Pendiente de batch: incorporar `source_snapshot_id` a `agent2_contracts_canonical.parquet` y a futuros nodos/edges de grafo.
