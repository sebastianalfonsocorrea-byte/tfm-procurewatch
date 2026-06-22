# Seguimiento Operativo del Proyecto

Objetivo: registrar avances del pipeline para trazabilidad del TFM y reproducibilidad de decisiones.

## 31/05/2026

### Hecho

- run-agent1 quedo operativo como orquestador minimo de 3 fuentes: BOE, PLACE y OpenTender.
- Cobertura entre fuentes habilitada:
  - `data/processed/agent1_contract_key_coverage.parquet`
  - `data/processed/agent1_contract_key_coverage_preview.csv`
- Reporte de ejecucion unificado:
  - `data/processed/agent1_run_report.json` (sha256, tamano, fecha, versiones de parsers).
- PLACE ahora tiene retry en descarga, `downloaded=False` al fallo final y limpieza de temporal.
- `PARSER_VERSION = "1.0.0"` incorporado en boe, place y opentender.
- `run-batch` implementado como frontera operativa semanal/mensual:
  - comando `procurewatch run-batch`.
  - persistencia de estado en `data/processed/run_batch_state.json`.
  - manifest detallado por ejecución en `data/manifest/batches/<run_mode>/<batch_id>/manifest.json`.
  - lógica idempotente semanal: si no cambia hash/tamaño de fuentes críticas, se salta `run-agent1`.
- documentado stack técnico completo en `docs/00_vision/STACK_TECNICO_PROYECTO.md`.

### Decisiones

- Mantener `Parquet` como almacenamiento base procesado.
- Mantener `CSV` solo como preview humana y auditoria rapida.
- En vez de añadir mas fuentes ahora, estabilizar primero la normalizacion de `contract_key_canon`.
- Priorizar trazabilidad y calidad antes de integrar LLM/heuristicas avanzadas.

### Riesgos

- Posibles falsos negativos en cobertura por diferencias textuales y de formato de fechas entre fuentes.
- El ajuste de normalizacion puede cambiar la tasa de overlap y aparentar mejora sin valor real.
- Faltan pruebas de estabilidad de calidad para toda la corrida end-to-end con pandas en este entorno de pruebas.

### Acciones siguientes

- Ajustar limpieza de texto/fechas para `contract_key_canon` y medir mejora de cobertura.
- Aniadir tests de no-deriva entre ejecuciones para dataset Agent1.
- Integrar el output de Agent1 a estado LangGraph de la capa orquestadora.
- Documentar politicas de normalizacion y exclusiones en `docs/03_agent1_ingesta/PLAN_AGENTE1_PIPELINE.md`.
- Ampliar tests de integración con escenarios de batch (skip/resync semanal y ejecución mensual).

## 01/06/2026 (previsto)

### Objetivo

- Cerrar el bloque de calidad final de Agent1.
- Dejar protocolo de ejecucion reproducible en docs de agente.
- Preparar dataset canonico estricto para Agent2.

## Registro de trazabilidad de documentacion actualizada

- `docs/03_agent1_ingesta/PLAN_AGENTE1_PIPELINE.md` (estado, checklist, fuentes y flujo).
- `docs/02_fuentes/FUENTES_DATOS_Y_ROADMAP.md` (fuentes utiles + priorizacion datos.gob.es).
- `docs/03_agent1_ingesta/SEGUIMIENTO_AGENT1.md` (log de decisiones y riesgos).
- `README.md` (estado tecnico, comandos de control y proximos pasos).
- `data/processed/agent1_run_report.json` (metadatos de corrida).
- `docs/03_agent1_ingesta/PLAN_INGESTA_BATCH_AGENT1.md` (modelo semanal/mensual de refresh y propuesta de integración datos.gob.es).

## Cierre real de sesion 31/05/2026

### Hecho adicional

- PLACE perfiles 2024 procesado con filtrado temprano CPV 71:
  - 633.995 entradas inspeccionadas.
  - 49.918 candidatas CPV 71.
  - 12.611 registros deduplicados CPV 71 cuando se ejecuto solo `profiles`.
- PLACE agregacion 2024 procesado con filtrado temprano CPV 71:
  - 242.265 entradas inspeccionadas.
  - 23.606 candidatas CPV 71.
  - 6.359 registros deduplicados CPV 71 cuando se ejecuto solo `aggregation`.
- `run-agent1` optimizado con cache por fuente:
  - reutiliza `contracts_boe*.parquet`, `contracts_place*.parquet` y `contracts_opentender*.parquet` si coinciden fuentes y reportes.
  - `--force-rebuild` fuerza reconstruccion completa.
- `run-agent1 --year 2024 --cpv-prefix 71` ejecutado correctamente tras optimizacion.
- Tiempo observado de corrida normal con cache: ~23 segundos.
- `agent1_data_quality_summary.json` queda en estado `ok`.
- `agent2_contracts_canonical.parquet` generado con 51.720 filas.
- Tests ejecutados:
  - `python -m unittest tests.test_agent1 tests.test_batch`
  - Resultado historico: 5 tests OK. Ver seguimiento general para la validacion actual.

### Artefactos finales

- `data/processed/agent1_run_report.json`
- `data/processed/agent1_contract_key_coverage.parquet`
- `data/processed/agent1_contract_key_coverage_preview.csv`
- `data/processed/agent1_data_quality_summary.json`
- `data/processed/agent2_contracts_canonical.parquet`
- `data/processed/agent2_contracts_canonical_preview.csv`
- `data/processed/agent2_contracts_canonical_schema.json`

### Siguiente sesion

- Prioridad 1: mejorar matching entre BOE, PLACE y OpenTender; las intersecciones actuales son 0.
- Prioridad 2: fijar pruebas de no-deriva para cobertura y schema canonico.
- Prioridad 3: conectar `agent2_contracts_canonical.parquet` con el primer set de red flags.
