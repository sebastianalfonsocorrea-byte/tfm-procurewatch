# Seguimiento operativo de agentes

Este documento es el seguimiento transversal. Los detalles historicos de Agent1 se mantienen en
`SEGUIMIENTO_AGENT1.md`.

## Estado actual 23/06/2026

| Agente | Estado | Entrada principal | Salida principal | Siguiente paso |
|---|---|---|---|---|
| Agent1 | Operativo | BOE, PLACE, OpenTender raw | `agent2_contracts_canonical.parquet` | Mejorar matching entre fuentes |
| Agent2 | Operativo dentro del MVP del TFM | Canonico Agent1 | `agent2_risk_flags.parquet`, `agent2_risk_scores.parquet` | Consolidar la persistencia en PostgreSQL y preparar Agent3 |
| Agent3 | Planificado | Canonico Agent1/PostgreSQL | nodos, edges y metricas | Crear generador de grafo |
| Agent4 | Scaffold y plan | Contratos y documentos | chunks, retrieval y contexto | PoC RAG con evidencia |

## Reglas comunes

- `data/` guarda datasets y artefactos generados.
- `scr/procurewatch/data_sources/` guarda conectores y parsers de fuentes externas.
- `scr/procurewatch/agentN/` guarda la logica propia de cada agente.
- Ningun agente debe afirmar fraude; todos priorizan revision humana con evidencia trazable.
- El MVP del TFM es el flujo completo de extremo a extremo; los comandos `run-mvp` y
  `run-agent2-mvp` solo son atajos operativos para ejecutar piezas del mismo flujo con menos
  friccion durante el desarrollo.

## Avance Agent2 23/06/2026

- Se amplía el alcance operativo de Agent2 a un conjunto pequeño de red flags explicables:
  - RF-01: adjudicatario ausente;
  - RF-02: procedimiento sensible o de urgencia;
  - RF-03: recurrencia comprador-proveedor;
  - RF-04: concentración de importe en la pareja comprador-proveedor;
  - RF-05: desviación entre importe estimado y adjudicado;
  - RF-06: patrón temporal anómalo entre publicación y adjudicación.
- El score pasa a escalar de 0 a 100 y conserva evidencia por contrato.
- `run-agent2-mvp` lee `data/processed/agent2_contracts_canonical.parquet` y genera las salidas
  analíticas del agente sin pedir parámetros extra.
- El resultado ya permite enseñar un ranking mínimo de casos y no depende todavía de grafos ni
  documentos.
- Ejecución real sobre el canonico Agent1 actual:
  - 17.927 contratos analizados;
  - 17.601 contratos con alguna señal;
  - 31.278 señales activadas en total;
  - reparto por red flag:
    - RF-01: 17.202;
    - RF-02: 198;
    - RF-03: 5.321;
    - RF-04: 568;
    - RF-05: 7.989.
- En el canonico actual RF-06 no se activa, porque no hay suficientes patrones temporales
  anómalos detectables con los datos disponibles; el rule-set sigue implementado para futuros
  lotes o enriquecimientos.

## Avance Agent2 23/06/2026 - persistencia del agente

- `run-agent2` y `run-agent2-mvp` ya aceptan `--postgres-dsn` y `--write-postgres`.
- El agente persiste en PostgreSQL estas tablas de salida:
  - `agent2_risk_flags`
  - `agent2_risk_scores`
  - `agent2_supplier_risk_summary`
  - `agent2_outputs`
- La salida Parquet sigue siendo la referencia principal del pipeline y PostgreSQL queda como
  capa estructurada para trazabilidad y consulta posterior.
- El scoring ya no queda solo por contrato: también se agrega un resumen por adjudicatario para
  acercarse al requisito de score por entidad de la propuesta.
- El Agente 2 añade además una comparativa paralela contra Isolation Forest y una aproximación
  Positive-Unlabeled para contrastar el enfoque de reglas con modelos no supervisados y semi-
  supervisados.
- La validación automatizada usa SQLite en tests para comprobar que el writer funciona sin
  depender de un servidor PostgreSQL levantado.

### Diferencia operativa entre los dos comandos

| Comando | Uso | Configuración | Persistencia |
|---|---|---|---|
| `run-agent2` | Ejecución explícita y configurable | Recibe `--input`, `--output-dir`, `--deviation-threshold`, `--postgres-dsn` y `--write-postgres` | Solo si se activa con `--write-postgres` |
| `run-agent2-mvp` | Ejecución rápida para demo o borrador | Usa por defecto `data/processed/agent2_contracts_canonical.parquet` y `data/processed` | Automática si existe `PROCUREWATCH_POSTGRES_DSN` o se pasa `--postgres-dsn` |

La lógica analítica es la misma en ambos casos; cambia el nivel de comodidad de la interfaz.

## Avance Agent2 21/06/2026

- RF-05 detecta adjudicaciones cuyo importe supera en más de un 10 % el importe estimado.
- El umbral es configurable y queda versionado como decisión operativa inicial.
- Cada activación conserva evidencia, versión de regla y hash del dataset de entrada.
- Los contratos sin ambos importes se marcan como `no_evaluable`; no se interpretan como riesgo
  bajo.
- El score inicial usa escala 0-100: 25 puntos y nivel medio cuando RF-05 se activa.
- Resultado sobre las 4.062 líneas de adjudicación BOE actuales:
  - 557 contratos evaluables por disponer de importe estimado y adjudicado;
  - 3.505 contratos no evaluables por falta de alguno de esos datos;
  - 11 activaciones de RF-05 con el umbral inicial del 10 %.
- La cobertura limitada de importes debe constar como limitación del resultado; las 11 activaciones
  no representan una estimación de fraude ni del riesgo total del universo.

## Bloqueos y cautelas

- El matching actual entre BOE, PLACE y OpenTender tiene intersecciones 0 por `contract_key_canon`.
- Agent2 puede avanzar con señales intrafuente, pero no debe afirmar contraste real entre fuentes.
- Agent3 debe construirse desde el canonico o PostgreSQL, no desde raw.
- Agent4 debe citar `document_id`, `chunk_id` y `contract_key_canon` cuando use evidencia textual.

## Documentos canonicos

- `PLAN_AGENTE1_PIPELINE.md`
- `PLAN_AGENTE2_SCORING.md`
- `PLAN_AGENTE3_GRAFOS.md`
- `PLAN_AGENTE4_RAG_LANGGRAPH.md`
- `PLAN_CAPA_DATOS_AGENTES.md`
