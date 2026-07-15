# ProcureWatch Agents Playbook

Este documento sirve como punto de arranque para cualquier nueva conversacion tecnica.

## Contexto rapido (31/05/2026)

- Objetivo activo: activar capa de datos para Agent2 y Agent4 tras cierre funcional de Agent1.
- Estado actual funcional:
  - `procurewatch run-agent1` orquesta BOE + PLACE + OpenTender.
  - `agent1_run_report.json` y reportes de cobertura por clave canonical ya estan activos.
  - `procurewatch run-batch` ya publica el estado de corrida semanal/mensual en `data/processed/run_batch_state.json`.
  - `agent2_contracts_canonical.parquet` ya existe como frontera para Agent2 y siguientes capas.
- Objetivo operativo actual:
  - plantear Agent2 como motor de red flags y scoring explicable;
  - avanzar Agent4 con estructura LangGraph/LangChain, Qdrant, Ollama y RAG documental;
  - preparar PostgreSQL, Neo4j y Qdrant como capa de datos coordinada.
- Arquitectura de referencia:
  - Ingesta en `data/raw/`.
  - Normalizacion en `data/processed/`.
  - Cobertura y metadatos para siguiente capa.
  - PostgreSQL como canonico estructurado, Neo4j como grafo derivado y Qdrant como indice RAG.

## Que documentos leer primero para entender el proyecto completo

### Orden recomendado de lectura tecnica

1. [README](README.md)
   - Estado actual, comandos de uso inmediato y flujo base.
2. [SETUP](SETUP.md)
   - Entorno local y dependencias por fase.
3. [ARCHITECTURE](ARCHITECTURE.md)
   - Capas del sistema y decisiones de separacion.
4. [DOCS_README](docs/README.md)
   - Indice navegable de documentacion.
5. [PLANIFICACION_TFM](docs/00_vision/PLANIFICACION_TFM.md)
   - Stack definitivo, alcance academico y cronograma.
6. [PLAN_AGENTE1_PIPELINE](docs/03_agent1_ingesta/PLAN_AGENTE1_PIPELINE.md)
   - Flujo real de ingesta/normalizacion/coverage actual.
7. [PLAN_INGESTA_BATCH_AGENT1](docs/03_agent1_ingesta/PLAN_INGESTA_BATCH_AGENT1.md)
   - Batch recurrente y cronograma operativo.
8. [ARQUITECTURA_BATCH_Y_GRAFOS](docs/01_arquitectura/ARQUITECTURA_BATCH_Y_GRAFOS.md)
   - Propuesta de actualizaciones futuras + Neo4j.
9. [FUENTES_DATOS_Y_ROADMAP](docs/02_fuentes/FUENTES_DATOS_Y_ROADMAP.md)
   - Seleccion de fuentes y criterio de prioridad.
10. [ESTRATEGIA_PLACE_HACIENDA](docs/02_fuentes/ESTRATEGIA_PLACE_HACIENDA.md)
   - Encaje de PLACE en la metodologia y orden tecnico.
11. [SEGUIMIENTO_AGENTES](docs/04_agentes/SEGUIMIENTO_AGENTES.md)
   - Estado transversal de Agent1-Agent4.
12. [SEGUIMIENTO_AGENT1](docs/03_agent1_ingesta/SEGUIMIENTO_AGENT1.md)
   - Log de riesgos y decisiones del bloque activo.
13. [STACK_TECNICO_PROYECTO](docs/00_vision/STACK_TECNICO_PROYECTO.md)
    - Stack actual y objetivo del proyecto.
14. [PLAN_CAPA_DATOS_AGENTES](docs/01_arquitectura/PLAN_CAPA_DATOS_AGENTES.md)
    - Preparacion de PostgreSQL, Neo4j, Qdrant e IDs comunes.
15. [PLAN_AGENTE2_SCORING](docs/04_agentes/PLAN_AGENTE2_SCORING.md)
    - Red flags, scoring y salidas explicables.
16. [PLAN_AGENTE3_GRAFOS](docs/04_agentes/PLAN_AGENTE3_GRAFOS.md)
    - Grafos, Neo4j, NetworkX y relaciones.
17. [PLAN_AGENTE4_RAG_LANGGRAPH](docs/04_agentes/PLAN_AGENTE4_RAG_LANGGRAPH.md)
    - Estructura LangGraph/LangChain, Qdrant y RAG documental.

### Lectura de producto

- [GUIA_ENTREVISTA_TFM](docs/00_vision/GUIA_ENTREVISTA_TFM.md)
  para frasear el proyecto en defensa o entrevista.

## Stack y filosofias de uso

- Stack operativo: Python + pandas/Polars + LangGraph/LangChain + FastAPI (futuro) + Streamlit + Qdrant/Neo4j/PostgreSQL (fase posterior).
- Filosofia: primero data engineering, luego IA.
  1) Raw immutable.
  2) Normalizacion tipada y reproducible.
  3) Cobertura y calidad con metadatos (`sha256`, fecha, parser version).
  4) Solo despues, reglas y modelos.
- Diseño para relacionar: Neo4j se usa como capa derivada para consultas de vecinos, centralidad y recorridos.
- Uso interno recomendado:
  - Mantener comando unificado (`run-agent1`) para verificar estado base.
- No cambiar contratos canonicos sin actualizar pruebas de no-deriva.
  - Registrar toda corrida importante en `data/processed/agent1_run_report.json` y docs de seguimiento.

## Build, test y calidad

Comandos base:

```powershell
python -m procurewatch doctor
python -m pytest tests
python -m ruff check api scr tests
python -m ruff format api scr tests
```

Comandos de pipeline:

```powershell
procurewatch run-agent1 --year 2024 --cpv-prefix 71
procurewatch place-sources --year 2024 --datasets place_profiles place_aggregation place_buyer_profiles --inspect
```

## Estructura operativa minima

- `scr/procurewatch/`: codigo Python importable.
- `scr/procurewatch/agent1/`: ingesta, canonizacion y cobertura.
- `scr/procurewatch/agent2/`: red flags, scoring y estado de riesgo.
- `scr/procurewatch/agent3/`: futuro modulo de grafos y relaciones.
- `scr/procurewatch/agent4/`: NLP, RAG y LangGraph.
- `scr/procurewatch/data_sources/`: conectores/parsers de BOE, PLACE y OpenTender.
- `data/raw/`: origen sin tocar.
- `data/processed/`: parquet/csv preview, schema estable.
- `data/processed_sample/`: salidas de prueba separadas.
- `data/synthetic/`: muestras reproducibles.
- `docs/`: memoria tecnica y trazabilidad.
- `tests/`: regresion de parsing y reglas.

Regla fija: `data/` guarda datasets y artefactos generados; `scr/procurewatch/data_sources/`
guarda codigo de fuentes externas; `scr/procurewatch/agentN/` guarda logica de agente.

## Preguntas de continuidad para la proxima conversacion

- "Que fecha y fuente cambio hoy?" -> revisar `docs/03_agent1_ingesta/SEGUIMIENTO_AGENT1.md`.
- "Que ejecucion fue la ultima valida?" -> revisar `data/processed/agent1_run_report.json`.
- "Que hay que hacer despues de datos nuevos?" -> revisar `docs/03_agent1_ingesta/PLAN_AGENTE1_PIPELINE.md`.

## Objetivo propuesto: batch semanal/mensual de fuentes

- Objetivo actualizado: batch total de fuentes base + enriquecer con fuentes de datos.gob.es de forma sistemática.
- **Batch semanal**: controles de salud + inspeccion de cambios por manifiesto para BOE/PLACE/OpenTender/datos.gob.es.
- **Batch mensual**: refresco de capas base y reconstruccion derivada hacia el grafo de relaciones.
- Ver y completar en: [docs/03_agent1_ingesta/PLAN_INGESTA_BATCH_AGENT1.md](docs/03_agent1_ingesta/PLAN_INGESTA_BATCH_AGENT1.md).
- Estado objetivo de grafo en arquitectura: [docs/01_arquitectura/ARQUITECTURA_BATCH_Y_GRAFOS.md](docs/01_arquitectura/ARQUITECTURA_BATCH_Y_GRAFOS.md).

## Aclaracion sobre datos.gob.es

- Ya está clasificado el conjunto recomendable en:
  `docs/02_fuentes/FUENTES_DATOS_Y_ROADMAP.md`.
- Queda fuera del flujo mínimo actual de `run-agent1`, pero entra en la capa de actualizacion integral y contraste.
- En siguientes iteraciones se usará para enriquecer tablas de referencia y crear joins de entidad para grafos y red flags.

## Cierre de sesion (31/05/2026)

- `run-agent1` queda operativo y optimizado: reutiliza cache de BOE, PLACE y OpenTender si los artefactos procesados existen y coinciden con la fuente.
- Ultima corrida valida: `procurewatch run-agent1 --year 2024 --cpv-prefix 71`.
- Tiempo observado de corrida con cache: ~23 segundos.
- Artefactos clave generados:
  - `data/processed/agent1_run_report.json`
  - `data/processed/agent1_contract_key_coverage.parquet`
  - `data/processed/agent1_data_quality_summary.json`
  - `data/processed/agent2_contracts_canonical.parquet`
  - `data/processed/agent2_contracts_canonical_schema.json`
- Calidad final Agent1: `agent1_data_quality_summary.json` queda en estado `ok`.
- Dataset canonico Agent2: 51.720 filas.
- Cobertura actual por claves:
  - BOE: 7.867 claves.
  - PLACE: 18.797 claves.
  - OpenTender: 25.057 claves.
  - Universo: 51.721 claves.
  - Intersecciones entre fuentes: 0.
- Siguiente foco tecnico: mejorar `contract_key_canon` para reducir falsos no-match entre fuentes.
- Para reconstruccion completa usar: `procurewatch run-agent1 --year 2024 --cpv-prefix 71 --force-rebuild`.

## Replanificacion operativa 31/05/2026

El foco pasa de cerrar Agent1 a activar la capa superior:

- Agent2: usar `scr/procurewatch/agent2/` para red flags v1 sobre `agent2_contracts_canonical.parquet`.
- Agent3: crear la capa de grafos y relaciones desde el canonico o PostgreSQL.
- Agent4: mantener estructura importable bajo `scr/procurewatch/agent4/` con estado LangGraph,
  carga documental, chunking, embeddings, Qdrant y recuperacion.
- Datos: PostgreSQL como canonico estructurado, Neo4j como derivado relacional y Qdrant como
  indice vectorial.
- Stack local: instalar Docker Desktop, PostgreSQL, Neo4j Desktop o contenedor Neo4j, Qdrant por
  Docker, Ollama y modelos locales.
