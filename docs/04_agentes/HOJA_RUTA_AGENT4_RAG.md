# Hoja de ruta Agent4: documental, RAG y LangGraph

Objetivo: completar Agent4 como capa documental capaz de cargar documentos, crear chunks trazables, indexar en Qdrant, recuperar evidencia y generar contexto explicable para fichas de caso sin declarar fraude.

## Hito 0 - Base actual y trazabilidad

Estado:

- Existe scaffold en `scr/procurewatch/agent4/`.
- Ya hay:
  - `document_loader.py`
  - `chunking.py`
  - `retrieval.py`
  - `qdrant_store.py` con health check;
  - `graph.py` con flujo minimo/fallback;
  - `smoke.py`;
  - `tests/test_agent4.py`.

Pendiente:

- Separar claramente PoC local, Qdrant real, LangGraph real y generacion de ficha.
- Resolver entorno temporal de tests si vuelve a fallar `TemporaryDirectory` en Windows.

Criterio de cierre:

- Estado base documentado y smoke test estable.

## Hito 1 - Corpus documental minimo

Estado:

- Corpus sintetico minimo definido en `data/synthetic/agent4_corpus/`.
- Loaders ampliados para TXT, HTML y Markdown.
- Manifiesto generable con:

```powershell
procurewatch agent4-build-manifest
```

- Salida local esperada:
  - `data/processed/agent4_documents_manifest.json`

Implementado:

- Corpus de prueba:
  - TXT locales;
  - HTML simple;
  - Markdown como texto plano.
- Loaders:
  - TXT;
  - HTML con BeautifulSoup si esta instalado y fallback con `html.parser`;
  - Markdown como texto plano;
  - PDF queda fuera hasta incorporar Docling.
- Manifiesto:
  - `data/processed/agent4_documents_manifest.json`
- Metadatos obligatorios:
  - `document_id`
  - `contract_key_canon`
  - `source`
  - `source_record_id`
  - `document_type`
  - `text_hash`
  - `path` o URL de origen.

Criterio de cierre:

- Agent4 puede cargar un corpus pequeno y documentar sus metadatos.
- Hito cerrado cuando el commit `feat(agent4): add document corpus manifest` quede subido a
  `sebas`.

Tecnologias:

- pathlib, hashlib, BeautifulSoup, lxml, Docling futuro.

## Hito 2 - Chunking y retrieval local

Estado:

- Chunking endurecido para desarrollo local sin Qdrant.
- Retrieval local por keyword mantenido como fallback offline.
- Export `keyword_retrieve` disponible desde `procurewatch.agent4`.
- Ollama/modelo local y Qdrant quedan para Hito 3+.

Implementado:

- Mejorar chunking:
  - chunks deterministas;
  - solape configurable;
  - rechazo de texto vacio;
  - hashes por chunk;
  - preservacion de `document_id`, `chunk_id`, `contract_key_canon`.
- Mantener retrieval local por keyword como fallback.
- Crear tests:
  - texto vacio;
  - texto corto;
  - texto largo con solape;
  - payload completo;
  - retrieval con y sin resultados.

Criterio de cierre:

- Agent4 funciona sin Qdrant para desarrollo y tests unitarios.
- Hito cerrado cuando el commit `feat(agent4): harden chunking and local retrieval` quede subido
  a `sebas`.

Tecnologias:

- Python, dataclasses, hashing, tests unitarios.

## Hito 3 - Qdrant y embeddings

Estado:

- Store Qdrant real preparado para la coleccion `procurement_documents`.
- Embeddings via Ollama como PoC local configurable.
- BGE-M3 queda como objetivo metodologico posterior si se instala como modelo de embeddings.
- CLI demo disponible:

```powershell
procurewatch agent4-index-corpus --query "evidencia documental"
```

Implementado:

- Definir coleccion:
  - `procurement_documents`
- Crear store real:
  - crear coleccion si no existe;
  - upsert de chunks;
  - busqueda vectorial;
  - filtros por `contract_key_canon`, `source`, `document_type`.
- Elegir embeddings:
  - PoC via Ollama usando `PROCUREWATCH_OLLAMA_EMBEDDING_MODEL`;
  - objetivo metodologico posterior: BGE-M3.
- Registrar:
  - modelo de embeddings;
  - version;
  - fecha de indexacion;
  - dimensiones del vector.
- Mantener tests unitarios sin servicio y tests de integracion opcionales cuando Qdrant este activo.

Criterio de cierre:

- Un chunk se indexa y se recupera desde Qdrant con `document_id`, `chunk_id` y `contract_key_canon`.
- Hito cerrado cuando el commit `feat(agent4): add qdrant vector store` quede subido a `sebas`.

Tecnologias:

- Qdrant, qdrant-client, embeddings, Ollama/BGE-M3, Docker Compose.

## Hito 4 - LangGraph documental

Estado:

- Flujo documental completo preparado con fallback local si LangGraph no esta instalado.
- El flujo ejecuta una PoC de punta a punta sobre documentos locales del corpus sintetico.
- CLI demo disponible:

```powershell
procurewatch agent4-run-flow --contract-key PW-2024-0001 --question "evidencia documental"
```

Implementado:

- Completar flujo LangGraph:
  - `load_contract_context`
  - `discover_documents`
  - `extract_text`
  - `chunk_text`
  - `embed_and_upsert`
  - `retrieve_context`
  - `generate_case_context`
  - `persist_agent_output`
- Mantener fallback si LangGraph no esta instalado.
- Estado minimo:
  - `run_id`
  - `contract_key_canon`
  - `question`
  - `contract_context`
  - `document_refs`
  - `chunks`
  - `retrieved_context`
  - `answer`
  - `citations`
  - `warnings`.

Criterio de cierre:

- El grafo de Agent4 ejecuta una PoC de punta a punta con documentos locales.
- Hito cerrado cuando el commit `feat(agent4): complete langgraph case flow` quede subido a
  `sebas`.

Tecnologias:

- LangGraph, LangChain, TypedDict, orquestacion por estado.

## Hito 5 - Generacion de ficha explicable

Estado:

- Ficha JSON trazable v1 implementada en `case_context`.
- La salida mantiene compatibilidad con `answer` y `citations`.
- La generacion queda en modo determinista para tests y ejecucion offline.
- La ruta real con servicios queda disponible mediante:

```powershell
procurewatch agent4-run-flow --contract-key PW-2024-0001 --question "evidencia documental" --use-services
```

- Qdrant responde en Docker en `http://localhost:6333`; Agent4 valida `/healthz` y Docker usa
  un healthcheck TCP porque la imagen no trae `curl`.
- Ollama responde en local con `qwen3:8b` como modelo generativo.
- `bge-m3` queda como modelo de embeddings local via Ollama para indexar/consultar Qdrant.
- Limitacion observada: `qwen3:8b` no implementa `/api/embed`; se mantiene solo como modelo
  generativo.

Implementado:

- Crear prompt controlado:
  - responder solo con evidencia recuperada;
  - no declarar fraude;
  - indicar incertidumbre si falta evidencia;
  - citar `document_id` y `chunk_id`.
- Crear salida estructurada:
  - resumen;
  - evidencias;
  - citas;
  - advertencias;
  - campos usados del contrato;
  - metricas Agent3 usadas si existen.
- Tests:
  - sin evidencia;
  - con evidencia;
  - formato de citas;
  - advertencia obligatoria.
- Integracion local con servicios:
  - Qdrant real via Docker;
  - Ollama/Qwen3 para generar resumen;
  - fallback determinista de embeddings si el modelo principal no soporta `/api/embed`.

Nota de cierre:

- La coleccion `procurement_documents` se valida con `bge-m3` y dimension 1024 tras recrear la
  version que habia quedado con embeddings deterministas de 16 dimensiones.

Criterio de cierre:

- Agent4 genera una ficha textual/JSON trazable para un contrato con evidencia recuperada y
  resumen local via Ollama.

Tecnologias:

- Ollama, Qwen3, prompts estructurados, JSON.

## Hito 6 - Integracion con Agent2 y Agent3

Estado:

- Integracion local implementada con JSON como salida primaria.
- Comando disponible:

```powershell
procurewatch agent4-case-context --contract-key PW-2024-0001 --canonical-path data/processed_sample/agent2_contracts_canonical.parquet
```

- El canonico Agent2 real sigue siendo el origen por defecto:
  - `data/processed/agent2_contracts_canonical.parquet`
- Las metricas Agent3 se leen si existe:
  - `data/processed/agent3_agent2_features.parquet`
- Si Agent3 no existe para el contrato, Agent4 continua con warning.

Implementado:

- Agent4 debe recibir:
  - contrato canonico;
  - flags y score de Agent2 calculados en memoria con reglas actuales;
  - metricas de Agent3 si existen;
  - chunks recuperados desde Qdrant.
- Crear comando y funcion:
  - `procurewatch agent4-case-context --contract-key ...`
- Persistir salida:
  - JSON local primero, implementado;
  - PostgreSQL `agent_outputs` despues.
- Crear caso demo:
  - contrato con metricas Agent3;
  - una evidencia documental;
  - respuesta con citas y warnings.

Criterio de cierre:

- Una ficha combina dato estructurado, score Agent2, grafo Agent3 si existe y evidencia
  documental.

Tecnologias:

- pandas/PostgreSQL futuro, Qdrant, LangGraph, Ollama.

## Hito 7 - Evaluacion y cierre

Estado:

- Evaluacion local reproducible implementada.
- Comando disponible:

```powershell
procurewatch agent4-evaluate
```

- Eval set sintetico minimo:
  - `data/synthetic/agent4_corpus/agent4_eval_set.json`
- Reporte local:
  - `data/processed/agent4_evaluation_report.json`

Implementado:

- Evaluar retrieval:
  - precision@k aproximada por documentos esperados;
  - recall de documentos esperados;
  - cobertura de citas;
  - porcentaje de respuestas con evidencia;
  - cumplimiento de expectativa por caso.
- Evaluar RAG con RAGAS cuando haya corpus suficiente, documentado como futuro:
  - faithfulness;
  - answer relevancy;
  - context recall.
- Documentar limitaciones:
  - OCR/PDF si no esta cerrado;
  - corpus pequeno;
  - dependencia de calidad documental;
  - LLM solo explica, no decide.

Criterio de cierre:

- Agent4 queda defendible como PoC documental/RAG trazable con metricas locales, reporte JSON y
  limitaciones explicitas.

Tecnologias:

- Evaluacion local JSON, RAGAS futuro, documentacion tecnica.

## Cierre operativo 23/06/2026

Estado:

- Agent4 queda cerrado como PoC documental/RAG trazable.
- Se genera demo integrada con Agent3 en:
  - [Cierre integrado Agent3-Agent4 2026-06-23](CIERRE_AGENT3_AGENT4_2026_06_23.md)
- Se endurece Qdrant para validar la dimension vectorial de colecciones existentes antes de
  indexar. Si la coleccion fue creada con otra dimension, Agent4 falla temprano con mensaje
  accionable en lugar de fallar tarde en upsert o busqueda.
- La demo integrada offline genera ficha `case_context` para `PW-2024-0001` con:
  - score Agent2;
  - metricas Agent3;
  - 2 evidencias;
  - 2 citas;
  - frontera explicita de no declaracion de fraude.

Validacion:

- `python -m pytest -p no:cacheprovider tests\test_agent3.py tests\test_agent4.py`
  - Resultado: 52 passed.
- `python -m ruff check --no-cache scr\procurewatch\agent3 scr\procurewatch\agent4 tests\test_agent3.py tests\test_agent4.py`
  - Resultado: All checks passed.

Siguiente foco:

- Ampliar corpus real o semi-real para evaluar retrieval con mas variabilidad.
- Preparar dashboard/demo integrada final.
- Mantener Qdrant/Ollama como servicios opcionales para demo live y los tests como flujo offline
  reproducible.

## Orden recomendado de commits

1. `docs: add agent4 roadmap`
2. `feat(agent4): add document corpus manifest`
3. `feat(agent4): improve document loaders`
4. `feat(agent4): harden chunking and local retrieval`
5. `feat(agent4): add qdrant vector store`
6. `feat(agent4): add semantic retrieval`
7. `feat(agent4): complete langgraph case flow`
8. `feat(agent4): generate traceable case context`
9. `test(agent4): cover rag and evidence paths`
10. `feat(agent4): integrate agent2 agent3 case context`
11. `feat(agent4): add local rag evaluation report`
