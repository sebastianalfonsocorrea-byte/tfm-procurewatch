# Hoja de ruta final TFM 2026-06-24

Objetivo: cerrar hoy una version defendible de ProcureWatch Analytics para entrega, con codigo,
demo, memoria y relato academico alineados. El criterio no es implementar mas funcionalidad, sino
dejar claro que existe un MVP reproducible, explicable y limitado honestamente.

## Decision de alcance para hoy

ProcureWatch se presenta como prototipo analitico multiagente, no como plataforma productiva.

Debe quedar cerrado:

- pipeline de datos y salida canonica;
- motor de red flags y scoring;
- grafo de relaciones y metricas;
- ficha documental/RAG trazable;
- dashboard local para explicar un caso;
- memoria con resultados, limitaciones y trabajo futuro.

Queda fuera de cierre de hoy:

- despliegue cloud;
- autenticacion y usuarios;
- backend FastAPI productivo;
- matching perfecto entre BOE, PLACE y OpenTender;
- evaluacion RAGAS completa con corpus grande;
- Neo4j/Qdrant/Ollama obligatorios para la demo;
- cualquier afirmacion juridica de fraude.

Docker no bloquea esta hoja de ruta. Si Docker no esta encendido, se trabaja con artefactos locales,
capturas, JSON/Parquet ya generados y comandos documentados.

## Estado de integracion

Rama objetivo: `integration/multiagent`.

Estado esperado:

- rama `Satu` integrada;
- rama `sebas` integrada;
- `main` se mantiene estable hasta decidir promocion;
- la documentacion final apunta a `integration/multiagent` como rama de entrega tecnica.

Criterio de cierre:

- no hay conflictos de Git;
- el equipo sabe que rama entregar o exportar;
- los cambios finales se concentran en documentacion, demo y correcciones menores.

## Orden de trabajo de hoy

### 1. Congelar el relato del TFM

Responsables: ambos.

Tareas:

- Redactar en la memoria que el sistema es una herramienta de priorizacion para revision humana.
- Explicar la arquitectura por capas: Agent1, Agent2, Agent3, Agent4 y dashboard.
- Alinear la memoria con lo implementado, no con el alcance ideal de la propuesta inicial.
- Mover lo no implementado a limitaciones o trabajo futuro.

Criterio de hecho:

- la memoria no promete funcionalidades inexistentes;
- el lector entiende que el MVP es reproducible y trazable;
- queda explicito que no se declara fraude.

### 2. Cerrar resultados tecnicos

Responsables: Sebastian para Agent1/Agent2, Saturia para Agent3/Agent4, ambos para integracion.

Tareas:

- Agent1: documentar fuentes, canonico, cobertura y limitacion de matching.
- Agent2: documentar red flags implementadas, scoring y salida explicable.
- Agent3: documentar nodos, aristas, comunidades, centralidad y features para scoring/RAG.
- Agent4: documentar ficha de caso, evidencias, citas y fallback offline.
- Dashboard: documentar flujo de demo aunque Docker/servicios no esten activos.

Criterio de hecho:

- cada agente tiene entrada, proceso, salida y limitacion descritos;
- existen nombres concretos de artefactos generados;
- hay un caso demo que se puede explicar de principio a fin.

### 3. Preparar la demo defendible

Responsables: ambos.

Ruta base de demo:

```text
data/processed/agent3_agent4_demo_2026_06_23/
```

Artefactos clave:

- `agent2_contracts_canonical_demo.parquet`
- `agent3_graph_report.json`
- `agent3_nodes.parquet`
- `agent3_edges.parquet`
- `agent3_agent2_features.parquet`
- `agent4_case_context_integrated_demo.json`

Caso principal:

```text
PW-2024-0001
```

Guion minimo:

1. Agent1/Agent2 entregan contrato canonico y score.
2. Agent3 convierte contratos en grafo y calcula relaciones.
3. Agent4 recupera evidencia documental y genera ficha citada.
4. Dashboard muestra KPIs, red, caso y evidencias.
5. Se explica que el resultado prioriza revision humana.

Criterio de hecho:

- si Streamlit funciona, se abre la demo local;
- si Streamlit no funciona, se muestran capturas o JSON/Parquet y se explica el flujo;
- no se depende de servicios Docker para defender el concepto.

### 4. Cerrar memoria escrita

Responsables: ambos.

Prioridad alta:

- Capitulo de desarrollo: arquitectura, pipeline, agentes y dashboard.
- Capitulo de evaluacion/resultados: calidad de datos, red flags, grafo, RAG y demo.
- Limitaciones: datos, matching, corpus documental, ausencia de etiquetas de fraude.
- Trabajo futuro: FastAPI, despliegue, RAGAS completo, Neo4j/Qdrant persistentes, mejora de matching.
- Conclusiones: aportacion academica y tecnica.

Prioridad media:

- revisar figuras y tablas;
- normalizar nombres de agentes y artefactos;
- revisar que referencias y fuentes esten citadas;
- completar anexos de comandos.

Criterio de hecho:

- la memoria tiene una linea argumental completa;
- todas las decisiones tecnicas importantes estan justificadas;
- las limitaciones aparecen como parte del metodo, no como disculpas.

### 5. Preparar entrega y defensa

Responsables: ambos.

Entregables:

- repositorio en rama de integracion o rama final acordada;
- memoria actualizada;
- guia de demo;
- hoja de ruta final;
- capturas o evidencias de salida;
- lista de comandos reproducibles;
- presentacion breve si aplica.

Checklist antes de entregar:

- README principal indica como ejecutar o entender el MVP.
- `docs/README.md` permite navegar la documentacion.
- La memoria y el repositorio usan los mismos nombres de agentes.
- Los artefactos demo estan descritos aunque `data/processed/` no se versiona completo.
- Se decide si hacer push de `integration/multiagent`.
- Se decide si fusionar a `main` o dejar `main` estable.

## Triage de tareas

### Imprescindible

- Hoja de ruta final creada y enlazada.
- Memoria alineada con MVP real.
- Guion de demo cerrado.
- Limitaciones escritas.
- Rama de integracion clara.

### Importante

- Capturas del dashboard o de salidas JSON.
- Tabla de resultados por agente.
- Tabla de red flags implementadas.
- Tabla de artefactos generados.
- Checklist de comandos reproducibles.

### Prescindible hoy

- Nuevas fuentes de datos.
- Nuevas reglas de scoring.
- Mas integraciones con servicios.
- Ajustes esteticos no criticos.
- Refactors no necesarios.

## Tabla de cierre

| Bloque | Responsable | Estado objetivo hoy | Evidencia |
|---|---|---|---|
| Git e integracion | Ambos | Rama integrada sin conflictos | `integration/multiagent` |
| Agent1 | Sebastian | Canonico y calidad documentados | `agent2_contracts_canonical.parquet` |
| Agent2 | Sebastian | Scoring v1 explicado | salidas Agent2 / docs |
| Agent3 | Saturia | Grafo y metricas explicadas | `agent3_graph_report.json` |
| Agent4 | Saturia | Ficha documental citada | `agent4_case_context_integrated_demo.json` |
| Dashboard | Ambos | Demo local o guion alternativo | `frontend/agent3_demo.py` |
| Memoria | Ambos | Resultados y limitaciones cerrados | documento TFM |
| Defensa | Ambos | Guion de 5-7 minutos | presentacion/capturas |

## Guion de defensa de 5 minutos

1. Problema: la contratacion publica genera datos abiertos, pero cuesta priorizar revision.
2. Propuesta: ProcureWatch integra datos, reglas, grafos y evidencia documental.
3. Agent1: normaliza fuentes y genera el canonico.
4. Agent2: calcula red flags y score explicable.
5. Agent3: anade relaciones, comunidades y centralidad.
6. Agent4: recupera evidencia documental y genera ficha citada.
7. Dashboard: permite revisar un caso sin afirmar fraude.
8. Limitaciones: matching, corpus pequeno, sin etiquetas completas.
9. Futuro: mejorar matching, ampliar corpus, persistencia Neo4j/Qdrant y API productiva.

## Frase final del proyecto

ProcureWatch Analytics demuestra que es posible construir un MVP reproducible para priorizar
contratos publicos revisables combinando datos abiertos, red flags, grafos y RAG documental, con
trazabilidad suficiente para apoyar supervision humana sin sustituir una auditoria.
