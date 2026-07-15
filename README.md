# ProcureWatch Analytics

ProcureWatch Analytics es el prototipo tecnico del TFM para analizar datos abiertos de
contratacion publica y priorizar casos con posibles patrones de riesgo. El sistema no declara
fraude: calcula senales explicables para apoyar una revision humana.

## Estado actual

El repositorio esta en fase de activacion de capas superiores tras cerrar la base funcional de
Agent1.

### Bitacora tecnica (31/05/2026)

- run-agent1 ejecuta ya una corrida unificada BOE + PLACE + OpenTender.
- Se reforzo la trazabilidad de salida (reportes de cobertura y metadatos de entrada).
- Se registraron parsers versions y checks de integridad (`sha256`, tamaño, fecha).
- PLACE mejora su robustez: reintento de descarga + estado final correcto cuando falla.

### Estado tecnico actual (31/05/2026)

- Orquestador `run-agent1` ya ejecuta:
  - BOE normalizado,
  - PLACE normalizado,
  - OpenTender normalizado.
- Cobertura entre fuentes y reporte agregado:
  - `data/processed/agent1_contract_key_coverage.parquet`
  - `data/processed/agent1_contract_key_coverage_preview.csv`
  - `data/processed/agent1_run_report.json`
- Descargas PLACE con reintento y validaciones de estado, incluyendo hash y estado final correcto de fallo.
- Trazabilidad reforzada en reportes con sha256 de los ficheros de entrada y version de parsers.

Resumen base:

- Configuracion Python instalable desde `pyproject.toml`.
- Paquete inicial `procurewatch` bajo `scr/`.
- Comando de diagnostico `procurewatch doctor`.
- Pruebas minimas para validar configuracion y CLI.
- Documentacion inicial de setup y arquitectura.

## Estructura

```text
api/                 Futuro backend o capa de consulta.
data/raw/            Datos originales descargados.
data/processed/      Datos normalizados y listos para analisis.
data/synthetic/      Datos pequenos de prueba o demos.
data/processed_sample/ Salidas de prueba separadas de la corrida completa.
deployment/          Docker y despliegue local.
docs/                Planificacion, memoria y documentacion metodologica.
frontend/            Dashboard Streamlit y visualizaciones.
models/              Artefactos de modelos locales o entrenados.
notebooks/           Exploracion reproducible.
scr/procurewatch/    Codigo Python importable del proyecto.
scr/procurewatch/agent1/ Pipeline de ingesta/canonizacion.
scr/procurewatch/agent2/ Red flags y scoring.
scr/procurewatch/agent3/ Futuro analisis de grafos y relaciones.
scr/procurewatch/agent4/ NLP/RAG/LangGraph.
scr/procurewatch/data_sources/ Conectores/parsers de fuentes externas.
tests/               Pruebas automatizadas.
```

Regla de estructura: `data/` contiene datos y artefactos generados; `scr/procurewatch/data_sources/`
contiene codigo para leer fuentes externas; `scr/procurewatch/agentN/` contiene la logica propia
de cada agente.

## Documentacion operativa obligatoria para continuidad

- `AGENTS.md` (contexto tecnico para nuevas sesiones).
- `docs/README.md` (indice navegable de documentacion).
- `docs/03_agent1_ingesta/PLAN_AGENTE1_PIPELINE.md` (estado y flujo del agente 1).
- `docs/04_agentes/PLAN_AGENTE2_SCORING.md` (planteamiento de red flags y scoring).
- `docs/04_agentes/PLAN_AGENTE3_GRAFOS.md` (grafos, Neo4j, NetworkX y relaciones).
- `docs/04_agentes/PLAN_AGENTE4_RAG_LANGGRAPH.md` (estructura Agent4 con NLP/RAG/LangGraph).
- `docs/04_agentes/SEGUIMIENTO_AGENTES.md` (seguimiento transversal de agentes).
- `docs/01_arquitectura/PLAN_CAPA_DATOS_AGENTES.md` (PostgreSQL, Neo4j, Qdrant e IDs comunes).
- `docs/03_agent1_ingesta/PLAN_INGESTA_BATCH_AGENT1.md` (batch semanal/mensual + actualización total).
- `docs/01_arquitectura/ARQUITECTURA_BATCH_Y_GRAFOS.md` (arquitectura de updates y Neo4j).
- `docs/02_fuentes/FUENTES_DATOS_Y_ROADMAP.md` (fuentes y prioridades).
- `docs/00_vision/STACK_TECNICO_PROYECTO.md` (stack Python + servicios + flujo técnico completo).

## Arranque rapido

Desde PowerShell:

```powershell
cd C:\PROYECTOS\tfm_procurewatch
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,data,graph,frontend]"
python -m procurewatch doctor
python -m pytest tests
```

Para fases con PostgreSQL, Neo4j, Qdrant, Ollama o RAG, instala tambien los extras
correspondientes:

```powershell
python -m pip install -e ".[dev,data,db,graph,rag,frontend]"
```

## Variables de entorno

Copia `.env.example` a `.env` y ajusta valores locales si vas a usar servicios externos. No
subas credenciales ni datos sensibles al repositorio.

## Objetivo tecnico del siguiente bloque

Agent1 queda como base cerrada para construir capas superiores. El foco inmediato pasa a preparar
la capa de datos y arrancar Agent2/Agent4:

- plantear Agent2 con red flags, scoring, entradas y salidas explicables;
- plantear Agent3 como capa de grafos y relaciones derivada del canonico;
- trabajar Agent4 a fondo: scraping/NLP/RAG, Qdrant, Ollama y LangGraph;
- preparar PostgreSQL como capa canonica estructurada;
- preparar Neo4j como capa derivada para relaciones;
- preparar Qdrant como indice documental semantico;
- mantener `agent2_contracts_canonical.parquet` como frontera actual entre Agent1 y siguientes capas;
- seguir mejorando el matching entre fuentes antes de afirmar contraste real entre BOE/PLACE/OpenTender.

Comandos de control diario:

```powershell
procurewatch place-sources --year 2024 --datasets place_profiles place_aggregation place_buyer_profiles --inspect
procurewatch normalize-place --inputs data/raw/place/profiles/licitacionesPerfilesContratanteCompleto3_2024.zip data/raw/place/aggregation/PlataformasAgregadasSinMenores_2024.zip --cpv-prefix 71
procurewatch normalize-opentender --input data/raw/opentender/data-es-ocds-json.zip --year 2024 --cpv-prefix 71
procurewatch normalize-boe
procurewatch run-agent1 --year 2024 --cpv-prefix 71
```

Para pruebas rapidas de desarrollo, usar siempre limites y un directorio de salida separado. Esto
evita sobrescribir los Parquet productivos de `data/processed` con una muestra parcial:

```powershell
procurewatch make-agent1-sample --rows 1000 --overwrite
procurewatch run-agent1 --boe-input data/synthetic/agent1_sample/boe_sample.csv --opentender-input data/synthetic/agent1_sample/opentender_2024_sample.zip --place-inputs data/synthetic/agent1_sample/licitacionesPerfilesContratanteCompleto3_2024_sample.zip data/synthetic/agent1_sample/PlataformasAgregadasSinMenores_2024_sample.zip --output-dir data/processed_sample --year 2024 --cpv-prefix 71
```

Estandar recomendado: `tests/` debe trabajar con fixtures pequenos o `TemporaryDirectory`; smoke
tests locales pueden usar 500-5.000 filas por fuente; la corrida completa queda para validacion
nocturna, mensual o antes de congelar resultados del TFM.

La corrida normal de `run-agent1` debe reutilizar `data/processed` si ya fue construido desde raw.
Solo se vuelve a leer y parsear raw completo con `--force-rebuild`, cambios de fuente/esquema o
batch mensual/validacion final.

Checklist de control para la corrida de hoy:

- Confirmar que `run-agent1 --year 2024 --cpv-prefix 71` reproduce artefactos clave.
- Revisar estabilidad de `agent1_contract_key_coverage.parquet` (sin variaciones masivas sin causa).
- Verificar que `agent1_run_report.json` incluye metadata de entrada para cada fuente.

## Roadmap inmediato (despues de hoy)

- Cerrar ajustes de normalizacion de clave compuesta para bajar no-cases.
- Añadir validaciones de calidad por bloque de cobertura.
- Conectar `agent1` con el orquestador LangGraph del bloque 4.
- Preparar dataset de entrada canónico para Agent2 con columnas estrictas.
- Diseñar y revisar batch total + capa Neo4j con actualizaciones incrementales.

Hoy puedes ejecutar el flujo del Agente 1 completo:

```powershell
procurewatch run-agent1 --year 2024 --cpv-prefix 71
```

Si es la primera ejecucion y quieres refrescar PLACE desde el manifiesto:

```powershell
procurewatch run-agent1 --year 2024 --cpv-prefix 71 --place-download
procurewatch run-batch --run-mode weekly --year 2024 --cpv-prefix 71
procurewatch run-batch --run-mode monthly --year 2024 --cpv-prefix 71 --place-download --place-datasets place_profiles place_aggregation
```

El comando genera ademas:

- `data/processed/contracts_place.parquet`
- `data/processed/contracts_place_cpv71.parquet`
- `data/processed/contracts_opentender_2024.parquet`
- `data/processed/contracts_opentender_2024_cpv71.parquet`
- `data/processed/agent1_contract_key_coverage.parquet`
- `data/processed/agent1_run_report.json`

```bash
python -m unittest tests.test_agent1 tests.test_cli
python -m py_compile scr/procurewatch/agent1/pipeline.py scr/procurewatch/data_sources/{boe,opentender,place,place_normalize}.py
```

## Cierre de sesion (31/05/2026)

La base operativa del Agente 1 queda cerrada. `run-agent1` ya procesa BOE, PLACE y OpenTender, genera cobertura, resumen de calidad y dataset canonico para Agent2.

Estado final observado:

- Corrida valida: `procurewatch run-agent1 --year 2024 --cpv-prefix 71`.
- Corrida normal con cache: ~23 segundos.
- Reconstruccion completa disponible con `--force-rebuild`.
- `agent1_data_quality_summary.json`: estado `ok`.
- `agent2_contracts_canonical.parquet`: 51.720 filas.
- Validacion actual de la rama integrada: `120 passed`, `1 skipped`; Ruff sin errores. La prueba
  omitida corresponde a la integracion PostgreSQL cuando no esta instalado el extra `db`.

Artefactos de continuidad:

- `data/processed/agent1_run_report.json`
- `data/processed/agent1_contract_key_coverage.parquet`
- `data/processed/agent1_data_quality_summary.json`
- `data/processed/agent2_contracts_canonical.parquet`
- `data/processed/agent2_contracts_canonical_schema.json`

Siguiente trabajo: mejorar matching entre fuentes. La cobertura existe, pero las intersecciones BOE/PLACE/OpenTender siguen en 0 con la clave actual.

## Evaluacion reproducible de Agent2

La muestra versionada de 3.437 contratos permite ejecutar RF-01 a RF-06 y comparar la sensibilidad
de los umbrales numericos:

```powershell
procurewatch evaluate-agent2
```

El comando genera tres escenarios (`lower`, `base`, `upper`) con factores 0,9, 1,0 y 1,1, junto
con scores, flags y los reportes:

- `data/processed_sample/agent2_evaluation/agent2_evaluation_report.json`
- `data/processed_sample/agent2_evaluation/agent2_evaluation_report.md`

La evaluacion registra cobertura por regla, campos ausentes, frecuencias, distribucion del score y
estabilidad frente al escenario base. Es una evaluacion proxy sobre la muestra reproducible; no
sustituye la ejecucion pendiente sobre el canonico completo de 51.720 contratos ni valida fraude.

## Evaluacion de diez fichas de caso

Las fichas cualitativas reutilizan el escenario base de Agent2 y las relaciones calculadas por
Agent3 sobre la misma muestra. Primero se generan las features relacionales y despues las fichas:

```powershell
procurewatch run-agent3 `
  --input data/processed_sample/agent2_contracts_canonical.parquet `
  --output-dir data/processed_sample/agent3_case_studies
procurewatch evaluate-case-studies
```

La seleccion reproducible incluye cinco contratos con score maximo, tres de riesgo medio y dos
controles sin flags. Cada ficha JSON/Markdown conserva fuente, importes, procedimiento, reglas,
evidencias, relaciones y advertencias. El corpus actual no contiene documentos asociados a esos
diez contratos, por lo que la ausencia documental queda registrada y no se sustituye por contenido
sintetico. Los artefactos agregados son:

- `data/processed_sample/case_studies/case_studies_report.json`
- `data/processed_sample/case_studies/case_studies_report.md`

El benchmark incorpora `integration.case_studies.traceable`; las fichas evaluan priorizacion y
explicacion para revision humana y no declaran fraude.
