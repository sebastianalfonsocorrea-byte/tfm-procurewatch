# Bitacora Agent4: documental, RAG y LangGraph

Este documento recoge cortes operativos de Agent4 para mantener trazabilidad entre sesiones.

## 2026-06-23 - Corte de estado y arranque de ficha explicable

Contexto:

- La sesion parte del cierre funcional del Hito 4 de Agent4: flujo documental LangGraph/fallback
  sobre corpus local.
- El objetivo inmediato es dejar constancia de lo implementado y continuar con los siguientes
  hitos sin perder trazabilidad.

Estado comprobado del repo:

- `scr/procurewatch/agent4/` contiene carga documental, chunking, retrieval local, embeddings,
  Qdrant store, indexacion, nodos, estado y grafo.
- Existe corpus sintetico trazable en `data/synthetic/agent4_corpus/` con TXT, HTML y Markdown.
- Comandos CLI disponibles:
  - `procurewatch agent4-smoke`
  - `procurewatch agent4-build-manifest`
  - `procurewatch agent4-index-corpus`
  - `procurewatch agent4-run-flow`
- Artefactos locales observados:
  - `data/processed/agent4_documents_manifest.json`
  - `data/processed/agent4_case_context_hito4.json`
- Validacion inicial del dia:
  - `python -m pytest tests\test_agent4.py`
  - Resultado: 21 tests pasados.
  - Nota: pytest emitio una advertencia de cache por permisos en `.pytest_cache`; no afecta a
    los tests de Agent4.
- Validacion tras iniciar Hito 5:
  - `python -m pytest tests\test_agent4.py`
  - Resultado: 23 tests pasados.
- Validacion CLI tras Hito 5:
  - `python -m procurewatch agent4-run-flow --contract-key PW-2024-0001 --question "evidencia documental" --output data\processed\agent4_case_context_hito5.json`
  - Resultado: 2 documentos, 2 chunks, 2 evidencias y 2 citas.
- Validacion CLI con servicios tras Hito 5:
  - `docker compose ps qdrant`
  - Resultado: `procurewatch-qdrant` en estado `healthy`.
  - `python -m procurewatch agent4-smoke --check-services`
  - Resultado: Qdrant OK y Ollama OK.
  - `python -m procurewatch agent4-run-flow --contract-key PW-2024-0001 --question "evidencia documental" --use-services --output data\processed\agent4_case_context_hito5_services.json`
  - Resultado: Qdrant `procurement_documents`, 2 documentos, 2 chunks, 2 evidencias, 2 citas y
    generacion `ollama`.
  - Nota: `qwen3:8b` no soporta `/api/embed`; la corrida usa embeddings deterministas para Qdrant
    y registra warning hasta configurar un modelo de embeddings semantico.
- Validacion posterior con `bge-m3`:
  - `ollama list` muestra `bge-m3:latest`.
  - `bge-m3` responde en `/api/embed` con vectores de 1024 dimensiones.
  - `agent4-run-flow --use-services --embedding-model bge-m3 --collection procurement_documents_bge_m3`
    genera ficha con Qdrant real y Ollama sin warnings.
  - Se recrea la coleccion generada `procurement_documents`, que habia quedado con dimension 16
    por el fallback determinista, y se valida el flujo por defecto con `bge-m3`.
  - `agent4-run-flow --use-services` genera `agent4_case_context_hito5_bge_m3_default.json`
    sin warnings, con `embedding_model=bge-m3`, dimension 1024 y generacion `ollama`.
- Implementacion Hito 6:
  - Se crea `procurewatch agent4-case-context` como comando de ficha integrada.
  - Agent4 carga un contrato canonico desde `agent2_contracts_canonical.parquet`.
  - Agent2 se calcula en memoria con las reglas actuales (`missing_supplier`,
    `awarded_above_estimate`).
  - Agent3 se consume desde `agent3_agent2_features.parquet` si existe; si falta, se registra
    warning y el flujo continua.
  - La salida JSON conserva `agent2_score`, `contract_context`, `agent3_metrics_used`,
    evidencias documentales y citas.
- Validacion tras Hito 6:
  - `python -m pytest tests\test_agent4.py`
  - Resultado: 31 tests pasados.
  - `python -m ruff check scr\procurewatch\agent4 tests\test_agent4.py scr\procurewatch\cli.py`
  - Resultado: OK.
  - `python -m pytest tests`
  - Resultado: 50 tests pasados y 5 fallos en Agent1/Batch por permisos de `TemporaryDirectory`
    bajo `C:\Users\salfo\AppData\Local\Temp`; no afecta a Agent4.
  - Nota: pytest/ruff siguen mostrando avisos de cache por permisos locales en Windows.
- Implementacion Hito 7:
  - Se crea `procurewatch agent4-evaluate` como comando de evaluacion local.
  - Se define `data/synthetic/agent4_corpus/agent4_eval_set.json` con casos sinteticos para
    evidencia esperada y ausencia de documentos.
  - El reporte `agent4_evaluation_report.json` mide casos con evidencia, expectativa cumplida,
    precision@k aproximada, recall de documentos esperados, cobertura de citas, cobertura de
    terminos esperados y warnings.
  - RAGAS queda marcado como `not_run` por corpus sintetico pequeno.
- Validacion tras Hito 7:
  - `python -m pytest tests\test_agent4.py`
  - Resultado: 34 tests pasados.
  - `python -m ruff check scr\procurewatch\agent4 tests\test_agent4.py scr\procurewatch\cli.py`
  - Resultado: OK.
  - `python -m pytest tests`
  - Resultado: 53 tests pasados y 5 fallos en Agent1/Batch por permisos de `TemporaryDirectory`
    bajo `C:\Users\salfo\AppData\Local\Temp`; no afecta a Agent4.
- Endurecimiento posterior de Qdrant:
  - `QdrantVectorStore` valida la dimension vectorial de colecciones existentes antes de indexar.
  - Si una coleccion existe con dimension incompatible, Agent4 falla temprano con mensaje
    accionable para recrear la coleccion o usar otro nombre.
  - Se cubren casos de coleccion compatible, incompatible, REST fallback y dimension no
    detectable.
  - Validacion enfocada:
    - `python -m pytest tests\test_agent4.py`
    - Resultado: 39 tests pasados.
    - `python -m ruff check scr\procurewatch\agent4 tests\test_agent4.py`
    - Resultado: OK.
- Cierre integrado Agent3-Agent4:
  - Se crea [Cierre integrado Agent3-Agent4 2026-06-23](CIERRE_AGENT3_AGENT4_2026_06_23.md).
  - Artefactos generados en `data/processed/agent3_agent4_demo_2026_06_23/`.
  - Agent3 sobre canonico sintetico minimo:
    - 3 contratos;
    - 11 nodos;
    - 13 aristas;
    - 3 filas de features para Agent2/Agent4.
  - Agent4 sobre `PW-2024-0001`:
    - Agent2 `risk_score=0.5`;
    - flags `risky_procedure` y `awarded_above_estimate`;
    - metricas Agent3 presentes;
    - 2 evidencias documentales;
    - 2 citas.
  - Validacion enfocada final:
    - `python -m pytest -p no:cacheprovider tests\test_agent3.py tests\test_agent4.py`
    - Resultado: 52 tests pasados.
    - `python -m ruff check --no-cache scr\procurewatch\agent3 scr\procurewatch\agent4 tests\test_agent3.py tests\test_agent4.py`
    - Resultado: OK.

Estado por hitos:

| Hito | Estado al 2026-06-23 | Evidencia |
|---|---|---|
| Hito 0 - Base y trazabilidad | Implementado | Paquete importable, smoke test y tests Agent4 |
| Hito 1 - Corpus documental minimo | Implementado | Corpus sintetico y manifiesto documental |
| Hito 2 - Chunking y retrieval local | Implementado | Chunks deterministas y fallback keyword |
| Hito 3 - Qdrant y embeddings | Implementado como capa de codigo | Store Qdrant, filtros y embeddings Ollama; validacion real depende de servicio local |
| Hito 4 - LangGraph documental | Implementado | `agent4-run-flow` ejecuta PoC local y persiste salida |
| Hito 5 - Ficha explicable | Implementado con v1 determinista y ruta local Qdrant/Ollama | Salida JSON estructurada `case_context`; validacion con `--use-services`, Qdrant real y generacion `ollama` |
| Hito 6 - Integracion Agent2/Agent3 | Implementado como demo local reproducible | `agent4-case-context` combina contrato canonico, score Agent2, metricas Agent3 opcionales y RAG |
| Hito 7 - Evaluacion y cierre | Implementado como evaluacion local reproducible | `agent4-evaluate` genera reporte JSON con metricas de retrieval, citas y limitaciones |

Decisiones de continuidad:

- Mantener fallback local sin Qdrant ni LangGraph para tests reproducibles.
- No usar Agent4 para declarar fraude; la salida solo prioriza revision humana con evidencia
  documental trazable.
- Mantener `answer` y `citations` por compatibilidad, pero avanzar hacia `case_context` como
  contrato principal del Hito 5.
- Mantener fallback determinista para que los tests no dependan de servicios externos.
- Usar Ollama/Qwen3 cuando `--use-services` este activo y haya evidencia recuperada.
- Mantener PostgreSQL fuera del Hito 6; la persistencia operativa sigue siendo JSON local.
- Mantener RAGAS fuera del cierre actual hasta ampliar corpus documental real o semi-real.

Pendientes inmediatos:

- Ampliar corpus documental real o semi-real para evaluar retrieval con mas variabilidad.
- Usar el reporte de `agent4-evaluate` como base de resultados en memoria/defensa del TFM.
