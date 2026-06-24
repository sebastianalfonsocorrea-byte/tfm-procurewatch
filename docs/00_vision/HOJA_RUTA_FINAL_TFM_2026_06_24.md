# Hoja de ruta final TFM 2026-06-24

Objetivo: cerrar `integration/multiagent` como rama candidata a entrega y promocion a la rama
principal, con las ramas de Sebas y Satu unificadas, todos los agentes funcionando en conjunto,
dashboard explorable y documentacion alineada con el MVP real.

La prioridad ya no es ampliar alcance. La prioridad es integrar, validar, demostrar y dejar una
ruta clara para pasar de integracion a rama principal sin introducir riesgos de ultima hora.

## Decision de alcance final

ProcureWatch se presenta como prototipo analitico multiagente, no como plataforma productiva.

Debe quedar cerrado:

- rama `integration/multiagent` como rama tecnica de entrega;
- integracion de los trabajos de `sebas` y `Satu`;
- pipeline de datos y salida canonica;
- Agent2 con red flags y scoring explicable;
- Agent3 con grafo, relaciones, metricas y features;
- Agent4 con ficha documental, evidencias y citas;
- dashboard local para explorar resultados de forma clara;
- memoria y documentacion sin prometer funcionalidades no implementadas;
- gate objetivo para promocionar a rama principal.

Queda fuera del cierre:

- nuevas fuentes de datos;
- nuevas reglas grandes de scoring;
- refactors estructurales;
- despliegue cloud;
- autenticacion y usuarios;
- backend FastAPI productivo;
- matching perfecto entre BOE, PLACE y OpenTender;
- evaluacion RAGAS completa con corpus grande;
- Neo4j, Qdrant, Ollama o Docker como requisitos obligatorios de demo;
- cualquier afirmacion juridica de fraude.

Regla de comunicacion del TFM: el sistema prioriza revision humana con evidencia trazable; no
declara fraude ni sustituye una auditoria.

## Estado de integracion confirmado

Rama de trabajo:

```text
integration/multiagent
```

Estado observado el 2026-06-24:

- `origin/Satu` esta contenido en `integration/multiagent`.
- `origin/sebas` esta contenido en `integration/multiagent`.
- El arbol de trabajo esta limpio.
- La rama local `integration/multiagent` va por delante de `origin/integration/multiagent`.
- La rama principal local detectada es `master`; si el equipo usa el nombre `main`, debe tratarse
  como la rama principal objetivo antes de promocionar.

Comandos de control:

```powershell
git status --short --branch
git merge-base --is-ancestor origin/Satu HEAD
git merge-base --is-ancestor origin/sebas HEAD
git log --oneline --graph --decorate --all -12
```

## Hito 1 - Integracion funcional de agentes

Objetivo: confirmar que Agent1, Agent2, Agent3 y Agent4 estan unificados en la rama de integracion
y que cada uno conserva una entrada, proceso, salida y limitacion explicables.

Estado esperado:

| Agente | Entrada | Salida defendible | Criterio de hecho |
|---|---|---|---|
| Agent1 | BOE, PLACE, OpenTender | `agent2_contracts_canonical.parquet` | Canonico reproducible y calidad documentada |
| Agent2 | Canonico Agent1 | scores y flags | Red flags deterministas y explicables |
| Agent3 | Canonico o demo canonica | nodos, aristas, metricas y features | Grafo derivado sin depender de servicios externos |
| Agent4 | Contrato, features y corpus | ficha con evidencias y citas | Respuesta trazable con fallback offline |

Comandos base:

```powershell
$env:PYTHONPATH="scr"
python -m procurewatch doctor
python -m procurewatch run-agent2 --input data/processed/agent2_contracts_canonical.parquet --output-dir data/processed
```

Criterio de cierre:

- no hay errores de importacion entre agentes;
- Agent2 puede operar sobre el canonico de Agent1;
- Agent3 puede generar features relacionales consumibles por Agent2/Agent4;
- Agent4 puede generar ficha integrada para un contrato;
- las limitaciones quedan documentadas, especialmente el matching actual entre fuentes.

## Hito 2 - Demo integrada reproducible

Objetivo: regenerar una demo pequena, estable y explicable que muestre el flujo completo sin
depender de Docker ni servicios externos.

Ruta oficial de demo:

```text
data/processed/agent3_agent4_demo_2026_06_23/
```

Caso principal:

```text
PW-2024-0001
```

Artefactos esperados:

- `agent2_contracts_canonical_demo.parquet`
- `agent3_graph_report.json`
- `agent3_nodes.parquet`
- `agent3_edges.parquet`
- `agent3_agent2_features.parquet`
- `agent4_case_context_integrated_demo.json`

Regeneracion Agent3:

```powershell
$env:PYTHONPATH="scr"
python -c "from procurewatch.cli import main; raise SystemExit(main(['run-agent3','--input','data/processed/agent3_agent4_demo_2026_06_23/agent2_contracts_canonical_demo.parquet','--output-dir','data/processed/agent3_agent4_demo_2026_06_23']))"
```

Regeneracion Agent4:

```powershell
$env:PYTHONPATH="scr"
python -c "from procurewatch.cli import main; raise SystemExit(main(['agent4-case-context','--contract-key','PW-2024-0001','--question','evidencia documental y riesgos explicables','--canonical-path','data/processed/agent3_agent4_demo_2026_06_23/agent2_contracts_canonical_demo.parquet','--agent3-features-path','data/processed/agent3_agent4_demo_2026_06_23/agent3_agent2_features.parquet','--output','data/processed/agent3_agent4_demo_2026_06_23/agent4_case_context_integrated_demo.json']))"
```

Criterio de cierre:

- `PW-2024-0001` muestra score Agent2;
- existen red flags explicables;
- existen metricas relacionales Agent3;
- existen evidencias y citas Agent4;
- la demo puede explicarse de principio a fin en defensa.

## Hito 3 - Dashboard de exploracion

Objetivo: dejar un dashboard local que permita explorar resultados sin obligar al tribunal o al
equipo a leer Parquet/JSON manualmente.

Dashboard oficial:

```text
frontend/agent3_demo.py
```

Ejecucion:

```powershell
$env:PYTHONPATH="scr"
$env:PROCUREWATCH_AGENT3_DEMO_DIR="data/processed/agent3_agent4_demo_2026_06_23"
$env:PROCUREWATCH_AGENT4_CASE_CONTEXT="data/processed/agent3_agent4_demo_2026_06_23/agent4_case_context_integrated_demo.json"
streamlit run frontend/agent3_demo.py
```

Debe permitir explorar:

- vista general y KPIs;
- red de compradores, proveedores, contratos, CPV y fuentes;
- caso seleccionado;
- senales Agent2;
- metricas Agent3;
- evidencias y citas Agent4;
- debug tecnico con rutas y payloads.

Criterio de cierre:

- Streamlit abre sin excepciones;
- el selector de contrato permite revisar `PW-2024-0001`;
- las pestañas principales cargan datos;
- si Streamlit falla por dependencia local, queda documentado el fallback con artefactos
  JSON/Parquet y capturas.

## Hito 4 - Validacion tecnica de integracion

Objetivo: ejecutar una validacion suficiente para decidir si `integration/multiagent` puede pasar a
la rama principal.

Validacion completa:

```powershell
$env:PYTHONPATH="scr"
python -m procurewatch doctor
python -m pytest tests
python -m ruff check api scr tests frontend
```

Validacion enfocada si el tiempo aprieta:

```powershell
$env:PYTHONPATH="scr"
python -m pytest tests\test_agent1.py tests\test_agent2.py tests\test_agent3.py tests\test_agent4.py tests\test_cli.py
python -m ruff check scr\procurewatch frontend tests\test_agent3.py tests\test_agent4.py
```

Criterio de cierre:

- tests verdes, o fallos documentados con causa y alcance;
- ruff verde, o excepciones justificadas;
- `doctor` no bloquea la demo;
- no hay cambios sin revisar en Git.

## Hito 5 - Documentacion, memoria y defensa

Objetivo: alinear el repositorio y la memoria externa con lo que realmente funciona en la rama de
integracion.

Documentos de referencia:

- `README.md`
- `docs/README.md`
- `docs/04_agentes/SEGUIMIENTO_AGENTES.md`
- `docs/04_agentes/CIERRE_AGENT3_AGENT4_2026_06_23.md`
- `docs/04_agentes/HOJA_RUTA_CIERRE_TFM_2026_06_24.md`
- esta hoja de ruta final

Contenido que debe pasar a la memoria:

- ProcureWatch es un prototipo de priorizacion para revision humana.
- Agent1 normaliza fuentes y produce un canonico.
- Agent2 calcula red flags y scoring determinista.
- Agent3 deriva una red de relaciones y metricas.
- Agent4 recupera evidencia documental y genera ficha citada.
- El dashboard permite explicar el caso integrado.
- Las limitaciones son parte del metodo: matching imperfecto, corpus pequeno, muestra demo reducida
  y ausencia de etiquetas juridicas completas.

Criterio de cierre:

- README y docs apuntan al flujo real;
- la memoria no promete servicios ni funcionalidades no cerradas;
- la defensa tiene un guion de 5 a 7 minutos basado en `PW-2024-0001`;
- las limitaciones aparecen de forma honesta y metodologica.

## Hito 6 - Promocion a rama principal

Objetivo: pasar de integracion a rama principal solo cuando la rama este validada y el equipo tenga
claro que entregar.

Gate antes de promocionar:

- `integration/multiagent` contiene `origin/Satu` y `origin/sebas`;
- `git status --short --branch` esta limpio;
- tests y ruff ejecutados o fallos documentados;
- dashboard probado o fallback documentado;
- hoja de ruta y documentacion actualizadas;
- rama `integration/multiagent` subida al remoto;
- decision explicita sobre si la rama principal sera `master` o `main`.

Comandos de cierre:

```powershell
git status --short --branch
git push origin integration/multiagent
```

Promocion si la rama principal es `master`:

```powershell
git checkout master
git merge --no-ff integration/multiagent
git push origin master
```

Promocion si el equipo decide usar `main`:

```powershell
git checkout -b main integration/multiagent
git push origin main
```

Criterio final:

- existe una rama principal con la integracion final;
- el repositorio, la demo y la documentacion cuentan la misma historia;
- el equipo puede entregar o defender sin depender de cambios pendientes.

## Triage final

### Imprescindible

- Integracion Sebas/Satu confirmada.
- Dashboard explorable.
- Demo Agent3-Agent4 reproducible.
- Validacion tecnica ejecutada.
- Limitaciones escritas.
- Decision de rama principal.

### Importante

- Capturas del dashboard.
- Tabla de resultados por agente.
- Tabla de artefactos generados.
- Lista de comandos reproducibles.
- Texto breve para memoria externa.

### Prescindible

- Nuevas fuentes.
- Nuevas reglas de scoring.
- Servicios Docker obligatorios.
- Ajustes esteticos no criticos.
- Refactors no necesarios.

## Guion de defensa de 5 minutos

1. Problema: la contratacion publica genera datos abiertos, pero cuesta priorizar revision.
2. Propuesta: ProcureWatch integra datos, reglas, grafos y evidencia documental.
3. Agent1: normaliza fuentes y genera el canonico.
4. Agent2: calcula red flags y score explicable.
5. Agent3: transforma contratos en red y calcula relaciones.
6. Agent4: recupera evidencia documental y genera ficha citada.
7. Dashboard: permite explorar resultados y explicar un caso.
8. Limitaciones: matching, corpus pequeno, muestra demo y ausencia de etiquetas de fraude.
9. Futuro: mejorar matching, ampliar corpus, persistir Neo4j/Qdrant y crear API productiva.

## Frase final del proyecto

ProcureWatch Analytics demuestra que es posible construir un MVP reproducible para priorizar
contratos publicos revisables combinando datos abiertos, red flags, grafos y RAG documental, con
trazabilidad suficiente para apoyar supervision humana sin sustituir una auditoria.
