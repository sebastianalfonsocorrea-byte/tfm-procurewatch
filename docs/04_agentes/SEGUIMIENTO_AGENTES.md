# Seguimiento operativo de agentes

Este documento es el seguimiento transversal. Los detalles historicos de Agent1 se mantienen en
[Seguimiento Agent1](../03_agent1_ingesta/SEGUIMIENTO_AGENT1.md).

## Estado actual 23/06/2026

| Agente | Estado | Entrada principal | Salida principal | Siguiente paso |
|---|---|---|---|---|
| Agent1 | Operativo | BOE, PLACE, OpenTender raw | `agent2_contracts_canonical.parquet` | Mejorar matching entre fuentes |
| Agent2 | V1 local implementada | Canonico Agent1 | `agent2_risk_scores.parquet`, `agent2_risk_flags.parquet` | Integrar features Agent3 y PostgreSQL |
| Agent3 | MVP tecnico cerrado | Canonico Agent1/PostgreSQL | nodos, edges, metricas y features | Demo integrada y dashboard final |
| Agent4 | PoC RAG trazable cerrada | Contratos y documentos | case context, citas y evaluacion RAG local | Ampliar corpus real/semi-real |

## Corte integrado Agent3-Agent4 23/06/2026

Se genera un cierre demostrable conjunto para Agent3 y Agent4 en:

- [Cierre integrado Agent3-Agent4 2026-06-23](CIERRE_AGENT3_AGENT4_2026_06_23.md)
- Artefactos locales: `data/processed/agent3_agent4_demo_2026_06_23/`

## Cierre operativo TFM 24/06/2026

La hoja de ruta de cierre del dia queda en:

- [Hoja de ruta final TFM 2026-06-24](../00_vision/HOJA_RUTA_FINAL_TFM_2026_06_24.md)
- [Hoja de ruta cierre TFM 2026-06-24](HOJA_RUTA_CIERRE_TFM_2026_06_24.md)

Prioridad: validar `integration/multiagent`, ejecutar la demo reproducible y alinear memoria,
dashboard y limitaciones con el alcance realmente implementado.

Resumen de la demo:

- Agent3 se ejecuta sobre un canonico sintetico minimo con 3 contratos.
- Agent3 genera 11 nodos, 13 aristas, 3 metricas contractuales y 3 filas de features.
- Agent4 genera ficha para `PW-2024-0001` combinando:
  - contrato canonico;
  - score Agent2 `risk_score=0.5`;
  - red flags `risky_procedure` y `awarded_above_estimate`;
  - metricas Agent3;
  - 2 evidencias documentales y 2 citas.

Validacion enfocada:

- `python -m pytest -p no:cacheprovider tests\test_agent3.py tests\test_agent4.py`
  - Resultado: 52 passed.
- `python -m ruff check --no-cache scr\procurewatch\agent3 scr\procurewatch\agent4 tests\test_agent3.py tests\test_agent4.py`
  - Resultado: All checks passed.

Validacion de integracion final 2026-06-24:

- Rama validada: `integration/multiagent`.
- `origin/Satu` y `origin/sebas` estan integradas en `HEAD`.
- `python -m procurewatch doctor`
  - Resultado: OK; servicios PostgreSQL, Neo4j, Qdrant y Ollama quedan como opcionales.
- `python -m pytest tests`
  - Resultado: 92 passed, 1 skipped.
- `python -m ruff check api scr tests frontend`
  - Resultado: All checks passed.
  - Nota: ruff aviso que no pudo escribir cache local, sin afectar al resultado.
- Demo Agent3 regenerada en `data/processed/agent3_agent4_demo_2026_06_23/`.
  - Resultado: 11 nodos, 13 aristas, 3 metricas contractuales y 3 filas de features.
- Ficha Agent4 regenerada para `PW-2024-0001`.
  - Resultado: `risk_score=0.5`, 2 red flags, metricas Agent3, 2 evidencias y 2 citas.
- Dashboard `frontend/agent3_demo.py` validado en modo headless.
  - Resultado: HTTP 200, sin artefactos faltantes, KPIs cargados.

Decision de continuidad:

- La integracion multiagente queda validada como candidata a promocion a rama principal.
- Agent3 y Agent4 quedan cerrados como MVP/PoC defendibles.
- El siguiente bloque recomendado es acordar si la rama principal sera `master` o `main`, hacer
  push/merge final y capturar evidencias visuales del dashboard para memoria o defensa.
- La hoja de ruta de cierre de `sebas` queda en
  [Hoja de ruta sebas: cierre TFM y demo evaluable](HOJA_RUTA_SEBAS_CIERRE_TFM.md).

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
- [Hoja de ruta sebas cierre TFM](HOJA_RUTA_SEBAS_CIERRE_TFM.md)
- [Plan capa datos agentes](../01_arquitectura/PLAN_CAPA_DATOS_AGENTES.md)
