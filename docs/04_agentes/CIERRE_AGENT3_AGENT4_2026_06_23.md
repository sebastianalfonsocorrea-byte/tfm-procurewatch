# Cierre integrado Agent3-Agent4 2026-06-23

## Objetivo

Dejar trazado el estado de cierre de Agent3 y Agent4 como bloque tecnico demostrable:

- Agent3 genera grafo, metricas relacionales y features por `contract_key_canon`.
- Agent4 genera una ficha documental trazable con contrato canonico, score Agent2, metricas Agent3
  y evidencias/citas.
- Ningun agente declara fraude; todos producen senales para revision humana.

## Estado de cierre

| Bloque | Estado | Evidencia |
|---|---|---|
| Agent3 | MVP tecnico cerrado | Grafo reproducible, metricas NetworkX, features para Agent2/Agent4 y carga Neo4j preparada |
| Agent4 | PoC RAG trazable cerrada | Corpus sintetico, retrieval local/Qdrant, ficha `case_context`, integracion Agent2/Agent3 y evaluacion local |
| Integracion | Demo reproducible generada | Artefactos en `data/processed/agent3_agent4_demo_2026_06_23/` |

## Demo integrada generada

Carpeta de artefactos:

```text
data/processed/agent3_agent4_demo_2026_06_23/
```

Entrada canonica sintetica:

- `agent2_contracts_canonical_demo.parquet`
- 3 contratos sinteticos.
- Contrato principal: `PW-2024-0001`.
- El contrato principal activa:
  - procedimiento de riesgo: `negociado sin publicidad`;
  - adjudicacion por encima del estimado;
  - proveedor recurrente dentro del grafo demo;
  - evidencia documental en el corpus Agent4.

Comando Agent3 ejecutado:

```powershell
python -c "import sys; sys.path.insert(0, 'scr'); from procurewatch.cli import main; raise SystemExit(main(['run-agent3','--input','data/processed/agent3_agent4_demo_2026_06_23/agent2_contracts_canonical_demo.parquet','--output-dir','data/processed/agent3_agent4_demo_2026_06_23']))"
```

Resultado Agent3:

- Nodos: 11.
- Aristas: 13.
- Metricas por contrato: 3.
- Features Agent2/Agent4: 3.
- Componentes: 1.
- Comunidades: 2.
- Reporte: `agent3_graph_report.json`.

Comando Agent4 ejecutado:

```powershell
python -c "import sys; sys.path.insert(0, 'scr'); from procurewatch.cli import main; raise SystemExit(main(['agent4-case-context','--contract-key','PW-2024-0001','--question','evidencia documental y riesgos explicables','--canonical-path','data/processed/agent3_agent4_demo_2026_06_23/agent2_contracts_canonical_demo.parquet','--agent3-features-path','data/processed/agent3_agent4_demo_2026_06_23/agent3_agent2_features.parquet','--output','data/processed/agent3_agent4_demo_2026_06_23/agent4_case_context_integrated_demo.json']))"
```

Resultado Agent4:

- Agent2 `risk_score`: 0.5.
- Agent2 red flags: `risky_procedure`, `awarded_above_estimate`.
- Agent3 metricas: presentes.
- Evidencias documentales: 2.
- Citas: 2.
- Generacion: fallback determinista offline.
- Warning esperado: vector store no configurado en esta demo offline.
- Ficha: `agent4_case_context_integrated_demo.json`.

## Artefactos clave

- `agent3_nodes.parquet`
- `agent3_edges.parquet`
- `agent3_contract_metrics.parquet`
- `agent3_entity_metrics.parquet`
- `agent3_communities.parquet`
- `agent3_network_summary.json`
- `agent3_agent2_features.parquet`
- `agent3_agent2_features_schema.json`
- `agent3_graph_report.json`
- `agent4_case_context_integrated_demo.json`

## Validacion tecnica

Validacion enfocada ejecutada tras el cierre:

```powershell
python -m pytest -p no:cacheprovider tests\test_agent3.py tests\test_agent4.py
python -m ruff check --no-cache scr\procurewatch\agent3 scr\procurewatch\agent4 tests\test_agent3.py tests\test_agent4.py
```

Resultado:

- Tests Agent3/Agent4: 52 passed.
- Ruff Agent3/Agent4: All checks passed.

## Lectura para memoria o defensa

Este corte permite explicar el flujo completo:

1. Agent1/Agent2 entregan contrato canonico y score determinista.
2. Agent3 transforma contratos en grafo derivado y devuelve metricas relacionales.
3. Agent4 toma contrato, score, metricas y documentos, y genera una ficha con evidencia citada.
4. La salida final prioriza revision humana y trazabilidad, no declaracion automatica de fraude.

## Limitaciones registradas

- La demo integrada usa una muestra sintetica minima para alinear contrato, grafo y corpus.
- La calidad final de Agent3 depende de normalizacion de entidades y `contract_key_canon`.
- La calidad final de Agent4 depende de ampliar corpus documental real o semi-real.
- Qdrant/Ollama quedan disponibles para demo con servicios, pero los tests unitarios se mantienen
  offline y reproducibles.
