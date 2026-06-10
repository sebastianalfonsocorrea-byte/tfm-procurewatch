# Plan de Agent4: NLP, scraping, RAG y LangGraph

Objetivo: trabajar Agent4 como agente documental, conectado a Qdrant, Ollama y LangGraph, usando
contratos canonicos como contexto estructurado.

## Rol de Agent4

Agent4 no calcula el score principal. Su funcion es:

- descargar o recibir documentos publicos;
- extraer texto y metadatos;
- crear chunks trazables;
- generar embeddings;
- indexar en Qdrant;
- recuperar evidencia textual por contrato o pregunta;
- producir contexto para fichas explicables.

## Stack de Agent4

- BeautifulSoup + lxml para HTML/XML.
- spaCy para NLP clasico en espanol.
- Qdrant para vector store local.
- BGE-M3 como embedding objetivo.
- Ollama con Qwen3-8B como LLM local de explicacion.
- LangGraph para orquestacion por estado.
- LangChain solo como capa util de conectores cuando aporte valor.

## Estructura propuesta de codigo

Ruta actual/recomendada:

```text
scr/procurewatch/agent4/
  __init__.py
  state.py
  graph.py
  nodes.py
  prompts.py
  document_loader.py
  chunking.py
  embeddings.py
  qdrant_store.py
  retrieval.py
  schemas.py
```

Regla de estructura: `data/` guarda datasets y artefactos generados; `scr/procurewatch/data_sources/`
guarda conectores/parsers de fuentes externas; `scr/procurewatch/agent4/` guarda NLP, RAG y
orquestacion documental.

## Estado LangGraph v1

Estado minimo:

- `run_id`
- `contract_key_canon`
- `source_record_id`
- `question`
- `contract_context`
- `document_refs`
- `chunks`
- `retrieved_context`
- `answer`
- `citations`
- `warnings`

## Grafo LangGraph v1

Flujo recomendado:

```text
load_contract_context
  -> discover_documents
  -> extract_text
  -> chunk_text
  -> embed_and_upsert
  -> retrieve_context
  -> generate_case_context
  -> persist_agent_output
```

Para una primera PoC se puede saltar `discover_documents` y trabajar con documentos/textos ya
descargados.

## Qdrant

Coleccion inicial:

- `procurement_documents`

Payload obligatorio:

- `document_id`
- `chunk_id`
- `contract_key_canon`
- `source`
- `source_record_id`
- `document_type`
- `text`
- `text_hash`
- `created_at`

## Ollama y modelos

Modelo LLM objetivo:

- `qwen3:8b`

Modelos alternativos si el equipo no tiene suficiente VRAM/RAM:

- `qwen3:4b`
- `mistral`

Embeddings:

- BGE-M3 como objetivo metodologico.
- Si se usa Ollama para embeddings en una PoC, documentar la diferencia y no mezclar resultados
  sin registrar modelo/version.

## Entregables v1

- Stack instalado o identificado.
- Qdrant y Ollama arrancables en local.
- Estructura de paquete Agent4 definida.
- Estado LangGraph documentado.
- Primera coleccion Qdrant definida.
- Primer flujo RAG acotado a un contrato o documento de prueba.

## Criterios de aceptacion

- `procurewatch doctor` detecta variables de servicios cuando esten configuradas.
- Qdrant responde en local.
- Ollama responde en local con el modelo elegido.
- Agent4 puede recuperar un chunk por similitud y devolver evidencia con `contract_key_canon`.
- La respuesta de Agent4 incluye advertencia si no hay evidencia suficiente.
