# Stack Tecnologico del Proyecto (Estado actual y objetivo)

Este documento recoge el stack completo del proyecto, lo que está implementado hoy y lo que está definido como objetivo técnico para el TFM.

Nota de lectura:

- las secciones "implementada hoy" describen estado real del repo;
- las secciones "objetivo" o "roadmap" describen direccion tecnica, no cierre final;
- para preparar la memoria conviene cruzarlo con `docs/BASE_MEMORIA_TFM.md`.

## 1) Objetivo del stack

ProcureWatch Analytics está construido como un sistema de analitica aplicada:

- Ingesta y limpieza de datos abiertos de contratacion publica.
- Generacion de un modelo analitico base (Agent1).
- Preparacion para capas posteriores: scoring, grafos, RAG y explicabilidad.
- Trazabilidad fuerte (raw immutable + metadatos + reportes).

## 2) Pila base de Python (implementada hoy)

### 2.1 Runtime

- Python: `>=3.11` (recomendado 3.11).
- Gestor de proyecto: `pyproject.toml` (PEP 621).
- Empaquetado: `setuptools` + `wheel`.
- Script CLI: `procurewatch` (entrypoint definido en `[project.scripts]`).

### 2.2 Dependencias instalables

En `pyproject.toml`, las dependencias estan separadas por extras:

- `dev`
  - `mypy`
  - `pytest`
  - `ruff`
- `data`
  - `beautifulsoup4`
  - `lxml`
  - `pandas`
  - `polars`
  - `pyarrow`
  - `requests`
  - `scikit-learn`
- `db`
  - `alembic`
  - `psycopg[binary]`
  - `sqlalchemy`
- `graph`
  - `neo4j`
  - `networkx`
  - `python-louvain`
- `rag`
  - `langchain`
  - `langgraph`
  - `ollama`
  - `qdrant-client`
  - `ragas`
  - `spacy`
- `frontend`
  - `plotly`
  - `pyvis`
  - `streamlit`
- `all`: combina todos los grupos anteriores.

Instalacion recomendada inicial:

```powershell
python -m pip install -e ".[dev,data,graph,frontend]"
```

Instalacion completa de stack:

```powershell
python -m pip install -e ".[dev,data,db,graph,rag,frontend]"
```

### 2.3 Librerias ya usadas por codigo actual

- Standard library:
  - `argparse`, `json`, `hashlib`, `pathlib`, `datetime`, `dataclasses`, `re`, `csv`, `zipfile`,
    `unittest`, etc.
- Proyecto:
  - `pandas` para limpieza y serializacion principal.
  - `pyarrow` para lectura/escritura Parquet.
  - `requests` para descarga HTTP de fuentes PLACE.
  - `beautifulsoup4` / `lxml` (definidas como objetivo y auxiliares para scraping y parseo HTML/XML).

## 3) Estructura de codigo (scr/)

### 3.1 CLI y orquestacion local

- `scr/procurewatch/cli.py`
  - Comandos base:
    - `doctor`
    - `normalize-boe`
    - `place-sources`
    - `normalize-place`
    - `normalize-opentender`
    - `run-agent1`
    - `run-batch`
  - `run-batch` imprime también la ruta del `freeze_manifest.json` cuando la ejecución es
    mensual o forzada; ese manifiesto es el artefacto de referencia para el cierre reproducible
    del TFM.
- `scr/procurewatch/__main__.py`
  - Ejecuta `procurewatch` como entrada estandar.

### 3.2 Configuracion

- `scr/procurewatch/settings.py`
  - Variables de entorno:
    - `PROCUREWATCH_DATA_DIR`
    - `PROCUREWATCH_RAW_DATA_DIR`
    - `PROCUREWATCH_PROCESSED_DATA_DIR`
    - `PROCUREWATCH_SYNTHETIC_DATA_DIR`
    - `PROCUREWATCH_MODELS_DIR`
    - Servicios opcionales:
      - `PROCUREWATCH_POSTGRES_DSN`
      - `PROCUREWATCH_NEO4J_URI`
      - `PROCUREWATCH_NEO4J_USER`
      - `PROCUREWATCH_NEO4J_PASSWORD`
      - `PROCUREWATCH_QDRANT_URL`
      - `PROCUREWATCH_OLLAMA_BASE_URL`
      - `PROCUREWATCH_OLLAMA_MODEL`

### 3.3 Fuentes y normalizadores

Estos modulos son codigo, no almacenamiento de datasets. Los datos reales y artefactos generados
viven bajo `data/`.

- `scr/procurewatch/data_sources/boe.py`
  - Parser del CSV BOE
  - Limpieza de fechas, CPV, importes y campos clave
  - Output principal: `contracts_boe*.parquet` y `data_quality_report.json`
- `scr/procurewatch/data_sources/place.py`
  - Manifest + descargas de PLACE.
- `scr/procurewatch/data_sources/place_normalize.py`
  - Parser de ZIP/Atom/XML de PLACE.
  - Output principal: `contracts_place*.parquet` y `contracts_place_quality.json`
- `scr/procurewatch/data_sources/opentender.py`
  - Parser de OCDS JSON (OpenTender)
  - Output principal: `contracts_opentender*.parquet` y calidad.

### 3.4 Pipeline de Agent1

- `scr/procurewatch/agent1/pipeline.py`
  - Ejecuta BOE + PLACE + OpenTender en un flujo unico.
  - Construye cobertura de claves (`contract_key_canon`) y exporta:
    - `agent1_contract_key_coverage.parquet`
    - `agent1_contract_key_coverage_preview.csv`
    - `agent1_run_report.json`
- `scr/procurewatch/agent1/__init__.py`
  - Reexporta la API publica para mantener `from procurewatch.agent1 import run_agent1`.

### 3.5 Agent2

- `scr/procurewatch/agent2/`
  - Scaffold de schemas, reglas, scoring y estado para red flags.

### 3.6 Agent3

- `scr/procurewatch/agent3/` (previsto)
  - Capa de grafos y relaciones desde el canonico o PostgreSQL.
  - Plan detallado en `docs/PLAN_AGENTE3_GRAFOS.md`.

### 3.7 Batch orchestration

- `scr/procurewatch/batch.py`
  - `run_batch` para operación recurrente semanal/mensual.
  - Snapshot de fuentes por hash (`sha256`) para detectar cambios.
  - Reejecución de Agent2 cuando cambia el canónico o cuando el lote es mensual/forzado.
  - `freeze_manifest.json` para congelar el resultado mensual/final sin duplicar artefactos pesados.
  - Estado persistido:
    - `data/processed/run_batch_state.json`
    - `data/manifest/batches/<run_mode>/<batch_id>/manifest.json`

## 4) Almacenamiento y formatos de datos

### 4.1 Capas de datos

- `data/raw/`: inmutable (input original descargado).
- `data/processed/`: limpio y modelado.
- `data/tmp/`: temporal de trabajo para descargas o descompresiones intermedias; se limpia al
  terminar y no se versiona.
- `data/processed_sample/`: salidas de prueba.
- `data/synthetic/`: datos de prueba/demos.

Regla de separacion: `data/` guarda datasets y artefactos; `scr/procurewatch/data_sources/`
guarda conectores/parsers; `scr/procurewatch/agentN/` guarda logica de agente.

### 4.2 Formatos concretos

- Entrada principal: CSV/ZIP/XML/JSON.
- Procesado principal: Parquet (`.parquet`) + CSV de preview.
- Reportes:
  - JSON estructurado de calidad y cobertura.

### 4.3 Convenciones de trazabilidad

- Cada corrida guarda metadatos de artefactos:
  - rutas
  - fecha de creacion
  - hash sha256
  - versiones de parser.
- `agent1` y `batch` usan `sha256` para seguimiento de cambios.

## 5) Stack objetivo de analitica avanzada (propuesto / en fase de roadmap)

### 5.1 Persistencia analitica

- PostgreSQL:
  - tablas de hechos y dimensiones para scoring y auditoria.
- DuckDB (opcional) para analisis local rapido y reproducible.

Decision corregida:

- DuckDB consulta Parquet y ayuda a preparar datasets.
- PostgreSQL conserva el modelo estructurado canonico para agentes, dashboard y auditoria.
- DuckDB no es una fase obligatoria para "pasarlo todo" a PostgreSQL.

### 5.2 Grafos

- Neo4j como grafo de relaciones `Buyer-Supplier-Contract-CPV-Source`.
- NetworkX para metricas de grafo en scripts y analisis local.

### 5.3 NLP y RAG

- OCR + parsing de documentos (PDF/HTML/TXT) para ampliar evidencia.
- Vector store: Qdrant.
- Embeddings + recuperacion semantica para ficha explicativa.
- Coleccion inicial: `procurement_documents`.
- Payload obligatorio: `contract_key_canon`, `document_id`, `chunk_id`, `source`, `text`.

### 5.4 LLM y orquestacion multiagente

- LLM local vía Ollama:
  - Objetivo: `qwen3:8b` o `mistral` para explicación / ayuda analítica.
- LangGraph (estado y flujo de nodos).
- LangChain como capa de tooling/conectores.

Estructura objetivo de Agent4:

```text
scr/procurewatch/agent4/
  state.py
  graph.py
  nodes.py
  document_loader.py
  chunking.py
  embeddings.py
  qdrant_store.py
  retrieval.py
  schemas.py
```

### 5.5 Frontend

- Streamlit para tablero analítico.
- Plotly para graficos.
- Pyvis/Sigma para visualizacion de grafos.

## 6) Flujo tecnico recomendado

1. `doctor` para validar entorno.
2. Descargas normalizadas con `place-sources` o `run-batch`.
3. `run-batch` semanal/mensual para control de cambios.
4. `run-agent1` si hay cambios o forzado.
5. Revisión de reportes de calidad y cobertura.
6. (Futuro) Cargar en PostgreSQL, grafo Neo4j y vector store.

## 7) Estados de uso (practico)

- Desarrollo y demos: `run-agent1`, `run-batch`, `procurewatch doctor`.
- TFM defensivo (arquitectura): explicar:
  - reproducibilidad (raw inmutable)
  - versionado de entrada (`sha256`)
  - orquestacion por capas y por estado (`run_batch_state.json`)
  - separación entre determinista (reglas) y explicativo (LLM).

## 8) Estado real vs objetivo en este momento

### Implementado hoy
- Parser BOE, parser PLACE, parser OpenTender, cobertura base y batch inicial.
- CLI unificada y reportes de evidencia.

### Pendiente en roadmap
- Almacen persistente PostgreSQL y carga de capas analiticas.
- Capa Agent3/Neo4j operativa + grafos de relacion.
- RAG/NLP documental completo con Qdrant.
- FastAPI para capa de servicion.

## 9) Stack manual para el PC

Instalar manualmente:

- Git for Windows.
- Python 3.11.
- Docker Desktop con WSL2.
- PostgreSQL local o contenedor `postgres:16`.
- Neo4j Desktop o contenedor `neo4j:5-community`.
- Qdrant por Docker: `qdrant/qdrant`.
- Ollama.
- Modelos Ollama: `qwen3:8b` y, como reserva ligera, `qwen3:4b` o `mistral`.

Instalar dentro del venv:

```powershell
python -m pip install -e ".[dev,data,db,graph,rag,frontend]"
```

## Cierre de sesion 31/05/2026

Implementado y verificado:

- Agent1 incremental con cache por fuente y reconstruccion opcional mediante `--force-rebuild`.
- PLACE optimizado con filtrado temprano CPV 71 y progreso.
- OpenTender optimizado con prefiltro CPV y extraccion de CPV desde `tender.items`.
- Dataset canonico Agent2:
  - `data/processed/agent2_contracts_canonical.parquet`
  - `data/processed/agent2_contracts_canonical_schema.json`
- Resumen de calidad Agent1:
  - `data/processed/agent1_data_quality_summary.json`
- Estado de calidad: `ok`.
- Pendiente principal: mejora de matching entre fuentes; actualmente la cobertura cruzada BOE/PLACE/OpenTender no encuentra intersecciones con la clave canonica actual.
