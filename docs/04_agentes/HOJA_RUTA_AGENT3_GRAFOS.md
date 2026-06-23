# Hoja de ruta Agent3: grafos y relaciones

Objetivo: completar Agent3 como capa de grafos derivada del canonico, capaz de generar artefactos reproducibles, cargar Neo4j y producir metricas relacionales para Agent2, Agent4 y dashboard.

## Hito 0 - Base actual y trazabilidad

Estado:

- Existe `scr/procurewatch/agent3/` con schemas, loader, generacion de nodos/aristas y metricas basicas.
- Existe `tests/test_agent3.py`.
- Trabajo base commiteado en `86239c9 feat(agent3): add graph foundation and organize docs`.
- Validacion actual:
  - `python -m pytest -p no:cacheprovider tests\test_agent3.py`
  - `python -m ruff check --no-cache scr\procurewatch\agent3 tests\test_agent3.py`

Pendiente:

- No mezclar cambios de `data/` ni PDFs no trackeados con commits de codigo.

Criterio de cierre:

- Agent3 local v1 queda commiteado y trazado.

## Hito 1 - Agent3 ejecutable local

Estado:

- Implementada funcion de orquestacion `run_agent3`.
- Lectura de `data/processed/agent2_contracts_canonical.parquet` o ruta equivalente por parametro.
- Exportacion de artefactos:
  - `data/processed/agent3_nodes.parquet`
  - `data/processed/agent3_edges.parquet`
  - `data/processed/agent3_contract_metrics.parquet`
  - `data/processed/agent3_graph_report.json`
- Reporte JSON con:
  - filas de entrada;
  - nodos por tipo;
  - aristas por tipo;
  - contratos sin proveedor;
  - contratos sin CPV;
  - fecha de ejecucion;
  - version de Agent3.
- CLI anadida:
  - `procurewatch run-agent3 --input data/processed/agent2_contracts_canonical.parquet --output-dir data/processed`
- Tests anadidos para lectura, escritura, reporte y comando CLI.

Validacion:

- `python -m pytest -p no:cacheprovider tests\test_agent3.py tests\test_cli.py`
- `python -m ruff check --no-cache scr\procurewatch\agent3 scr\procurewatch\cli.py tests\test_agent3.py tests\test_cli.py`

Criterio de cierre:

- Cerrado cuando el commit del hito quede subido a `sebas`.

Tecnologias:

- pandas, pyarrow, Parquet, JSON, argparse.

## Hito 2 - Grafo Neo4j minimo

Estado:

- Implementado modulo `neo4j_store.py`.
- Definidos constraints:
  - `Buyer(node_id)`
  - `Supplier(node_id)`
  - `Contract(node_id)`
  - `CPV(node_id)`
  - `Source(node_id)`
- Carga de nodos con `MERGE`.
- Carga de aristas con `MERGE` por `edge_id`.
- Conservadas propiedades:
  - `contract_key_canon`
  - `source`
  - `source_record_id`
  - `edge_type`
- CLI anadida:
  - `procurewatch agent3-load-neo4j --nodes ... --edges ...`
- Consultas de control:
  - conteo de nodos por tipo;
  - conteo de relaciones por tipo;
  - top compradores;
  - top proveedores;
  - vecinos de un contrato.

Validacion real:

- Docker Desktop disponible con Neo4j `neo4j:5-community`.
- Carga sobre muestra canonica temporal de 500 contratos.
- Primera y segunda carga mantienen los mismos conteos:
  - nodos: Buyer 15, CPV 71, Contract 500, Source 1, Supplier 193.
  - aristas: AWARDED_TO 500, FROM_SOURCE 500, HAS_CPV 1097, PUBLISHED 500.

Criterio de cierre:

- Cerrado cuando el commit del hito quede subido a `sebas`.

Tecnologias:

- Neo4j Community, Cypher, neo4j Python driver, Docker Compose.

## Hito 3 - Metricas avanzadas de red

Estado:

- Implementado calculo de metricas con NetworkX:
  - degree centrality;
  - betweenness centrality;
  - connected components;
  - numero de vecinos por entidad;
  - contratos por comunidad o componente.
- Implementada deteccion de comunidades Louvain con semilla fija para reproducibilidad.
- Exportacion anadida:
  - `agent3_entity_metrics.parquet`
  - `agent3_communities.parquet`
  - `agent3_network_summary.json`
- Limitaciones documentadas para siguientes hitos:
  - proveedores nulos;
  - identificadores incompletos;
  - matching entre fuentes todavia imperfecto.

Criterio de cierre:

- Cerrado cuando el commit del hito quede subido a `sebas` y pase la comprobacion integral.

Tecnologias:

- NetworkX, python-louvain, pandas.

## Hito 4 - Integracion con Agent2

Estado:

- Preparado contrato de features Agent3 para red flags futuras:
  - RF-03 recurrencia comprador-proveedor;
  - RF-04 concentracion proveedor/comprador;
  - centralidades como senales auxiliares.
- Definido contrato de salida:
  - `contract_key_canon`
  - metricas contractuales;
  - version de Agent3;
  - fecha de calculo.
- Exportacion anadida:
  - `agent3_agent2_features.parquet`
  - `agent3_agent2_features_schema.json`
- Agent2 todavia no se implementa en este hito; queda preparado para consumir features sin recalcular grafo.

Criterio de cierre:

- Cerrado cuando el commit del hito quede subido a `sebas`.

Tecnologias:

- pandas joins, feature engineering, scoring explicable.

## Hito 5 - Demostrador y documentacion de Agent3

Decision de alcance:

- Este hito se realizara como cierre demostrable propio de Agent3.
- No depende de que Agent2, Agent4 o el dashboard global esten terminados.
- El dashboard final integrado queda fuera de este hito; aqui se prepara una demo tecnica reutilizable.

Estado:

- Preparada demo Streamlit propia de Agent3:
  - nodos filtrables;
  - aristas filtrables;
  - comunidades;
  - top entidades.
- Preparados 3 casos explicables:
  - contrato con proveedor recurrente;
  - comprador concentrado;
  - subgrafo/comunidad interesante.
- Documentado para memoria/demo:
  - modelo de grafo;
  - metricas calculadas;
  - limitaciones;
  - no declaracion de fraude.
- Se deja claro que las salidas de Agent3 son senales relacionales, no scoring final.

Criterio de cierre:

- Cerrado cuando el commit del hito quede subido a `sebas`.

Tecnologias:

- Streamlit/Plotly o Neo4j Browser para demo tecnica; PyVis/Sigma.js queda como opcion futura.

## Cierre operativo 23/06/2026

Estado:

- Agent3 queda cerrado como MVP tecnico defendible.
- Se genera demo integrada con Agent4 en:
  - [Cierre integrado Agent3-Agent4 2026-06-23](CIERRE_AGENT3_AGENT4_2026_06_23.md)
- La demo integrada usa un canonico sintetico minimo para alinear:
  - contrato `PW-2024-0001`;
  - features Agent3;
  - score Agent2;
  - evidencias Agent4.

Validacion:

- `python -m pytest -p no:cacheprovider tests\test_agent3.py tests\test_agent4.py`
  - Resultado: 52 passed.
- `python -m ruff check --no-cache scr\procurewatch\agent3 scr\procurewatch\agent4 tests\test_agent3.py tests\test_agent4.py`
  - Resultado: All checks passed.

Siguiente foco:

- Preparar dashboard/demo integrada final.
- Mantener como limitacion metodologica la calidad de identificadores de comprador, proveedor y
  `contract_key_canon`.

## Orden recomendado de commits

1. `docs: add agent3 roadmap`
2. `feat(agent3): export graph artifacts`
3. `feat(cli): add run-agent3 command`
4. `feat(agent3): load graph into neo4j`
5. `feat(agent3): compute advanced network metrics`
6. `feat(agent2): consume agent3 graph metrics`
7. `feat(agent3): add standalone graph demo`
