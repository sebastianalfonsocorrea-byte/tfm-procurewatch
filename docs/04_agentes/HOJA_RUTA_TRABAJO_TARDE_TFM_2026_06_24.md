# Hoja de ruta de trabajo tarde TFM - 2026-06-24

Objetivo: cerrar, en orden y sin sobredimensionar el alcance, las piezas implementables que quedan
pendientes en `integration/multiagent` para que ProcureWatch sea defendible como MVP tecnico del
TFM. Esta hoja usa como entrada `PENDIENTES_NO_IMPLEMENTADO_2026_06_24.md` y la inspeccion real del
repositorio.

Regla de trabajo: cada hito debe terminar con codigo/documentacion trazable, comandos de validacion
y una decision clara: cerrado, queda limitado, o pasa a trabajo futuro. No se debe prometer una
plataforma productiva si el repositorio solo entrega un prototipo local.

## Prioridad de esta tarde

1. Cerrar lo que mejora la coherencia del MVP sin cambiar el alcance academico.
2. Evitar abrir trabajos grandes que no caben hoy: auth, cloud, FastAPI productivo, TED completo,
   RAGAS completo, etiquetas juridicas de fraude, matching perfecto.
3. Producir evidencia reproducible: artefactos JSON/Parquet, tests, ruff y dashboard.
4. Dejar lo no implementado registrado como limitacion o trabajo futuro.

## Hito 0 - Preparacion y linea base

Objetivo: asegurar que se trabaja sobre la rama y commit correctos, sin pisar cambios locales.

Trabajo:

- Confirmar rama `integration/multiagent`.
- Revisar `git status` y separar cambios del usuario de los cambios nuevos.
- Confirmar datos disponibles: raw PLACE, ausencia/presencia de BOE y OpenTender completos,
  `processed_sample` y corpus Agent4.
- Ejecutar solo checks de inspeccion ligeros al inicio.

Artefactos esperados:

- Nota breve de estado inicial en la conversacion.
- Lista de archivos que se van a tocar en el hito siguiente.

Validacion:

```bash
git status -sb --untracked-files=all
python -m procurewatch.cli doctor
```

Mensaje para continuar: "Hito 0 listo, pasamos a Agent1".

## Hito 1 - Agent1: canonico, `source_snapshot_id` y datos disponibles

Objetivo: cerrar la trazabilidad minima del canonico sin exigir matching perfecto.

Trabajo:

- Revisar si `source_snapshot_id` ya existe en alguna capa y, si no existe, incorporarlo al
  canonico Agent1 de forma determinista.
- Propagar `source_snapshot_id` a outputs que consumen Agent2 y Agent3 cuando aplique.
- Ajustar previews/esquemas/reportes para que el nuevo campo quede documentado.
- Mantener compatibilidad con `data/processed_sample`.
- No forzar una ejecucion completa si faltan raw BOE/OpenTender completos; usar muestras para
  validacion rapida.

Archivos probables:

- `scr/procurewatch/agent1/pipeline.py`
- `scr/procurewatch/agent1/analytical_dataset.py`
- `scr/procurewatch/agent1/coverage_report.py`
- `tests/test_agent1.py`
- `tests/test_agent1_analytical_dataset.py`

Artefactos esperados:

- Canonico con `source_snapshot_id`.
- Schema/preview actualizado.
- Reporte que indique claramente fuente y snapshot.

Validacion:

```bash
python -m pytest tests/test_agent1.py tests/test_agent1_analytical_dataset.py tests/test_agent1_coverage_report.py
python -m ruff check scr/procurewatch/agent1 tests/test_agent1.py tests/test_agent1_analytical_dataset.py
```

Decision de cierre:

- Cerrado si el campo existe, es estable y no rompe consumidores.
- Limitacion si no hay raw completo para recalcular resultados finales.

Mensaje para continuar: "Hito 1 listo, pasamos a matching".

## Hito 2 - Matching BOE/PLACE/OpenTender: mejora defendible, no promesa de perfeccion

Objetivo: mejorar la explicabilidad del enlace entre fuentes y registrar por que las
intersecciones actuales son bajas o nulas.

Trabajo:

- Revisar la generacion de `contract_key_canon`.
- Anadir, si es viable en tiempo, un reporte de candidatos de matching o diagnostico de no-match.
- Separar tres niveles: clave exacta, clave normalizada relajada y candidatos para revision humana.
- No inventar intersecciones ni forzar matches dudosos.

Archivos probables:

- `scr/procurewatch/agent1/pipeline.py`
- `scr/procurewatch/agent1/coverage_report.py`
- `tests/test_agent1.py`

Artefactos esperados:

- Reporte JSON/Markdown con universo por fuente, intersecciones exactas y diagnostico.
- Texto claro: el matching imperfecto sigue siendo limitacion si no hay evidencia de mejora real.

Validacion:

```bash
python -m pytest tests/test_agent1.py tests/test_agent1_coverage_report.py
```

Decision de cierre:

- Cerrado si se mejora la trazabilidad del matching.
- Pasa a limitacion si no aparecen intersecciones fiables.

Mensaje para continuar: "Hito 2 listo, pasamos a Agent2".

## Hito 3 - Agent2: integrar features Agent3 en scoring estable

Objetivo: que Agent2 pueda consumir features relacionales de Agent3 sin romper su ejecucion local.

Trabajo:

- Revisar `run-agent2` y `run-agent2-mvp`.
- Definir entrada opcional `agent3_agent2_features.parquet`.
- Incorporar features relacionales al scoring solo si existen y son trazables por
  `contract_key_canon`.
- Mantener fallback: si no hay features Agent3, Agent2 debe seguir funcionando con warning/reporte.
- Documentar que el score es una priorizacion determinista para revision humana.

Archivos probables:

- `scr/procurewatch/agent2/pipeline.py`
- `scr/procurewatch/agent2/mvp_pipeline.py`
- `scr/procurewatch/agent2/scoring.py`
- `scr/procurewatch/agent2/mvp_scoring.py`
- `tests/test_agent2.py`

Artefactos esperados:

- Scores con metadatos de uso de features Agent3.
- Reporte que indique si Agent3 fue usado o no.

Validacion:

```bash
python -m pytest tests/test_agent2.py tests/test_agent3.py
python -m ruff check scr/procurewatch/agent2 scr/procurewatch/agent3 tests/test_agent2.py tests/test_agent3.py
```

Decision de cierre:

- Cerrado si Agent2 funciona con y sin features Agent3.
- Futuro si se requiere calibracion con etiquetas reales.

Mensaje para continuar: "Hito 3 listo, pasamos a batch".

## Hito 4 - Batch: controles de salud, manifiesto y reconstruccion derivada

Objetivo: endurecer el flujo recurrente sin convertirlo en plataforma productiva.

Trabajo:

- Revisar `run-batch`.
- Asegurar validaciones de presencia de raw antes de ejecutar.
- Generar manifiesto de ejecucion con rutas, snapshots, fecha, modo semanal/mensual y estado.
- Si `monthly`, dejar preparado el refresco de derivados cuando existan outputs base.
- Evitar que el batch prometa descarga completa automatica de BOE/OpenTender si no esta cerrada.

Archivos probables:

- `scr/procurewatch/batch.py`
- `scr/procurewatch/cli.py`
- `tests/test_batch.py`

Artefactos esperados:

- Manifest JSON de batch.
- Mensajes claros cuando falten raw BOE/OpenTender.

Validacion:

```bash
python -m pytest tests/test_batch.py tests/test_cli.py
python -m ruff check scr/procurewatch/batch.py scr/procurewatch/cli.py tests/test_batch.py tests/test_cli.py
```

Decision de cierre:

- Cerrado si el batch es honesto, reproducible y falla temprano con datos ausentes.
- Futuro si se pide orquestacion productiva, scheduler o cloud.

Mensaje para continuar: "Hito 4 listo, pasamos a Agent4".

## Hito 5 - Agent4: ampliar corpus demostrable y reforzar evaluacion local

Objetivo: mejorar la demo documental sin depender de RAGAS completo ni servicios externos.

Trabajo:

- Revisar corpus actual de `data/synthetic/agent4_corpus`.
- Anadir documentos reales o semi-reales pequenos, trazables y versionables si existen.
- Garantizar que cada evidencia cite `document_id`, `chunk_id` y `contract_key_canon`.
- Reejecutar manifest, indexacion offline y evaluacion local.
- Mantener Qdrant/Ollama como opcionales.

Archivos probables:

- `data/synthetic/agent4_corpus/*`
- `scr/procurewatch/agent4/*`
- `tests/test_agent4.py`

Artefactos esperados:

- `agent4_documents_manifest.json`
- `agent4_case_context_*.json`
- `agent4_evaluation_report.json`

Validacion:

```bash
python -m pytest tests/test_agent4.py
python -m ruff check scr/procurewatch/agent4 tests/test_agent4.py
```

Decision de cierre:

- Cerrado si la ficha demo recupera evidencia trazable y la evaluacion local queda registrada.
- Futuro si se requiere corpus masivo, PDFs complejos, Docling, BGE-M3 estable o RAGAS completo.

Mensaje para continuar: "Hito 5 listo, pasamos a demo integrada".

## Hito 6 - Demo integrada Agent2-Agent3-Agent4

Objetivo: regenerar una demo defendible de punta a punta con artefactos consistentes.

Trabajo:

- Elegir un directorio oficial de demo.
- Ejecutar Agent3 sobre canonico demo.
- Ejecutar Agent4 sobre `PW-2024-0001` o el contrato demo acordado.
- Confirmar que la ficha combina contrato, score Agent2, metricas Agent3 y evidencias Agent4.
- Evitar depender de raw completos si el hito se plantea como demo integrada sintetica.

Comandos base:

```bash
python -m procurewatch.cli run-agent3 --input data/processed/agent3_agent4_demo_2026_06_23/agent2_contracts_canonical_demo.parquet --output-dir data/processed/agent3_agent4_demo_2026_06_23
python -m procurewatch.cli agent4-case-context --contract-key PW-2024-0001 --output-dir data/processed/agent3_agent4_demo_2026_06_23
```

Artefactos esperados:

- `agent3_graph_report.json`
- `agent3_nodes.parquet`
- `agent3_edges.parquet`
- `agent3_agent2_features.parquet`
- `agent4_case_context_integrated_demo.json`

Validacion:

```bash
python -m pytest tests/test_agent2.py tests/test_agent3.py tests/test_agent4.py
```

Decision de cierre:

- Cerrado si el caso demo explica el flujo completo.
- Limitacion si solo se valida con muestra sintetica.

Mensaje para continuar: "Hito 6 listo, pasamos a dashboard".

## Hito 7 - Dashboard Streamlit actual: validacion y capturas

Objetivo: dejar el dashboard Python existente como demo local estable para defensa.

Trabajo:

- Validar `frontend/agent3_demo.py` contra el directorio oficial de demo.
- Comprobar que no falten artefactos.
- Revisar texto visible para no prometer fraude ni plataforma productiva.
- Preparar capturas o al menos comandos reproducibles para la memoria/defensa.

Comandos base:

```bash
streamlit run frontend/agent3_demo.py
```

Validacion:

```bash
python -m ruff check frontend scr tests
```

Decision de cierre:

- Cerrado si el dashboard carga KPIs, caso, grafo, score y evidencias.
- Futuro si se pide UX productiva, backend API o despliegue.

Mensaje para continuar: "Hito 7 listo, pasamos a documentacion".

## Hito 8 - Documentacion tecnica de cierre

Objetivo: alinear documentos con lo realmente implementado despues de los hitos anteriores.

Trabajo:

- Actualizar seguimiento solo con resultados verificados.
- Marcar como cerrado lo implementado esta tarde.
- Mantener como limitacion lo que no se pueda cerrar.
- No escribir todavia la memoria final si no se solicita expresamente.

Archivos probables:

- `docs/04_agentes/SEGUIMIENTO_AGENTES.md`
- `docs/04_agentes/PENDIENTES_NO_IMPLEMENTADO_2026_06_24.md`
- `docs/04_agentes/CIERRE_AGENT3_AGENT4_2026_06_23.md`, solo si la demo cambia.

Validacion:

```bash
rg -n "fraude|productivo|FastAPI|cloud|RAGAS|perfecto|futuro|limitacion" docs
```

Decision de cierre:

- Cerrado si docs y codigo cuentan la misma historia.

Mensaje para continuar: "Hito 8 listo, pasamos a validacion final".

## Hito 9 - Validacion final de rama

Objetivo: dejar una evidencia tecnica compacta antes de escribir memoria o preparar entrega.

Trabajo:

- Ejecutar suite razonable segun tiempo disponible.
- Ejecutar ruff.
- Registrar comandos y resultado.
- Separar fallos reales de problemas de entorno.

Comandos:

```bash
python -m procurewatch.cli doctor
python -m pytest tests
python -m ruff check api scr tests frontend
git status -sb --untracked-files=all
```

Decision de cierre:

- Cerrado si tests/ruff pasan o si queda una limitacion de entorno claramente documentada.

Mensaje para continuar: "Hito 9 listo, planteamos Next.js".

## Hito 10 - Plantear diseno del frontend con Next.js

Objetivo: disenar, no implementar todavia, una evolucion del dashboard hacia un frontend moderno
sin mezclarla con el cierre del MVP Streamlit.

Alcance propuesto:

- Next.js como frontend exploratorio/productizable.
- API futura separada: FastAPI o endpoints de lectura sobre artefactos JSON/Parquet convertidos.
- Mantener Streamlit como demo TFM ya defendible.
- No bloquear el TFM por migrar frontend.

Pantallas iniciales:

- Vista `Overview`: KPIs, fuentes, cobertura, estado de calidad y limitaciones.
- Vista `Risk Cases`: ranking de contratos con score Agent2 y filtros por fuente, CPV, organismo,
  procedimiento y nivel de riesgo.
- Vista `Case Detail`: contrato, red flags, metricas Agent3, evidencias Agent4 y trazabilidad.
- Vista `Network`: grafo comprador-proveedor-contrato con comunidades y centralidad.
- Vista `Data Quality`: nulos, errores de parseo, snapshots, matching y coverage.
- Vista `Methodology`: explicacion breve de que el sistema prioriza revision humana.

Componentes:

- `RiskScoreBadge`
- `RedFlagList`
- `EvidencePanel`
- `NetworkGraph`
- `SourceCoverageTable`
- `CaseTimeline`
- `QualityWarnings`
- `TraceabilityDrawer`

Contrato de datos inicial:

- `GET /api/demo/summary`
- `GET /api/contracts`
- `GET /api/contracts/{contract_key_canon}`
- `GET /api/contracts/{contract_key_canon}/evidence`
- `GET /api/network`
- `GET /api/data-quality`

Decision de cierre:

- Crear solo documento de diseno si el MVP tecnico ya esta validado.
- Implementar Next.js despues, como mejora de presentacion/producto, no como requisito para cerrar
  la memoria.
