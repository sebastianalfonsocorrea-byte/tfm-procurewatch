# Plan de Agent3: grafos y relaciones

Objetivo: definir Agent3 como la capa de analisis de redes sobre contratos, organismos,
adjudicatarios, CPV y fuentes, sin sustituir el origen tabular trazable.

## Rol de Agent3

Agent3 construye una vista relacional derivada para detectar patrones que no se ven bien en tablas:

- recurrencia comprador-proveedor;
- concentracion de adjudicaciones;
- comunidades o clusters de entidades;
- centralidad de compradores, proveedores o CPV;
- relaciones indirectas entre contratos, fuentes y entidades.

Agent3 no descarga datos ni calcula el score final por si solo. Sus metricas alimentan Agent2 y el
dashboard.

## Entrada

Entrada minima actual:

- `data/processed/agent2_contracts_canonical.parquet`
- `data/processed/agent2_contracts_canonical_schema.json`

Cuando PostgreSQL este disponible, la entrada preferente sera la tabla canonica `contracts` y las
dimensiones `buyers`, `suppliers`, `cpv` y `sources`.

## Salida

Salidas previstas:

- tablas derivadas `nodes_*` y `edges_*` en Parquet o PostgreSQL;
- carga idempotente en Neo4j;
- metricas de red exportables para Agent2:
  - grado comprador/proveedor;
  - recurrencia comprador-proveedor;
  - concentracion por proveedor;
  - comunidades;
  - centralidad.

Cada salida debe conservar `contract_key_canon`, `source`, `source_record_id` y, cuando exista,
`source_snapshot_id`.

## Modelo minimo de grafo

Nodos:

- `Buyer`
- `Supplier`
- `Contract`
- `CPV`
- `Source`

Relaciones:

- `(:Buyer)-[:PUBLISHED]->(:Contract)`
- `(:Contract)-[:AWARDED_TO]->(:Supplier)`
- `(:Contract)-[:HAS_CPV]->(:CPV)`
- `(:Contract)-[:FROM_SOURCE]->(:Source)`

## Stack

- NetworkX para calculo reproducible en local.
- Neo4j como capa derivada para exploracion y consultas de relaciones.
- PostgreSQL o Parquet como origen canonico; Neo4j no es fuente primaria.

## Criterios de aceptacion

- Agent3 genera nodos y edges desde el canonico sin leer fuentes raw.
- La carga o exportacion es idempotente por clave estable.
- Las metricas derivadas pueden unirse de vuelta a `contract_key_canon`.
- Se documentan nulos y limitaciones antes de usar las metricas en scoring.
