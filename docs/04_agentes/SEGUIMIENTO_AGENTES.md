# Seguimiento operativo de agentes

Este documento es el seguimiento transversal. Los detalles historicos de Agent1 se mantienen en
[Seguimiento Agent1](../03_agent1_ingesta/SEGUIMIENTO_AGENT1.md).

## Estado actual 24/06/2026

| Agente | Estado | Entrada principal | Salida principal | Limitacion o siguiente paso |
|---|---|---|---|---|
| Agent1 | MVP operativo | BOE, PLACE, OpenTender raw o fixtures locales | `agent2_contracts_canonical.parquet`, diagnosticos y `source_snapshot_id` | Mejorar matching entre fuentes y normalizacion de claves canonicas |
| Agent2 | V1 local implementada | Canonico Agent1 y features opcionales Agent3 | `agent2_risk_scores.parquet`, `agent2_risk_flags.parquet` | Ampliar reglas futuras, calibrar con etiquetas reales y persistir historico en PostgreSQL |
| Agent3 | MVP tecnico cerrado | Canonico Agent1 o demo sintetica | nodos, aristas, comunidades, metricas y features para Agent2/Agent4 | Endurecer identificadores, operativa Neo4j y analisis productivo recurrente |
| Agent4 | PoC/MVP RAG trazable | Contratos canonicos, features Agent3 y corpus local | case context, evidencias, citas, evaluacion local y scope | Ampliar corpus documental real y dejar scraping vivo/RAGAS como trabajo futuro |
| Dashboard | Demo local validada | Artefactos regenerables Hito 6 | Streamlit demo y reporte de validacion | Capturas finales y despliegue quedan fuera del MVP tecnico |

## Corte integrado Agent3-Agent4 23/06/2026

Se genera un cierre demostrable conjunto para Agent3 y Agent4 en:

- [Cierre integrado Agent3-Agent4 2026-06-23](CIERRE_AGENT3_AGENT4_2026_06_23.md)
- Artefactos locales regenerables: `data/processed/agent3_agent4_demo_2026_06_23/`

## Cierre operativo TFM 24/06/2026

La hoja de ruta de cierre del dia queda en:

- [Hoja de ruta final TFM 2026-06-24](../00_vision/HOJA_RUTA_FINAL_TFM_2026_06_24.md)
- [Hoja de ruta cierre TFM 2026-06-24](HOJA_RUTA_CIERRE_TFM_2026_06_24.md)
- [Hoja de ruta trabajo tarde TFM 2026-06-24](HOJA_RUTA_TRABAJO_TARDE_TFM_2026_06_24.md)

Prioridad: validar `integration/multiagent`, ejecutar la demo reproducible y alinear memoria,
dashboard y limitaciones con el alcance realmente implementado.

## Hitos cerrados durante el 24/06/2026

- Hito 1: Agent1 incorpora `source_snapshot_id` determinista en el canonico y conserva la
  trazabilidad de snapshot para capas posteriores.
- Hito 2: Agent1 genera diagnosticos de matching y previews de candidatos para explicar por que
  BOE, PLACE y OpenTender no cruzan de forma fiable por `contract_key_canon`.
- Hito 3: Agent2 consume features opcionales de Agent3 para reforzar RF-03/RF-04 sin bloquear el
  scoring cuando esas features no existen.
- Hito 4: el batch incorpora health/manifest y puede quedar en `blocked_missing_inputs` sin
  producir salidas inconsistentes.
- Hito 5: Agent4 explicita su `agent4_scope`, source registry, politicas de fuentes y fetch puntual
  de anuncios BOE-B HTML. No implementa crawling vivo ni descarga automatica de pliegos PLACSP.
- Hito 6: se anade `run-integrated-demo` para regenerar offline el caso `PW-2024-0001` de Agent2 a
  Agent3 y Agent4.
- Hito 7: se anade `validate-dashboard-demo` para regenerar la demo, validar artefactos y ejecutar
  el dashboard Streamlit en modo headless.

## Demo integrada reproducible

Comando recomendado:

```powershell
$env:PYTHONPATH='scr'; python -m procurewatch.cli run-integrated-demo
```

Resultado verificado:

- Dataset canonico demo sintetico con 3 contratos, incluido `PW-2024-0001`.
- Agent3 genera 11 nodos, 13 aristas, comunidades, metricas contractuales y 3 filas de features.
- Agent4 genera ficha para `PW-2024-0001` combinando:
  - contrato canonico;
  - score Agent2 `risk_score=0.5`;
  - red flags `risky_procedure` y `awarded_above_estimate`;
  - metricas Agent3;
  - 2 evidencias documentales y 2 citas;
  - `decision_boundary` y `agent4_scope`.
- Reporte integrado: `agent2_agent3_agent4_demo_report.json`.
- Estado esperado del reporte: `ready`.

## Dashboard validado para defensa local

Comando recomendado:

```powershell
$env:PYTHONPATH='scr'; python -m procurewatch.cli validate-dashboard-demo
```

Resultado verificado:

- Regenera o actualiza primero la demo integrada para evitar artefactos obsoletos.
- Comprueba artefactos completos de Agent3 y ficha Agent4 de `PW-2024-0001`.
- Valida KPIs, score Agent2, metricas Agent3, evidencias y citas.
- Comprueba que el texto visible mantiene la frontera de priorizacion/revision humana y no declara
  fraude.
- Ejecuta `frontend/agent3_demo.py` con `streamlit.testing.v1.AppTest` en modo headless sin
  excepciones.
- Reporte: `dashboard_validation_report.json`.
- Estado esperado del reporte: `ready`.

Para abrir la demo en defensa:

```powershell
$env:PYTHONPATH='scr'
$env:PROCUREWATCH_AGENT3_DEMO_DIR='data/processed/agent3_agent4_demo_2026_06_23'
$env:PROCUREWATCH_AGENT4_CASE_CONTEXT='data/processed/agent3_agent4_demo_2026_06_23/agent4_case_context_integrated_demo.json'
streamlit run frontend/agent3_demo.py
```

Capturas recomendadas: Resumen, Contratos priorizados, Caso seleccionado, Relaciones, Evidencias y
Trazabilidad.

## Validacion tecnica verificada

- Rama validada: `integration/multiagent`.
- Commit base de inspeccion previo al cierre de hitos: `19919bd`.
- `python -m procurewatch doctor`
  - Resultado: OK; servicios PostgreSQL, Neo4j, Qdrant y Ollama quedan como opcionales.
- `$env:PYTHONPATH='scr'; python -m pytest`
  - Resultado: 111 passed, 1 skipped.
- `$env:PYTHONPATH='scr'; python -m ruff check frontend scr tests`
  - Resultado: All checks passed.
- `$env:PYTHONPATH='scr'; python -m procurewatch.cli run-integrated-demo`
  - Resultado: `ready`, 3 contratos, 11 nodos, 13 aristas, score 0.5, 2 evidencias y 2 citas.
- `$env:PYTHONPATH='scr'; python -m procurewatch.cli validate-dashboard-demo`
  - Resultado: `ready`, KPIs cargables y render headless sin excepciones.

Decision de continuidad:

- La integracion multiagente queda validada como candidata a promocion a rama principal.
- Agent3 y Agent4 quedan cerrados como MVP/PoC defendibles dentro de una demo integrada con Agent2.
- El siguiente bloque recomendado es acordar si la rama principal sera `master` o `main`, hacer
  push/merge final y capturar evidencias visuales del dashboard para memoria o defensa.
- La hoja de ruta de cierre de `sebas` queda en
  [Hoja de ruta sebas: cierre TFM y demo evaluable](HOJA_RUTA_SEBAS_CIERRE_TFM.md).

## Reglas comunes

- `data/` guarda datasets y artefactos generados; los artefactos de `data/processed` no se
  versionan y deben poder regenerarse.
- `scr/procurewatch/data_sources/` guarda conectores y parsers de fuentes externas.
- `scr/procurewatch/agentN/` guarda la logica propia de cada agente.
- Ningun agente debe afirmar fraude; todos priorizan revision humana con evidencia trazable.

## Bloqueos y cautelas

- El matching actual entre BOE, PLACE y OpenTender tiene intersecciones 0 por `contract_key_canon`.
- Agent2 puede avanzar con senales intrafuente y features de Agent3, pero no debe afirmar contraste
  real entre fuentes mientras el matching siga incompleto.
- Agent3 debe construirse desde el canonico o PostgreSQL, no desde raw.
- Agent4 debe citar `document_id`, `chunk_id` y `contract_key_canon` cuando use evidencia textual.
- Agent4 no scrapea webs en vivo, no navega por PLACSP, no descarga pliegos automaticamente, no usa
  spaCy como pipeline principal cerrado y no ejecuta RAGAS completo en el MVP.

## Documentos canonicos

- [Plan Agent1 pipeline](../03_agent1_ingesta/PLAN_AGENTE1_PIPELINE.md)
- [Plan Agent2 scoring](PLAN_AGENTE2_SCORING.md)
- [Plan Agent3 grafos](PLAN_AGENTE3_GRAFOS.md)
- [Plan Agent4 RAG LangGraph](PLAN_AGENTE4_RAG_LANGGRAPH.md)
- [Pendientes y no implementado 2026-06-24](PENDIENTES_NO_IMPLEMENTADO_2026_06_24.md)
- [Hoja de ruta sebas cierre TFM](HOJA_RUTA_SEBAS_CIERRE_TFM.md)
- [Plan capa datos agentes](../01_arquitectura/PLAN_CAPA_DATOS_AGENTES.md)
