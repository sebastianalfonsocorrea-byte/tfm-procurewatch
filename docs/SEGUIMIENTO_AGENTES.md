# Seguimiento operativo de agentes

Este documento es el seguimiento transversal. Los detalles historicos de Agent1 se mantienen en
`SEGUIMIENTO_AGENT1.md`.

## Estado actual 21/06/2026

| Agente | Estado | Entrada principal | Salida principal | Siguiente paso |
|---|---|---|---|---|
| Agent1 | Operativo | BOE, PLACE, OpenTender raw | `agent2_contracts_canonical.parquet` | Mejorar matching entre fuentes |
| Agent2 | RF-05 implementada | Canonico Agent1 | `agent2_risk_flags.parquet`, `agent2_risk_scores.parquet` | Validar resultados y añadir RF-02 |
| Agent3 | Planificado | Canonico Agent1/PostgreSQL | nodos, edges y metricas | Crear generador de grafo |
| Agent4 | Scaffold y plan | Contratos y documentos | chunks, retrieval y contexto | PoC RAG con evidencia |

## Reglas comunes

- `data/` guarda datasets y artefactos generados.
- `scr/procurewatch/data_sources/` guarda conectores y parsers de fuentes externas.
- `scr/procurewatch/agentN/` guarda la logica propia de cada agente.
- Ningun agente debe afirmar fraude; todos priorizan revision humana con evidencia trazable.

## Avance Agent2 21/06/2026

- RF-05 detecta adjudicaciones cuyo importe supera en más de un 10 % el importe estimado.
- El umbral es configurable y queda versionado como decisión operativa inicial.
- Cada activación conserva evidencia, versión de regla y hash del dataset de entrada.
- Los contratos sin ambos importes se marcan como `no_evaluable`; no se interpretan como riesgo
  bajo.
- El score inicial usa escala 0-100: 25 puntos y nivel medio cuando RF-05 se activa.
- Resultado sobre las 4.062 líneas de adjudicación BOE actuales:
  - 557 contratos evaluables por disponer de importe estimado y adjudicado;
  - 3.505 contratos no evaluables por falta de alguno de esos datos;
  - 11 activaciones de RF-05 con el umbral inicial del 10 %.
- La cobertura limitada de importes debe constar como limitación del resultado; las 11 activaciones
  no representan una estimación de fraude ni del riesgo total del universo.

## Bloqueos y cautelas

- El matching actual entre BOE, PLACE y OpenTender tiene intersecciones 0 por `contract_key_canon`.
- Agent2 puede avanzar con señales intrafuente, pero no debe afirmar contraste real entre fuentes.
- Agent3 debe construirse desde el canonico o PostgreSQL, no desde raw.
- Agent4 debe citar `document_id`, `chunk_id` y `contract_key_canon` cuando use evidencia textual.

## Documentos canonicos

- `PLAN_AGENTE1_PIPELINE.md`
- `PLAN_AGENTE2_SCORING.md`
- `PLAN_AGENTE3_GRAFOS.md`
- `PLAN_AGENTE4_RAG_LANGGRAPH.md`
- `PLAN_CAPA_DATOS_AGENTES.md`
