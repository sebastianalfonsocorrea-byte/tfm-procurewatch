# Resultados Agent3: demo tecnica independiente

## Objetivo

Cerrar Agent3 como MVP tecnico demostrable sin depender del cierre de Agent2, Agent4 o del
dashboard global. La demo usa artefactos generados por `run-agent3` y muestra senales
relacionales explicables para revision humana.

## Como ejecutar la demo

Generar artefactos Agent3:

```powershell
$env:PYTHONPATH='scr'
python -c "from procurewatch.cli import main; raise SystemExit(main(['run-agent3','--input','data/processed/agent2_contracts_canonical.parquet','--output-dir','data/processed']))"
```

Abrir Streamlit:

```powershell
$env:PYTHONPATH='scr'
streamlit run frontend/agent3_demo.py
```

Si se usa una carpeta de muestra:

```powershell
$env:PROCUREWATCH_AGENT3_DEMO_DIR='data/processed/agent3_demo_sample'
streamlit run frontend/agent3_demo.py
```

## Artefactos usados

- `agent3_nodes.parquet`
- `agent3_edges.parquet`
- `agent3_entity_metrics.parquet`
- `agent3_communities.parquet`
- `agent3_agent2_features.parquet`
- `agent3_network_summary.json`
- `agent3_graph_report.json`

## Vistas de la demo

- Resumen: contratos, nodos, aristas, comunidades, nodos por tipo, aristas por tipo y top
  comunidades.
- Red: subgrafo filtrable por tipo de nodo, comunidad y numero maximo de nodos.
- Casos: tres ejemplos explicables basados en recurrencia, concentracion y centralidad.
- Artefactos: rutas de salida y resumen tecnico de red.

## Casos explicables

- Proveedor recurrente: prioriza contratos con mayor recurrencia comprador-proveedor.
- Concentracion comprador-proveedor: prioriza contratos con mayor peso del proveedor dentro del
  comprador.
- Contrato central en la red: prioriza contratos con mayor betweenness o presencia en comunidad
  relevante.

## Limitaciones

- La demo no declara fraude.
- Las senales no sustituyen el scoring final de Agent2.
- La calidad depende de `contract_key_canon`, IDs de entidades y cobertura de proveedores.
- El subgrafo de Streamlit esta limitado para que la demo sea fluida.
- El dashboard global del TFM queda para una integracion posterior.

## Estado MVP

Agent3 queda cerrado como MVP tecnico y demostrable:

- genera grafo reproducible;
- calcula metricas relacionales y comunidades;
- carga Neo4j de forma idempotente;
- prepara features para Agent2;
- ofrece una demo Streamlit independiente con casos interpretables.
