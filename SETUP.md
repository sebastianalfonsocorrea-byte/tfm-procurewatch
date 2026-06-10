# Setup de desarrollo

Esta guia deja el entorno local preparado para desarrollar ProcureWatch Analytics en Windows con
PowerShell.

## 1. Requisitos base

- Python 3.11 o superior.
- Git.
- PowerShell.
- Docker Desktop cuando se empiecen a usar PostgreSQL, Neo4j y Qdrant.
- Ollama cuando se active la parte de modelos locales.

Comprueba Python:

```powershell
python --version
```

## 2. Crear entorno virtual

```powershell
cd C:\PROYECTOS\tfm_procurewatch
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## 3. Instalar el proyecto

Instalacion recomendada para el primer ciclo de programacion:

```powershell
python -m pip install -e ".[dev,data,graph,frontend]"
```

Instalacion completa para fases posteriores:

```powershell
python -m pip install -e ".[dev,data,db,graph,rag,frontend]"
```

Los extras tienen esta intencion:

- `dev`: pruebas, lint y tipado.
- `data`: pandas, Polars, scraping y machine learning basico.
- `db`: PostgreSQL y migraciones.
- `graph`: NetworkX y Neo4j.
- `rag`: Qdrant, LangGraph, Ollama, spaCy y RAGAS.
- `frontend`: Streamlit, Plotly y PyVis.

Estructura relevante:

- `data/`: datasets reales, muestras y artefactos generados.
- `scr/procurewatch/data_sources/`: codigo para leer BOE, PLACE, OpenTender y fuentes externas.
- `scr/procurewatch/agent1/`, `agent2/`, `agent4/`: logica propia de cada agente.

## 4. Configurar entorno local

```powershell
Copy-Item .env.example .env
```

Edita `.env` solo si vas a arrancar servicios locales. Para el primer ciclo, el comando de
diagnostico funciona sin esos servicios.

## 5. Diagnostico

```powershell
python -m procurewatch doctor
```

El diagnostico comprueba version de Python, carpetas de datos y variables configuradas para
servicios opcionales.

## 6. Normalizar datos BOE

Con el CSV en `data/raw`, ejecuta:

```powershell
procurewatch normalize-boe
```

El comando genera datasets Parquet en `data/processed` y un reporte JSON de calidad.

## 7. Pruebas y calidad

```powershell
python -m pytest tests
python -m ruff check api scr tests
python -m ruff format api scr tests
```

## 8. Servicios locales pendientes

PostgreSQL, Neo4j, Qdrant y Ollama pasan a ser el siguiente bloque de trabajo porque Agent2 y
Agent4 ya necesitan capa de datos, grafo y RAG.

Stack a instalar manualmente en Windows:

- Git for Windows.
- Python 3.11 si no esta instalado.
- Docker Desktop con backend WSL2.
- PostgreSQL local, o PostgreSQL por Docker si se prefiere mantener todo containerizado.
- Neo4j Desktop, o Neo4j Community por Docker.
- Ollama para modelos locales.
- Modelo LLM en Ollama: `qwen3:8b`.
- Modelo alternativo si el equipo no soporta 8B con fluidez: `qwen3:4b` o `mistral`.

Qdrant se recomienda ejecutarlo con Docker, no instalarlo como aplicacion Windows independiente.

Instalacion Python completa del proyecto:

```powershell
cd C:\PROYECTOS\tfm_procurewatch
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,data,db,graph,rag,frontend]"
```

Comandos de descarga/arranque de imagenes cuando Docker este disponible:

```powershell
docker pull postgres:16
docker pull neo4j:5-community
docker pull qdrant/qdrant
```

Modelo local:

```powershell
ollama pull qwen3:8b
ollama pull qwen3:4b
```

Variables `.env` a revisar:

```text
PROCUREWATCH_POSTGRES_DSN=
PROCUREWATCH_NEO4J_URI=
PROCUREWATCH_NEO4J_USER=
PROCUREWATCH_NEO4J_PASSWORD=
PROCUREWATCH_QDRANT_URL=
PROCUREWATCH_OLLAMA_BASE_URL=
PROCUREWATCH_OLLAMA_MODEL=qwen3:8b
```

## 9. Ejecutar Agent1 tras cierre 31/05/2026

Corrida normal optimizada:

```powershell
cd C:\PROYECTOS\tfm_procurewatch
.\.venv\Scripts\Activate.ps1
python -m procurewatch run-agent1 --year 2024 --cpv-prefix 71
```

Reconstruccion completa desde fuentes raw:

```powershell
python -m procurewatch run-agent1 --year 2024 --cpv-prefix 71 --force-rebuild
```

La corrida normal reutiliza cache de BOE/PLACE/OpenTender si ya existen los Parquet y los reportes de calidad asociados. La salida esperada incluye `agent1_run_report.json`, `agent1_data_quality_summary.json`, `agent1_contract_key_coverage.parquet` y `agent2_contracts_canonical.parquet`.

## 10. Siguiente foco: Agent2 y Agent4

Despues de validar Agent1:

```powershell
python -m procurewatch run-agent1 --year 2024 --cpv-prefix 71
```

Continuar con:

- cargar el canonico en PostgreSQL;
- derivar nodos y relaciones para Neo4j;
- preparar coleccion Qdrant `procurement_documents`;
- mantener `scr/procurewatch/agent4/` para LangGraph/RAG;
- plantear Agent2 con red flags v1.
