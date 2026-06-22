# Seguimiento operativo de agentes

Este documento es el seguimiento transversal. Los detalles historicos de Agent1 se mantienen en
[Seguimiento Agent1](../03_agent1_ingesta/SEGUIMIENTO_AGENT1.md).

## Estado actual 31/05/2026

| Agente | Estado | Entrada principal | Salida principal | Siguiente paso |
|---|---|---|---|---|
| Agent1 | Operativo | BOE, PLACE, OpenTender raw | `agent2_contracts_canonical.parquet` | Mejorar matching entre fuentes |
| Agent2 | Scaffold y plan | Canonico Agent1 | red flags y scores | Implementar reglas v1 |
| Agent3 | Planificado | Canonico Agent1/PostgreSQL | nodos, edges y metricas | Crear generador de grafo |
| Agent4 | Scaffold y plan | Contratos y documentos | chunks, retrieval y contexto | PoC RAG con evidencia |

## Reglas comunes

- `data/` guarda datasets y artefactos generados.
- `scr/procurewatch/data_sources/` guarda conectores y parsers de fuentes externas.
- `scr/procurewatch/agentN/` guarda la logica propia de cada agente.
- Ningun agente debe afirmar fraude; todos priorizan revision humana con evidencia trazable.

## Bloqueos y cautelas

- El matching actual entre BOE, PLACE y OpenTender tiene intersecciones 0 por `contract_key_canon`.
- Agent2 puede avanzar con señales intrafuente, pero no debe afirmar contraste real entre fuentes.
- Agent3 debe construirse desde el canonico o PostgreSQL, no desde raw.
- Agent4 debe citar `document_id`, `chunk_id` y `contract_key_canon` cuando use evidencia textual.

## Documentos canonicos

- [Plan Agent1 pipeline](../03_agent1_ingesta/PLAN_AGENTE1_PIPELINE.md)
- [Plan Agent2 scoring](PLAN_AGENTE2_SCORING.md)
- [Plan Agent3 grafos](PLAN_AGENTE3_GRAFOS.md)
- [Plan Agent4 RAG LangGraph](PLAN_AGENTE4_RAG_LANGGRAPH.md)
- [Plan capa datos agentes](../01_arquitectura/PLAN_CAPA_DATOS_AGENTES.md)
