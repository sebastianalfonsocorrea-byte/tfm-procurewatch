# Hoja de ruta sebas: cierre TFM y demo evaluable

Objetivo: usar `sebas` para cerrar las piezas no cubiertas por `Satu` y dejar una demo/MVP
defendible que pueda integrarse despues en `integration/multiagent`.

## Frontera entre ramas

`Satu` cubre:

- Agent1: ingesta, modelo analitico, cobertura y PostgreSQL opcional.
- Agent2: red flags, scoring y MVP RF-01..RF-06.

`sebas` debe cubrir:

- Agent3: grafo, metricas relacionales, Neo4j opcional y features para Agent2/Agent4.
- Agent4: corpus documental, RAG local/Qdrant, ficha trazable y evaluacion documental.
- Dashboard/demo integrada: grafo, ranking/casos y ficha explicable.
- Material de memoria: resultados, limitaciones, comandos reproducibles y guion de defensa.

La union final se valida en `integration/multiagent`; `main` queda estable.

## Hito S1 - Demo reproducible Agent3-Agent4

Estado actual:

- Agent3 y Agent4 ya tienen cierre tecnico defendible.
- Existe demo integrada documentada en
  [CIERRE_AGENT3_AGENT4_2026_06_23](CIERRE_AGENT3_AGENT4_2026_06_23.md).

Trabajo pendiente:

- Mantener una carpeta de demo con canonico, features, grafo y ficha `case_context`.
- Documentar un comando unico o una secuencia corta para regenerar artefactos.
- Garantizar que el contrato demo tiene:
  - score Agent2 calculable o compatible;
  - metricas Agent3;
  - evidencia Agent4;
  - citas documentales.

Criterio de cierre:

- `agent4_case_context_integrated_demo.json` existe y combina contrato, score, metricas, evidencias,
  citas y warnings.

## Hito S2 - Dashboard MVP

Objetivo: convertir la demo Agent3 en un tablero MVP de ProcureWatch.

Minimo aceptable:

- KPIs de grafo.
- Subgrafo filtrable.
- Casos explicables Agent3.
- Ficha Agent4 cargada desde JSON.
- Artefactos reproducibles visibles.

Fuera de alcance en `sebas`:

- Backend FastAPI productivo.
- Autenticacion, despliegue cloud o escritura en base de datos desde dashboard.
- Sustituir la integracion final de Agent1/2, que corresponde a `integration/multiagent`.

Comando recomendado:

```powershell
$env:PYTHONPATH="scr"
$env:PROCUREWATCH_AGENT3_DEMO_DIR="data/processed/agent3_agent4_demo_2026_06_23"
$env:PROCUREWATCH_AGENT4_CASE_CONTEXT="data/processed/agent3_agent4_demo_2026_06_23/agent4_case_context_integrated_demo.json"
streamlit run frontend/agent3_demo.py
```

## Hito S3 - Evaluacion y resultados para memoria

Entregables:

- Resumen de calidad de datos y limitaciones de matching.
- Resumen de Agent2 desde la rama integrada.
- Resumen de Agent3:
  - nodos;
  - aristas;
  - comunidades;
  - centralidades;
  - casos explicables.
- Resumen de Agent4:
  - casos evaluados;
  - evidencia recuperada;
  - cobertura de citas;
  - warnings;
  - motivo por el que RAGAS queda futuro si el corpus es pequeno.

Criterio de cierre:

- Existe una seccion de resultados reproducible y defendible para Entrega 3/predeposito.

## Hito S4 - Ajuste de memoria frente a la propuesta SASM

La propuesta tecnica SASM marca direccion, pero no obliga a implementar todo el alcance.

Ajustes necesarios:

- RF-01..RF-06 implementadas; RF-07..RF-15 quedan como trabajo futuro.
- Louvain/NetworkX implementado; Leiden queda como mejora futura si no se implementa.
- RAG local con corpus pequeno implementado; RAGAS completo queda futuro si no hay corpus suficiente.
- Dashboard MVP local implementado; plataforma productiva/API completa queda futura.
- Ningun modulo declara fraude; todos priorizan revision humana.

Criterio de cierre:

- La memoria describe el MVP real y no promete funcionalidades no implementadas.

## Hito S5 - Integracion final

Flujo:

1. Terminar y pushear `sebas`.
2. Fusionar `sebas` en `integration/multiagent`.
3. Fusionar/actualizar `Satu` en `integration/multiagent`.
4. Ejecutar validacion completa:

```powershell
$env:PYTHONPATH="scr"
python -m pytest tests
python -m procurewatch doctor
python -m procurewatch run-agent2 --input data/processed_sample/agent2_contracts_canonical.parquet --output-dir .tmp/agent2
python -m procurewatch run-agent3 --input data/processed_sample/agent2_contracts_canonical.parquet --output-dir .tmp/agent3
python -m procurewatch agent4-case-context --contract-key <contrato> --canonical-path data/processed_sample/agent2_contracts_canonical.parquet --agent3-features-path .tmp/agent3/agent3_agent2_features.parquet --output .tmp/case_context.json
```

Criterio de cierre:

- Tests verdes.
- Demo ejecutable.
- Memoria alineada con lo implementado.
- `main` permanece estable hasta decision final.
