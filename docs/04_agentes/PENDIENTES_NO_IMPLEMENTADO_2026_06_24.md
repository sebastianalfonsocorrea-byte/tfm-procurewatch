# Pendientes, no implementado y no terminado - 2026-06-24

Este documento recoge las piezas cerradas, parciales o fuera del alcance real del MVP actual de
ProcureWatch tras los hitos 1-7 del 24/06/2026. La referencia principal es el estado documentado en
las hojas de ruta, seguimiento de cierre, tests y artefactos regenerables.

## Resumen ejecutivo

- ProcureWatch queda defendible como prototipo analitico multiagente, no como plataforma productiva.
- Agent1, Agent2, Agent3 y Agent4 tienen una ruta MVP demostrable con demo offline reproducible.
- La limitacion tecnica principal sigue siendo el matching entre BOE, PLACE y OpenTender: las
  intersecciones actuales por `contract_key_canon` son 0.
- El sistema prioriza revision humana con evidencia trazable; no declara fraude ni sustituye una
  auditoria.

## Datos, ingesta y calidad

| Tema | Estado | Que falta o queda limitado |
|---|---|---|
| Matching BOE/PLACE/OpenTender | Pendiente | Mejorar `contract_key_canon` y la estrategia de enlace para reducir falsos no-match. |
| Intersecciones entre fuentes | Incompleto | Actualmente no hay intersecciones fiables entre BOE, PLACE y OpenTender por clave canonica. |
| `source_snapshot_id` | Implementado en canonico Agent1 | Propagarlo de forma sistematica a historico PostgreSQL y a analisis longitudinales futuros. |
| datos.gob.es | Futuro | Integrar como capa de enriquecimiento sistematica, no como parte minima de `run-agent1`. |
| Batch semanal/mensual | Parcial implementado | Hay health/manifest y bloqueo controlado por inputs faltantes; falta scheduling productivo recurrente. |
| Etiquetas juridicas de fraude | No implementado | No existe un set completo validado juridicamente para entrenar/evaluar fraude. |
| Persistencia historica | Futuro | Mover historico y snapshots a PostgreSQL en lugar de depender solo de Parquet locales. |

## Agent1 - ingesta y canonico

| Tema | Estado | Que falta o queda limitado |
|---|---|---|
| Cierre funcional base | Implementado | Mantener validaciones de no deriva cuando cambien contratos canonicos. |
| `source_snapshot_id` | Implementado | Mantenerlo estable y usarlo como base para historicos posteriores. |
| Diagnosticos de matching | Implementado | Usarlos para explicar cobertura y falsos no-match entre fuentes. |
| Calidad de campos aguas abajo | Parcial | Algunos campos dependientes de Agent2, Agent3 o Agent4 siguen nulos hasta que esas capas los completen. |
| PLACE/OpenTender/BOE como contraste cruzado | Incompleto | El flujo integra fuentes, pero el contraste real entre fuentes queda limitado por el matching. |
| PostgreSQL canonico | Parcial/futuro | La persistencia minima existe para MVP, pero la capa canonica productiva queda pendiente. |

## Agent2 - red flags y scoring

| Tema | Estado | Que falta o queda limitado |
|---|---|---|
| RF-01..RF-06 | Implementado | Mantener reglas deterministas y explicables. |
| RF-07..RF-15 | Futuro | Definir, implementar, probar y documentar reglas adicionales. |
| Features Agent3 | Implementado en MVP | Agent2 puede consumir features relacionales opcionales para RF-03/RF-04; faltan reglas avanzadas y calibracion. |
| Historico por snapshot | Futuro | Persistir scores por `source_snapshot_id` en PostgreSQL. |
| Contraste entre fuentes | Limitado | No afirmar senales de contradiccion interfuente mientras el matching siga incompleto. |
| Calibracion con etiquetas reales | No implementado | No hay etiquetas suficientes para calibracion estadistica o validacion juridica de riesgo. |

## Agent3 - grafos y relaciones

| Tema | Estado | Que falta o queda limitado |
|---|---|---|
| Grafo local NetworkX | MVP implementado | Mantenerlo como capa derivada reproducible desde canonico o PostgreSQL. |
| Features para Agent2/Agent4 | Implementado | Mantener compatibilidad de esquema y tolerancia a ausencia de features. |
| Demo integrada | Implementada | `run-integrated-demo` regenera el caso `PW-2024-0001` sin raw completos ni servicios externos. |
| Neo4j | Opcional/futuro | Cerrar carga operativa y consultas recurrentes en una instancia Neo4j estable. |
| Leiden | Futuro | Louvain/NetworkX cubre el MVP; Leiden queda como mejora si aporta valor metodologico. |
| Dashboard productivo | Futuro | Existe demo local validada; faltan backend, usuarios, despliegue y operativa productiva. |
| Identificadores incompletos | Limitacion | Mejorar normalizacion de compradores, adjudicatarios y expedientes antes de analisis avanzado. |

## Agent4 - RAG documental

| Tema | Estado | Que falta o queda limitado |
|---|---|---|
| PoC RAG trazable | Implementado | Mantener citas con `document_id`, `chunk_id` y `contract_key_canon`. |
| `agent4_scope` y frontera | Implementado | Seguir declarando que es apoyo documental para revision humana, no veredicto de fraude. |
| Source registry | Implementado | Mantener politicas de fuente y trazabilidad de BOE/PLACSP/datos abiertos. |
| Fetch BOE-B HTML puntual | Implementado limitado | Permite traer anuncios concretos; no equivale a crawler ni navegacion web. |
| Corpus documental | Parcial | Ampliar corpus real o semi-real para evaluacion y demostracion mas robusta. |
| PDF con Docling | Futuro | Incorporar parsing documental avanzado para PDFs cuando se cierre dependencia. |
| Qdrant/Ollama | Opcional | Disponibles para demo con servicios, pero no obligatorios en tests ni demo minima. |
| BGE-M3 | Futuro metodologico | Usarlo de forma estable via Ollama/Qdrant cuando el entorno lo permita. |
| RAGAS | No ejecutado | Queda futuro porque el corpus actual es pequeno y sintetico. |
| Generacion LLM productiva | Parcial | El fallback determinista cubre tests/offline; falta robustecer ejecucion con modelos locales. |
| PLACSP pliegos | No implementado | No hay descarga automatica ni scraping de pliegos, anexos o resoluciones desde la web operativa. |
| spaCy juridico | No implementado | No hay pipeline cerrado de extraccion de entidades juridicas complejas. |

## Plataforma, producto y demo

| Tema | Estado | Que falta o queda limitado |
|---|---|---|
| Demo integrada Agent2-Agent3-Agent4 | Implementada | Es sintetica/offline y regenerable; no usa raw completos ni servicios externos obligatorios. |
| Dashboard Streamlit | MVP local validado | `validate-dashboard-demo` valida artefactos y render headless; faltan capturas finales y validacion externa. |
| Frontend Next.js | Futuro | Se planteara como diseno posterior, no forma parte del cierre Streamlit del Hito 7. |
| FastAPI productivo | No implementado | Backend de API queda fuera del MVP actual. |
| Autenticacion y usuarios | No implementado | No hay gestion de usuarios, roles ni sesiones. |
| Despliegue cloud | No implementado | No existe infraestructura cloud ni pipeline de despliegue. |
| Docker como requisito de demo | Fuera de alcance MVP | PostgreSQL, Neo4j, Qdrant y Ollama quedan opcionales, no bloqueantes. |
| Monitorizacion productiva | No implementado | No hay observabilidad, alertas ni jobs programados productivos. |

## Memoria y comunicacion

- La memoria debe describir el MVP real y no prometer plataforma productiva.
- El lenguaje correcto es priorizacion de revision humana, no deteccion concluyente de fraude.
- Las limitaciones principales a declarar son matching imperfecto, corpus documental pequeno,
  muestra demo reducida, falta de etiquetas juridicas completas y servicios externos opcionales.
- El caso demo principal documentado es `PW-2024-0001`.
- La demo oficial actual es sintetica, offline y regenerable mediante `run-integrated-demo`.
- El dashboard validado es Streamlit local; Next.js queda para diseno futuro.

## Referencias internas

- `docs/00_vision/HOJA_RUTA_FINAL_TFM_2026_06_24.md`
- `docs/04_agentes/HOJA_RUTA_CIERRE_TFM_2026_06_24.md`
- `docs/04_agentes/HOJA_RUTA_TRABAJO_TARDE_TFM_2026_06_24.md`
- `docs/04_agentes/SEGUIMIENTO_AGENTES.md`
- `docs/04_agentes/CIERRE_AGENT3_AGENT4_2026_06_23.md`
- `docs/04_agentes/HOJA_RUTA_SEBAS_CIERRE_TFM.md`
- `docs/03_agent1_ingesta/SEGUIMIENTO_AGENT1.md`
