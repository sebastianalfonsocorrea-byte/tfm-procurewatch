# Plan practico del Agent 1

Objetivo: dejar una base reproducible para el `agent1` que consuma varias fuentes de contratacion y entregue tablas limpias para contraste entre BOE, PLACE y OpenTender.

Ubicacion de codigo: `scr/procurewatch/agent1/pipeline.py`, reexportado desde
`scr/procurewatch/agent1/__init__.py` para conservar `from procurewatch.agent1 import run_agent1`.

Modelo analítico objetivo: `scr/procurewatch/agent1/analytical_schema.py`, documentado en
`docs/MODELO_DATOS_ANALITICO.md`.

Nota de lectura para memoria: este plan mezcla diseño, estado parcial y tareas en curso. Para
redactar resultados conviene contrastarlo con `docs/BASE_MEMORIA_TFM.md` y `SEGUIMIENTO_AGENT1.md`.

## Estado al 31/05/2026

Resumen de lo hecho en la sesion del 31/05/2026:

- `procurewatch run-agent1` funciona como orquestador de 3 fuentes:
  - BOE normalizado.
  - PLACE normalizado (descarga opcional desde manifiesto).
  - OpenTender normalizado (OCDS dentro de ZIP).
- Trazabilidad mejorada:
  - Metadatos de input en `agent1_run_report.json` (`sha256`, `size_bytes`, `modified_utc`).
  - Versiones de parser registradas (`agent1`, `boe`, `place`, `opentender`).
  - Artefacto de cobertura (`contract_key_canon`) por fuente.
- Robustez de descargas PLACE mejorada:
  - Reintentos en descarga con backoff breve.
  - `downloaded=False` cuando falla el intento final.
  - Limpieza de fichero temporal tras error.
- Salidas de cobertura disponibles:
  - `data/processed/agent1_contract_key_coverage.parquet`
  - `data/processed/agent1_contract_key_coverage_preview.csv`
  - Estadisticas de presencia y cruces entre fuentes.

Bitacora de decisiones de la sesion:

- Se prioriza primero la clave canónica estable y rastreable (`contract_key_canon`) y luego la calidad de señal.
- `agent1_run_report.json` se define como artefacto de frontera entre Agent1 y la capa LangGraph.
- No se amplía número de fuentes esta semana para evitar fragilidad del pipeline base.

Pendiente para el siguiente ciclo:

- Revisar normalizacion de `contract_key_canon` para reducir no-cases por diferencias de texto.
- Añadir validaciones automaticas de tipos/campos criticos en el reporte final de cobertura.
- Integrar reporte de agente en el flujo de orquestacion LangGraph de 4 agentes.
- Mejorar el contrato canonico de Agent2 solo si cambian los criterios de scoring.
- Si el matching entre fuentes sigue sin producir intersecciones útiles, documentarlo como
  limitación reproducible del canónico actual en lugar de forzar coincidencias artificiales.

Checklist de cierre del ciclo:

- [ ] `data_quality_report.json` presente para BOE/PLACE/OCDS en la misma corrida.
- [ ] `agent1_contract_key_coverage.parquet` y `agent1_contract_key_coverage_preview.csv` regeneran de forma estable.
- [ ] Política de normalizacion de texto para `contract_key_canon` documentada en el informe de método.
- [x] `agent1_data_quality_summary.json` mide completitud OCDS, validez fiscal y coherencia temporal.

## 1) Formato recomendado para ingesta interna

Para este proyecto el formato de salida recomendado es:
- `Parquet` para dataset procesado (alto rendimiento y tipado).
- `CSV` solo como preview.
- `JSON` para reportes de calidad.

### Reglas clave

- Los archivos crudos (`raw`) se mantienen tal cual.
- La salida normalizada conserva:
  - identificadores fuente,
  - fechas normalizadas,
  - importes numericos,
  - CPV,
  - identificadores de adjudicatario y organismo.
- Los contratos CPV 71 se filtran en capas `*_cpv71.parquet` sin perder historico completo.

## 2) Fuentes que si entran en Agent 1

### Fuente principal ya descargada

- BOE: `data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv`
- OpenTender: descarga directa desde `https://opentender.eu/es/download`
  y almacenamiento temporal en `data/raw/opentender/` durante la ejecución.
- PLACE: `data/raw/place/` con:
  - `profiles/licitacionesPerfilesContratanteCompleto3_2024.zip`
  - `aggregation/PlataformasAgregadasSinMenores_2024.zip`
  - `buyer_profiles/place_buyer_profiles.xlsx`
- Referencias de soporte en `data/raw/reference_docs`:
  - `DGPE_PLACSP_ResumenDatosAbiertos.pdf`
  - `especificacion-sindicacion.pdf`

### Datasets de datos.gob.es a priorizar en esta fase

- Perfiles de contratante de PLACSP.
- Licitaciones publicadas sin contratos menores.
- Encargos a medios propios.
- Consultas preliminares de mercado.
- Catálogos de organismos / unidades de contratación (para codificación homogénea).
- Catálogos de CPV y entidades para validaciones de referencia.

Nota de descarte temprano:

- En esta fase se descartan datasets de agregados macro sin campos contractuales clave, salvo que aporten relaciones de entidad.

## 3) Orquestacion minima (estado actual)

1. Ingesta controlada
   - Mantener manifiesto de fuentes (URL + ruta local + SHA256 + fecha de captura).
   - Registrar cada refresco o cambio de fuente.

2. Normalizacion
   - `normalize-boe` -> `contracts_boe.parquet` y `contracts_boe_cpv71.parquet`.
   - `normalize-place` -> `contracts_place.parquet` y `contracts_place_cpv71.parquet`.
   - `normalize-opentender` -> `contracts_opentender_<anio>.parquet` y `contracts_opentender_<anio>_cpv71.parquet`.
   - `run-agent1` ejecuta los 3 y consolida reportes.
   - Si los artefactos procesados ya existen y el hash/fuente coincide, `run-agent1` reutiliza cache para evitar reprocesar BOE/PLACE/OpenTender.
   - Para reconstruccion completa se usa `--force-rebuild`.

3. Calidad y trazabilidad
   - `data_quality_report.json` por parser.
   - Reporte de entrada en `agent1_run_report.json`:
     - metadatos de artefactos,
     - rutas,
     - versiones de parser.
   - La corrida normal no debe volver a parsear `data/raw` si los Parquet procesados y reportes
     existentes siguen siendo reutilizables. El raw completo se reserva para primera carga,
     cambios de fuente/esquema o reconstrucciones forzadas.

4. Cruce BOE vs PLACE vs OpenTender
   - Construccion de clave compuesta `contract_key_canon`.
   - Cobertura por presencia de clave:
     - solo BOE,
     - solo PLACE,
     - solo OpenTender,
     - presente en las 3.
   - Salida:
     - `agent1_contract_key_coverage.parquet`
     - `agent1_contract_key_coverage_preview.csv`

5. Preparacion para Agent 2
   - Dataset de scoring recibe solo columnas canonicas:
     - buyer,
     - procedimiento,
     - fechas,
     - importes,
     - CPV,
     - adjudicatario,
     - fuente.

## 4) Comandos recomendados

```bash
procurewatch place-sources --year 2024 --datasets place_profiles place_aggregation place_buyer_profiles --download --overwrite
procurewatch normalize-place --inputs data/raw/place/profiles/licitacionesPerfilesContratanteCompleto3_2024.zip data/raw/place/aggregation/PlataformasAgregadasSinMenores_2024.zip --cpv-prefix 71
procurewatch normalize-opentender --input data/raw/opentender/data-es-ocds-json.zip --year 2024 --cpv-prefix 71
procurewatch normalize-boe
procurewatch run-agent1 --year 2024 --cpv-prefix 71
procurewatch run-agent1 --year 2024 --cpv-prefix 71 --force-rebuild
```

Para validacion de cambios locales:

```bash
python -m unittest tests.test_agent1 tests.test_cli
python -m py_compile scr/procurewatch/agent1/pipeline.py scr/procurewatch/data_sources/{boe,opentender,place,place_normalize}.py
```

Para desarrollo rapido con muestras:

```bash
procurewatch make-agent1-sample --rows 1000 --overwrite
procurewatch run-agent1 \
  --boe-input data/synthetic/agent1_sample/boe_sample.csv \
  --opentender-input data/synthetic/agent1_sample/opentender_2024_sample.zip \
  --place-inputs data/synthetic/agent1_sample/licitacionesPerfilesContratanteCompleto3_2024_sample.zip data/synthetic/agent1_sample/PlataformasAgregadasSinMenores_2024_sample.zip \
  --output-dir data/processed_sample \
  --year 2024 \
  --cpv-prefix 71
```

Regla operativa:

- `data/raw`: snapshot completo e inmutable.
- `data/processed`: resultado real de la corrida completa.
- `data/synthetic/agent1_sample`: muestras reproducibles para tests de desarrollo.
- `data/processed_sample`: salidas de prueba; nunca se usan como evidencia final del TFM.
- `scr/procurewatch/data_sources`: conectores/parsers; no almacena datos.
- `scr/procurewatch/agent1`: logica propia de Agent1.
- No usar `--force-rebuild` salvo cambios de parser, cambios de fuente, auditoria o cierre de
  resultados.

## 5) Plan de ingesta recurrente

Para evitar correr manualmente fuentes todos los dias se propone un ciclo doble:

- Batch semanal: checks de cambio por manifiesto y salud de pipelines.
- Batch mensual: descarga controlada, normalizacion completa y corrida de `run-agent1`.
- Batch total: incluye todas las fuentes base + catalogos de datos.gob.es para corroboración.
- Futuro incremental: incorporar datos nuevos por `source_snapshot_id` y regenerar solo las capas
  tocadas; el grafo y las red flags deberian recibir deltas, no una recarga completa en cada run.

Ver el plan detallado en:

- [docs/PLAN_INGESTA_BATCH_AGENT1.md](PLAN_INGESTA_BATCH_AGENT1.md)

La propuesta de grafos y actualizacion de Neo4j para relaciones esta definida en:

- [docs/ARQUITECTURA_BATCH_Y_GRAFOS.md](ARQUITECTURA_BATCH_Y_GRAFOS.md)

La continuacion hacia Agent2, Agent4 y capa de datos esta definida en:

- [docs/PLAN_CAPA_DATOS_AGENTES.md](PLAN_CAPA_DATOS_AGENTES.md)
- [docs/PLAN_AGENTE2_SCORING.md](PLAN_AGENTE2_SCORING.md)
- [docs/PLAN_AGENTE3_GRAFOS.md](PLAN_AGENTE3_GRAFOS.md)
- [docs/PLAN_AGENTE4_RAG_LANGGRAPH.md](PLAN_AGENTE4_RAG_LANGGRAPH.md)

## 6) Como explicarlo en la metodologia del TFM

Para trazabilidad del TFM, documentar siempre:

- Fecha de snapshot por fuente.
- Checks de integridad (`sha256`).
- Version de parsers.
- Politica de deduplicacion y normalizacion de claves.
- Excepciones de parsing y sus justificaciones.
- Criterios de actualización de grafo y uso de datos de apoyo (`datos.gob.es`).

## 7) Politica formal de normalizacion, deduplicacion y salida Agent2

### Normalizacion de claves

- La clave `contract_key_canon` se construye por fuente con identificadores contractuales fuertes cuando existen.
- BOE usa `file_number`, `buyer_name` y `publication_date`, con `contract_id` como fallback.
- PLACE usa `contract_folder_id`, `buyer_dir3` y `published_date`, con `source_entry_id` como fallback.
- OpenTender usa `source_record_id`, `buyer_name` y `publication_date`, con `source_entry_id` como fallback.
- Antes de comparar, los textos pasan a mayusculas, sin espacios, sin tildes y sin caracteres ajenos a identificadores (`A-Z`, `0-9`, guion, barra baja y barra).
- Las fechas se reducen a forma compacta `YYYYMMDD` cuando la fuente aporta fecha parseable.

### Politica operativa de `contract_key_canon`

La clave canónica no pretende inventar una identidad nueva; su función es homogeneizar la identidad
que ya traen las fuentes para poder comparar, deduplicar y trazar contratos entre sistemas.

Prioridad de campos:

1. identificadores contractuales explícitos de la fuente;
2. identificadores de expediente o carpeta;
3. combinaciones estables de comprador, fecha y objeto cuando no exista identificador fuerte;
4. fallback técnico de la fuente si todavía no hay una combinación suficiente.

Criterios de equivalencia:

- dos filas solo se consideran equivalentes si comparten la misma clave canónica normalizada;
- diferencias menores de formato no deben crear claves distintas si representan el mismo identificador;
- si faltan campos críticos y no se puede construir una clave estable, la fila queda trazada pero no se fuerza el match.

Qué pasa si falta información:

- si falta el identificador fuerte, se baja al siguiente nivel de prioridad;
- si la fuente no aporta campos suficientes para una clave segura, la fila mantiene su trazabilidad
  intra-fuente pero no se usa como prueba de cruce inter-fuente;
- el resultado debe documentarse como ausencia de evidencia suficiente, no como coincidencia negativa.

Trazabilidad del cruce:

- el pipeline conserva la fuente de origen, el identificador original y la clave canónica;
- las intersecciones entre fuentes se reportan explícitamente en cobertura;
- si el cruce sigue sin producir intersecciones útiles, eso se registra como limitación reproducible del canonico y no se interpreta como fallo del agente de scoring.
- el diagnóstico agregado de cobertura se guarda en `agent1_contract_key_coverage_diagnostics.json`
  y resume cuántas filas pudieron construir clave primaria, cuántas dependieron de fallback y
  cuántas quedaron sin clave suficiente por fuente.

### Deduplicacion

- PLACE conserva la version mas reciente por `contract_folder_id` o `source_entry_id`.
- OpenTender conserva la version mas reciente por `source_record_id` y filtra CPV antes de materializar la tabla final.
- Agent2 recibe una tabla sin duplicados por `source`, `source_record_id` y `contract_key_canon`.
- La ausencia de intersecciones útiles entre BOE, PLACE y OpenTender no invalida la tabla canónica;
  solo indica que el criterio de cruce debe tratarse como frontera trazable y no como prueba de
  identidad compartida entre fuentes.

### Contrato estricto para Agent2

La salida canonica es:

- `data/processed/agent2_contracts_canonical.parquet`
- `data/processed/agent2_contracts_canonical_preview.csv`
- `data/processed/agent2_contracts_canonical_schema.json`

Columnas obligatorias para scoring inicial:

- `contract_key_canon`
- `source`
- `buyer_name`
- `publication_date`
- `cpv_codes_raw`

Columnas permitidas como nulas porque dependen de la fuente:

- `source_record_id`
- `source_dataset`
- `buyer_id`
- `supplier_name`
- `supplier_id`
- `contract_title`
- `procedure`
- `award_date`
- `estimated_value_eur`
- `awarded_value_eur`
- `cpv_code_list`
- `source_file`

### Validaciones minimas de cierre Agent1

- `agent1_run_report.json` debe existir tras la corrida.
- `agent1_contract_key_coverage.parquet` debe existir y contener universo de claves por fuente.
- `agent2_contracts_canonical.parquet` debe existir y tener filas.
- `agent1_data_quality_summary.json` debe registrar cobertura de campos criticos y duplicados por clave.
- Dos ejecuciones sin cambios de raw no deben cambiar el esquema del dataset canonico ni las columnas del contrato.

## 8) Estado final de la sesion 31/05/2026

- Corrida valida: `procurewatch run-agent1 --year 2024 --cpv-prefix 71`.
- Reconstruccion completa: `procurewatch run-agent1 --year 2024 --cpv-prefix 71 --force-rebuild`.
- Tiempo observado con cache: ~23 segundos.
- Calidad: `data/processed/agent1_data_quality_summary.json` en `ok`.
- Filas canonicas Agent2: 51.720.
- Cobertura actual:
  - BOE: 7.867 claves.
  - PLACE: 18.797 claves.
  - OpenTender: 25.057 claves.
  - Universo: 51.721 claves.
  - Intersecciones: 0.
- Nota tecnica: la ausencia de intersecciones no bloquea Agent2, pero si debe tratarse antes de afirmar contraste real entre fuentes.
