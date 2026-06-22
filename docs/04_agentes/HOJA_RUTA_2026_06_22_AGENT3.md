# Hoja de ruta 2026-06-22: Agent3 grafos

## Objetivo de la sesion

Activar Agent3 como capa determinista de grafos y metricas relacionales sobre el dataset canonico de Agent1/Agent2. La prioridad es construir una salida local reproducible antes de cargar Neo4j.

## Fuentes de alineacion

- Documentacion principal del repositorio: [Plan Agent3 grafos](PLAN_AGENTE3_GRAFOS.md), [Plan capa datos agentes](../01_arquitectura/PLAN_CAPA_DATOS_AGENTES.md), [Seguimiento agentes](SEGUIMIENTO_AGENTES.md).
- Propuesta tecnica SASM: se usa como control de coherencia general.
- Maqueta TFM: se usa como referencia secundaria para confirmar enfoque de grafo empresa-organismo-contrato, centralidad y comunidades.

Regla de decision: los `.md` del repositorio mandan. SASM y maqueta solo corrigen desviaciones fuertes.

## Alcance tecnico de hoy

- Crear `scr/procurewatch/agent3/` como modulo importable.
- Leer solo `data/processed/agent2_contracts_canonical.parquet` o estructuras equivalentes en tests.
- Generar nodos `Buyer`, `Supplier`, `Contract`, `CPV` y `Source`.
- Generar aristas `PUBLISHED`, `AWARDED_TO`, `HAS_CPV` y `FROM_SOURCE`.
- Calcular metricas v1 unibles por `contract_key_canon`:
  - recurrencia comprador-proveedor;
  - grado de comprador;
  - grado de proveedor;
  - contratos por proveedor;
  - concentracion comprador-proveedor.

## Fuera de alcance hoy

- Carga real a Neo4j.
- Deteccion de comunidades Louvain/Leiden.
- Integracion final con Agent2 scoring.
- RAG completo de Agent4 con Qdrant/Ollama.

## Commits previstos

1. `docs: add daily roadmap for agent3 session`
2. `feat(agent3): add graph schemas and canonical input`
3. `feat(agent3): generate procurement graph tables`
4. `feat(agent3): compute graph metrics for scoring`
5. `test(agent3): cover graph tables and metrics`

## Tecnologias a estudiar durante el avance

- NetworkX: grados, centralidad y estructura bipartita/tripartita.
- Neo4j/Cypher: `MERGE`, claves estables e idempotencia.
- pandas + Parquet: agregaciones, deduplicacion y joins por `contract_key_canon`.
- Louvain/Leiden: comunidades como siguiente fase.
- Feature engineering: metricas relacionales para RF-03 y RF-04 sin declarar fraude.
