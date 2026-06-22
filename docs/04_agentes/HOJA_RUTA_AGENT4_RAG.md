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

TODO:

- Definir corpus de prueba:
  - TXT locales;
  - HTML simple;
  - documentos PLACE/BOE seleccionados si ya existen enlaces o archivos.
- Ampliar loaders:
  - TXT;
  - HTML con BeautifulSoup;
  - Markdown si se usa Docling mas adelante;
  - PDF solo cuando Docling este incorporado.
- Crear manifiesto:
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

Tecnologias:

- pathlib, hashlib, BeautifulSoup, lxml, Docling futuro.

## Hito 2 - Chunking y retrieval local

TODO:

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

Tecnologias:

- Python, dataclasses, hashing, tests unitarios.

## Hito 3 - Qdrant y embeddings

TODO:

- Definir coleccion:
  - `procurement_documents`
- Crear store real:
  - crear coleccion si no existe;
  - upsert de chunks;
  - busqueda vectorial;
  - filtros por `contract_key_canon`, `source`, `document_type`.
- Elegir embeddings:
  - objetivo metodologico: BGE-M3;
  - alternativa PoC: embeddings via Ollama si BGE-M3 no esta preparado.
- Registrar:
  - modelo de embeddings;
  - version;
  - fecha de indexacion;
  - dimensiones del vector.
- Mantener tests unitarios sin servicio y tests de integracion opcionales cuando Qdrant este activo.

Criterio de cierre:

- Un chunk se indexa y se recupera desde Qdrant con `document_id`, `chunk_id` y `contract_key_canon`.

Tecnologias:

- Qdrant, qdrant-client, embeddings, Ollama/BGE-M3, Docker Compose.

## Hito 4 - LangGraph documental

TODO:

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

Tecnologias:

- LangGraph, LangChain, TypedDict, orquestacion por estado.

## Hito 5 - Generacion de ficha explicable

TODO:

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
- Integrar LLM local:
  - Qwen3 via Ollama como objetivo;
  - fallback sin LLM para tests.
- Tests:
  - sin evidencia;
  - con evidencia;
  - formato de citas;
  - advertencia obligatoria.

Criterio de cierre:

- Agent4 genera una ficha textual/JSON trazable para un contrato.

Tecnologias:

- Ollama, Qwen3, prompts estructurados, JSON.

## Hito 6 - Integracion con Agent2 y Agent3

TODO:

- Agent4 debe recibir:
  - contrato canonico;
  - flags y score de Agent2;
  - metricas de Agent3;
  - chunks recuperados desde Qdrant.
- Crear comando o funcion:
  - `procurewatch agent4-case-context --contract-key ...`
- Persistir salida:
  - JSON local primero;
  - PostgreSQL `agent_outputs` despues.
- Crear caso demo:
  - contrato con metricas Agent3;
  - una evidencia documental;
  - respuesta con citas y warnings.

Criterio de cierre:

- Una ficha combina dato estructurado, grafo y evidencia documental.

Tecnologias:

- pandas/PostgreSQL futuro, Qdrant, LangGraph, Ollama.

## Hito 7 - Evaluacion y cierre

TODO:

- Evaluar retrieval:
  - precision manual de top-k;
  - cobertura de citas;
  - porcentaje de respuestas con evidencia.
- Evaluar RAG con RAGAS cuando haya corpus suficiente:
  - faithfulness;
  - answer relevancy;
  - context recall.
- Documentar limitaciones:
  - OCR/PDF si no esta cerrado;
  - corpus pequeno;
  - dependencia de calidad documental;
  - LLM solo explica, no decide.

Criterio de cierre:

- Agent4 queda defendible como PoC documental/RAG trazable.

Tecnologias:

- RAGAS, evaluacion manual, documentacion tecnica.

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
