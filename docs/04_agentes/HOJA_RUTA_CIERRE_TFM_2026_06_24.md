# Hoja de ruta de cierre TFM 2026-06-24

Objetivo del dia: dejar ProcureWatch en estado defendible para entrega, con integracion de ramas,
validacion tecnica, demo reproducible y documentacion alineada con el alcance realmente
implementado. Todo lo que no quede cerrado hoy pasa a limitaciones o trabajo futuro.

## Estado de partida

- Rama de trabajo: `integration/multiagent`.
- `origin/Satu` ya esta integrado en `integration/multiagent`.
- `sebas` queda integrado en `integration/multiagent` mediante merge local.
- Agent1: pipeline operativo y canonico para capas superiores.
- Agent2: red flags y scoring v1 implementados.
- Agent3: grafo, metricas, comunidades, Neo4j opcional y features para Agent2/Agent4.
- Agent4: RAG documental local, ficha explicable, citas y fallback offline.
- Dashboard: demo Streamlit Agent3-Agent4 en `frontend/agent3_demo.py`.

## Regla de cierre

No se anaden nuevas lineas grandes de producto salvo que desbloqueen la entrega. El foco es:

1. integrar;
2. validar;
3. documentar resultados;
4. preparar demo;
5. registrar limitaciones.

## Bloque 1 - Integracion Git

Tareas:

- Confirmar que `integration/multiagent` contiene `origin/Satu`.
- Fusionar el ultimo `sebas` en `integration/multiagent`.
- Preservar y revisar cambios locales de `frontend/agent3_demo.py`.
- Mantener `main` estable hasta decision final de promocion.

Criterio de hecho:

- `git status --short --branch` no muestra conflictos.
- La rama de integracion contiene el merge de `sebas` y el trabajo de `Satu`.
- Cualquier cambio no confirmado queda identificado antes de validar.

## Bloque 2 - Validacion tecnica minima

Comandos base:

```powershell
$env:PYTHONPATH="scr"
python -m procurewatch doctor
python -m pytest tests
python -m ruff check api scr tests frontend
```

Si el tiempo aprieta, validacion enfocada:

```powershell
$env:PYTHONPATH="scr"
python -m pytest tests\test_agent1.py tests\test_agent2.py tests\test_agent3.py tests\test_agent4.py tests\test_cli.py
python -m ruff check scr\procurewatch frontend tests\test_agent3.py tests\test_agent4.py
```

Criterio de hecho:

- Tests verdes o fallos documentados con causa y alcance.
- Ruff verde o excepciones justificadas.
- `doctor` no bloquea la demo local.

## Bloque 3 - Artefactos de demo reproducibles

Demo integrada Agent3-Agent4:

```powershell
$env:PYTHONPATH="scr"
python -c "from procurewatch.cli import main; raise SystemExit(main(['run-agent3','--input','data/processed/agent3_agent4_demo_2026_06_23/agent2_contracts_canonical_demo.parquet','--output-dir','data/processed/agent3_agent4_demo_2026_06_23']))"
python -c "from procurewatch.cli import main; raise SystemExit(main(['agent4-case-context','--contract-key','PW-2024-0001','--question','evidencia documental y riesgos explicables','--canonical-path','data/processed/agent3_agent4_demo_2026_06_23/agent2_contracts_canonical_demo.parquet','--agent3-features-path','data/processed/agent3_agent4_demo_2026_06_23/agent3_agent2_features.parquet','--output','data/processed/agent3_agent4_demo_2026_06_23/agent4_case_context_integrated_demo.json']))"
```

Dashboard:

```powershell
$env:PYTHONPATH="scr"
$env:PROCUREWATCH_AGENT3_DEMO_DIR="data/processed/agent3_agent4_demo_2026_06_23"
$env:PROCUREWATCH_AGENT4_CASE_CONTEXT="data/processed/agent3_agent4_demo_2026_06_23/agent4_case_context_integrated_demo.json"
streamlit run frontend/agent3_demo.py
```

Criterio de hecho:

- Existen `agent3_graph_report.json` y `agent4_case_context_integrated_demo.json`.
- El contrato `PW-2024-0001` muestra score, red flags, metricas de grafo y evidencias.
- El dashboard abre sin excepciones y permite explicar un caso completo.

## Bloque 4 - Memoria y documentacion

Actualizar o revisar:

- `docs/04_agentes/SEGUIMIENTO_AGENTES.md`: estado final de Agent1-Agent4.
- `docs/04_agentes/CIERRE_AGENT3_AGENT4_2026_06_23.md`: resultados de la demo integrada.
- `docs/DEMO_MVP.md`: comandos de ejecucion visibles para defensa.
- `docs/00_vision/PLANIFICACION_TFM.md`: alcance real frente a predeposito.
- README principal: comandos minimos y ruta de demo si aun no estan claros.

Contenido que debe quedar escrito para memoria:

- El sistema no declara fraude; prioriza revision humana.
- Agent1 entrega canonico reproducible.
- Agent2 calcula red flags y scoring determinista.
- Agent3 anade relaciones, centralidad y comunidades.
- Agent4 aporta evidencia documental citada.
- Las limitaciones principales son matching entre fuentes, corpus documental pequeno y evaluacion
  sin etiquetas completas de fraude.

Criterio de hecho:

- La documentacion no promete funcionalidades no implementadas.
- El lector puede reproducir la demo con una secuencia corta de comandos.
- Las limitaciones quedan en lenguaje academico, no como errores ocultos.

## Bloque 5 - Cierre de entrega

Checklist final:

- Rama actual: `integration/multiagent`.
- Merge de `sebas`: hecho.
- Integracion de `Satu`: verificada.
- Hoja de ruta de cierre: creada.
- Tests/ruff/doctor: ejecutados o documentados si fallan.
- Dashboard: ejecutado o documentado si falta dependencia local.
- Cambios revisados con `git status --short --branch`.
- Decidir si se hace push de `integration/multiagent`.
- Decidir si `main` se mantiene intacta o se promociona tras validacion.

## Fuera de alcance hoy

- Backend FastAPI productivo.
- Autenticacion, despliegue cloud o usuarios reales.
- Neo4j/Qdrant obligatorios en CI.
- RAGAS completo con corpus grande.
- Etiquetado juridico de fraude.
- Matching perfecto BOE/PLACE/OpenTender.

## Mensaje de defensa

ProcureWatch es un prototipo analitico multiagente para contratacion publica. Integra datos
abiertos, red flags, scoring, grafos y recuperacion documental para priorizar casos revisables con
trazabilidad. El resultado no sustituye una auditoria ni emite conclusiones juridicas; organiza
evidencia para supervision humana.
