# Plan de capa de datos para Agent2, Agent3 y Agent4

Objetivo: preparar una capa de datos coordinada para que Agent2, Agent3 y Agent4 puedan trabajar sobre
los mismos identificadores, evidencias y snapshots sin duplicar datos de forma descontrolada.

## Correccion de enfoque

DuckDB no debe entenderse como un paso obligatorio antes de PostgreSQL. La separacion correcta es:

- Parquet + DuckDB: exploracion analitica local, consultas rapidas y preparacion reproducible.
- PostgreSQL: capa canonica estructurada para contratos, entidades, scores, flags, outputs y
  trazabilidad.
- Neo4j: capa derivada de relaciones para recorridos, recurrencia, centralidades y comunidades.
- Qdrant: indice vectorial para recuperar evidencia textual y contexto documental.

PostgreSQL debe ser la referencia estructurada principal. Neo4j y Qdrant se construyen desde
PostgreSQL o desde Parquet canonico, pero no sustituyen el origen trazable.

## Fuentes de entrada inmediatas

- `data/processed/agent2_contracts_canonical.parquet`
- `data/processed/agent2_contracts_canonical_schema.json`
- `data/processed/agent1_run_report.json`
- `data/processed/agent1_data_quality_summary.json`
- Futuro: documentos HTML/PDF/TXT descargados desde PLACE/BOE u otras fuentes publicas.

## IDs estables obligatorios

Todas las capas deben conservar:

- `contract_key_canon`
- `source`
- `source_record_id`
- `buyer_id`
- `supplier_id`
- `source_snapshot_id` cuando se incorpore al batch
- `document_id` para textos/documentos
- `chunk_id` para fragmentos de RAG

## PostgreSQL minimo

Tablas objetivo para el primer ciclo:

- `contracts`
- `buyers`
- `suppliers`
- `awards`
- `documents`
- `risk_flags`
- `risk_scores`
- `agent_outputs`
- `etl_runs`
- `data_quality_issues`

El MVP de Agent2 ya escribe una version operativa reducida en PostgreSQL con:

- `agent2_risk_flags`
- `agent2_risk_scores`
- `agent2_outputs`

Esto no sustituye el esquema objetivo anterior; simplemente valida trazabilidad y consulta del
scoring mientras se completa la capa de datos completa.

## Neo4j minimo

Neo4j se usara como capa derivada para Agent3 y para metricas relacionales que alimenten Agent2.

Nodos:

- `Buyer`
- `Supplier`
- `Contract`
- `CPV`
- `Source`
- `RiskFlag`

Relaciones:

- `(:Buyer)-[:PUBLISHED]->(:Contract)`
- `(:Contract)-[:AWARDED_TO]->(:Supplier)`
- `(:Contract)-[:HAS_CPV]->(:CPV)`
- `(:Contract)-[:FROM_SOURCE]->(:Source)`
- `(:Contract)-[:HAS_RISK_FLAG]->(:RiskFlag)`

## Qdrant minimo

Qdrant se usara para Agent4/RAG, no como almacen documental principal.

Coleccion inicial:

- `procurement_documents`

Payload minimo por chunk:

- `document_id`
- `chunk_id`
- `contract_key_canon`
- `source`
- `source_record_id`
- `buyer_id`
- `supplier_id`
- `document_type`
- `text`
- `created_at`

## Secuencia de trabajo

1. Validar que `run-agent1` sigue generando el dataset canonico.
2. Definir esquema PostgreSQL minimo y carga desde `agent2_contracts_canonical.parquet`.
3. Generar tablas `nodes_*` y `edges_*` desde el canonico.
4. Cargar Neo4j de forma idempotente.
5. Descargar y catalogar documentos para muestra RAG.
6. Extraer texto, crear chunks y generar embeddings.
7. Cargar chunks en Qdrant con payload completo.
8. Conectar Agent3 a PostgreSQL/Neo4j.
9. Conectar Agent2 a PostgreSQL y a metricas de Agent3.
10. Conectar Agent4 a PostgreSQL/Qdrant/Ollama.
11. Registrar cada salida de agente en PostgreSQL con evidencias.

## Criterio de cierre del bloque

- Un contrato del canonico existe en PostgreSQL.
- Sus nodos y relaciones basicas existen en Neo4j.
- Al menos un documento o texto asociado se recupera desde Qdrant por similitud semantica.
- Agent2 puede calcular una primera red flag explicable.
- Agent3 puede generar una primera metrica relacional por `contract_key_canon`.
- Agent4 puede recuperar contexto y devolver evidencia trazable con `contract_key_canon`.
