# Arquitectura inicial

ProcureWatch Analytics se organiza como un prototipo modular. La prioridad inicial es que cada
modulo sea reproducible, testeable y explicable antes de integrar servicios masivos.

## Capas

```text
Fuentes abiertas
  -> pipeline de ingesta y normalizacion
  -> capas de evidencia (raw/manifest) y dataset procesado
  -> PostgreSQL / DuckDB (fact tables canónicas)
  -> grafo de relaciones (Neo4j, derivado y versionado)
  -> indice documental semantico (Qdrant, derivado y trazable)
  -> red flags, scoring y anomalias
  -> RAG documental y fichas explicables
  -> dashboard y fichas explicables
```

## Modulos del repositorio

- `scr/procurewatch/`: paquete Python comun, configuracion y utilidades compartidas.
- `scr/procurewatch/agent1/`: pipeline de ingesta, canonizacion, cobertura y entrega a Agent2.
- `scr/procurewatch/agent2/`: reglas de riesgo, scoring y estado de red flags.
- `scr/procurewatch/agent3/` (previsto): grafos, relaciones, metricas de red y carga a Neo4j.
- `scr/procurewatch/agent4/`: NLP, RAG documental y orquestacion LangGraph.
- `scr/procurewatch/data_sources/`: conectores, descargas y parsers de BOE, PLACE y OpenTender.
- `api/`: futura capa de consulta para dashboard o agentes.
- `frontend/`: dashboard Streamlit y visualizaciones.
- `tests/`: pruebas unitarias e integracion ligera.

Regla de separacion:

- `data/` guarda datasets reales, muestras y artefactos generados.
- `scr/procurewatch/data_sources/` guarda codigo para leer fuentes externas.
- `scr/procurewatch/agentN/` guarda la logica propia de cada agente.

## Decisiones de arranque

1. El codigo compartido vive en el paquete `procurewatch`, dentro de `scr/`, para respetar la
   estructura ya documentada en el TFM.
2. El primer comando ejecutable es `procurewatch doctor`; sirve para verificar entorno antes de
   descargar datos o levantar servicios.
3. PostgreSQL, Neo4j, Qdrant y Ollama se modelan como servicios opcionales hasta que haya un
   pipeline minimo que los consuma.
4. Los datos reales y modelos generados quedan fuera de Git. Solo se versionan muestras pequenas
   sinteticas o metadatos necesarios para reproducibilidad.
5. Los conectores de `datos.gob.es` se consideran fase de enriquecimiento y corroboracion; se incluyen
   en actualizaciones recurrentes, pero la capa base de Agent1 sigue centrada en BOE/PLACE/OpenTender.
6. Neo4j se usa como capa derivada, no como origen único. El origen analitico trazable sigue en
   archivos/Tabular + PostgreSQL.
7. Qdrant se usa como indice vectorial derivado, no como base documental principal. Los textos
   originales deben conservarse en PostgreSQL, Parquet o filesystem trazable.
8. DuckDB se usa para analisis local sobre Parquet; PostgreSQL queda como capa canonica
   estructurada cuando arranque la persistencia de agentes.

## Flujo minimo de datos previsto

1. Ingesta de fuentes en raw (con manifest y `sha256`).
2. Normalizacion a un esquema analitico compatible con OCDS.
3. Exportacion a `data/processed/` en Parquet.
4. Generacion de dataset canónico y carga analitica (PostgreSQL/DuckDB).
5. Construccion de grafo de relaciones en Neo4j a partir de tabla canónica (incremental).
6. Indexacion documental en Qdrant a partir de documentos/chunks trazables.
7. Calculo de red flags iniciales.
8. Construccion de grafo organismo-adjudicatario-contrato.
9. Recuperacion RAG para evidencias documentales.
10. Visualizacion en dashboard con ficha explicativa por caso.

## Evolucion del modelo para updates

- Batch semanal: vigilancia de cambios + manifest por fuente.
- Batch mensual: recarga de capas, ejecución de Agent1 y refresco parcial de grafo.
- Batch trimestral: armonización y validaciones de deriva global.

## Cierre de sesion (31/05/2026)

- Agent1 ya materializa BOE, PLACE y OpenTender en `data/processed`.
- Agent1 ya materializa una primera capa canonica para Agent2:
  - `data/processed/agent2_contracts_canonical.parquet`
  - `data/processed/agent2_contracts_canonical_schema.json`
- `run-agent1` funciona como orquestador incremental: usa cache si los outputs existen y admite `--force-rebuild` para reconstruccion completa.
- La cobertura cruzada existe en `agent1_contract_key_coverage.parquet`, pero las intersecciones entre fuentes siguen a 0 por la politica actual de clave.
- El siguiente trabajo arquitectonico es mejorar matching y despues derivar red flags/grafo desde el canonico Agent2.

## Replanificacion de capa de datos (31/05/2026)

- PostgreSQL sera la capa canonica para contratos, entidades, scores, flags y outputs de agentes.
- Neo4j se construira como capa derivada desde `agent2_contracts_canonical.parquet` o PostgreSQL.
- Qdrant se construira como indice derivado para Agent4/RAG, siempre con `contract_key_canon`,
  `document_id` y `chunk_id`.
- Agent2 se apoyara primero en Parquet/PostgreSQL y despues en Neo4j para relaciones.
- Agent3 sera la capa explicita de grafos y relaciones derivadas.
- Agent4 se apoyara en PostgreSQL/Qdrant/Ollama y quedara orquestado con LangGraph.
