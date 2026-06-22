# Hoja de ruta Agent3: grafos y relaciones

Objetivo: completar Agent3 como capa de grafos derivada del canonico, capaz de generar artefactos reproducibles, cargar Neo4j y producir metricas relacionales para Agent2, Agent4 y dashboard.

## Hito 0 - Base actual y trazabilidad

Estado:

- Existe `scr/procurewatch/agent3/` con schemas, loader, generacion de nodos/aristas y metricas basicas.
- Existe `tests/test_agent3.py`.
- Validacion actual:
  - `python -m pytest -p no:cacheprovider tests\test_agent3.py`
  - `python -m ruff check --no-cache scr\procurewatch\agent3 tests\test_agent3.py`

Pendiente:

- Hacer commits atomicos del trabajo actual.
- No mezclar cambios de `data/` ni PDFs no trackeados con commits de codigo.

Criterio de cierre:

- Agent3 local v1 queda commiteado y trazado.

## Hito 1 - Agent3 ejecutable local

TODO:

- Crear funcion de orquestacion `run_agent3`.
- Leer `data/processed/agent2_contracts_canonical.parquet`.
- Exportar artefactos:
  - `data/processed/agent3_nodes.parquet`
  - `data/processed/agent3_edges.parquet`
  - `data/processed/agent3_contract_metrics.parquet`
  - `data/processed/agent3_graph_report.json`
- Incluir reporte con:
  - filas de entrada;
  - nodos por tipo;
  - aristas por tipo;
  - contratos sin proveedor;
  - contratos sin CPV;
  - fecha de ejecucion;
  - version de Agent3.
- Anadir CLI:
  - `procurewatch run-agent3 --input data/processed/agent2_contracts_canonical.parquet --output-dir data/processed`

Criterio de cierre:

- `run-agent3` genera outputs locales reproducibles sin Neo4j.
- Tests cubren lectura, escritura y reporte.

Tecnologias:

- pandas, pyarrow, Parquet, JSON, argparse.

## Hito 2 - Grafo Neo4j minimo

TODO:

- Crear modulo `neo4j_store.py`.
- Definir constraints:
  - `Buyer(node_id)`
  - `Supplier(node_id)`
  - `Contract(node_id)` o `Contract(contract_key_canon)`
  - `CPV(node_id)`
  - `Source(node_id)`
- Cargar nodos con `MERGE`.
- Cargar aristas con `MERGE`.
- Conservar propiedades:
  - `contract_key_canon`
  - `source`
  - `source_record_id`
  - `edge_type`
- Anadir CLI:
  - `procurewatch agent3-load-neo4j --nodes ... --edges ...`
- Crear consultas de control:
  - conteo de nodos por tipo;
  - conteo de relaciones por tipo;
  - top compradores;
  - top proveedores;
  - vecinos de un contrato.

Criterio de cierre:

- Ejecutar la carga dos veces no duplica nodos ni relaciones.
- Neo4j muestra grafo basico consultable.

Tecnologias:

- Neo4j Community, Cypher, neo4j Python driver, Docker Compose.

## Hito 3 - Metricas avanzadas de red

TODO:

- Calcular metricas con NetworkX:
  - degree centrality;
  - betweenness centrality;
  - connected components;
  - numero de vecinos por entidad;
  - contratos por comunidad o componente.
- Preparar deteccion de comunidades:
  - Louvain como primera opcion;
  - Leiden como referencia metodologica si se incorpora dependencia viable.
- Exportar:
  - `agent3_entity_metrics.parquet`
  - `agent3_communities.parquet`
  - `agent3_network_summary.json`
- Documentar limitaciones:
  - proveedores nulos;
  - identificadores incompletos;
  - matching entre fuentes todavia imperfecto.

Criterio de cierre:

- Metricas de entidad y comunidad pueden unirse con contratos o dashboard.

Tecnologias:

- NetworkX, python-louvain, pandas.

## Hito 4 - Integracion con Agent2

TODO:

- Entregar features para red flags:
  - RF-03 recurrencia comprador-proveedor;
  - RF-04 concentracion proveedor/comprador;
  - centralidades como senales auxiliares.
- Definir contrato de salida:
  - `contract_key_canon`
  - metricas contractuales;
  - version de Agent3;
  - fecha de calculo.
- Ajustar tests de Agent2 cuando consuma metricas.

Criterio de cierre:

- Agent2 puede usar metricas Agent3 sin recalcular grafo.

Tecnologias:

- pandas joins, feature engineering, scoring explicable.

## Hito 5 - Integracion con dashboard y memoria

TODO:

- Preparar dataset para visualizacion:
  - nodos filtrables;
  - aristas filtrables;
  - comunidades;
  - top entidades.
- Preparar 2 o 3 casos explicables:
  - contrato con proveedor recurrente;
  - comprador concentrado;
  - subgrafo/comunidad interesante.
- Documentar en memoria:
  - modelo de grafo;
  - metricas calculadas;
  - limitaciones;
  - no declaracion de fraude.

Criterio de cierre:

- Agent3 puede demostrarse con grafo, metricas y narrativa defendible.

Tecnologias:

- PyVis/Sigma.js futuro, Streamlit, Plotly, Neo4j Browser.

## Orden recomendado de commits

1. `docs: add agent3 roadmap`
2. `feat(agent3): export graph artifacts`
3. `feat(cli): add run-agent3 command`
4. `feat(agent3): load graph into neo4j`
5. `feat(agent3): compute advanced network metrics`
6. `feat(agent2): consume agent3 graph metrics`
7. `docs: document agent3 graph results`
