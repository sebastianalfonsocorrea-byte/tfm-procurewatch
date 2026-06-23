# Plan de Agent2: red flags y scoring

Objetivo: plantear Agent2 como motor determinista y explicable de red flags, usando el dataset
canonico producido por Agent1 y preparando su posterior uso con PostgreSQL y Neo4j.

## Estado de partida

Entrada actual:

- `data/processed/agent2_contracts_canonical.parquet`
- `data/processed/agent2_contracts_canonical_schema.json`
- `data/processed/agent1_data_quality_summary.json`

Codigo base:

- `scr/procurewatch/agent2/schemas.py`
- `scr/procurewatch/agent2/rules.py`
- `scr/procurewatch/agent2/scoring.py`
- `scr/procurewatch/agent2/state.py`

Regla de estructura: `data/` guarda datasets y artefactos; `scr/procurewatch/data_sources/`
guarda conectores/parsers externos; `scr/procurewatch/agent2/` guarda la logica de scoring.

El dataset canonico tiene 51.720 filas y estado de calidad `ok`. La ausencia actual de
intersecciones entre BOE/PLACE/OpenTender por `contract_key_canon` no bloquea Agent2, pero limita
las afirmaciones de contraste entre fuentes.

## Casos no evaluables y limitaciones operativas

Agent2 no fuerza un score cuando faltan los campos que necesita cada regla o cada comparativa.
En ese caso la fila queda registrada como `no_evaluable` o con `confidence` reducido, según el
tipo de salida.

Casos típicos:

- importes faltantes o no válidos para RF-05 y para el score agregado por adjudicatario;
- ausencia de adjudicatario identificable para métricas de recurrencia o concentración;
- falta de suficiente variación o de variables útiles para la comparativa con Isolation Forest;
- ausencia de etiquetas fiables para una formulación estricta de Positive-Unlabeled Learning;
- falta de intersección entre fuentes para afirmar contraste real BOE/PLACE/OpenTender.

Regla práctica: si el dato no permite una evidencia trazable, el agente debe dejar constancia de la
limitación en lugar de inventar una señal, un emparejamiento o un score.

## Alcance v1

Agent2 queda planteado como motor incremental; no se considera cerrado hasta implementar red flags
v1 y salidas versionadas.

Entregables minimos:

- Catalogo v1 de red flags.
- Esquema de entrada/salida.
- Decision de columnas obligatorias.
- Plan de carga a PostgreSQL.
- Plan de derivacion a Neo4j para relaciones.
- Resumen agregado por adjudicatario para compatibilizar el score por contrato con el score
  por entidad que pide la propuesta.
- Comparativa del agente contra Isolation Forest y Positive-Unlabeled Learning.

## Red flags v1

Prioridad inicial:

- RF-01: concurrencia baja o adjudicatario unico cuando exista dato.
- RF-02: procedimiento restringido, negociado o menor recurrente.
- RF-03: recurrencia comprador-proveedor.
- RF-04: concentracion de importe por proveedor y comprador.
- RF-05: desviacion entre importe estimado y adjudicado.
- RF-06: patrones temporales anomalos.
- RF-07: repeticion de CPV, titulos o importes entre contratos cercanos.

### Ejecución operativa actual

Para el borrador del TFM, el agente deja operativas estas señales deterministas:

- RF-01: adjudicatario ausente.
- RF-02: procedimiento sensible o de urgencia.
- RF-03: recurrencia comprador-proveedor en el canonico.
- RF-04: concentracion de importe en la pareja comprador-proveedor.
- RF-05: desviacion entre importe estimado y adjudicado.
- RF-06: patron temporal anomalo entre publicacion y adjudicacion.

### Primera implementación: RF-05

La primera regla ejecutable compara `awarded_value_eur` con `estimated_value_eur`:

- solo se evalúa cuando ambos importes están disponibles y el estimado es mayor que cero;
- se activa cuando la desviación positiva supera el 10 %;
- el umbral es una decisión operativa inicial, configurable y pendiente de análisis de
  sensibilidad; no se presenta como un umbral normativo ni como prueba de fraude;
- una fila sin los importes necesarios queda como `no_evaluable`, no recibe artificialmente un
  score cero.

Ejecución:

```bash
procurewatch run-agent2
```

Cada red flag debe producir:

- `risk_flag_id`
- `contract_key_canon`
- `flag_code`
- `severity`
- `confidence`
- `evidence_fields`
- `evidence_text`
- `rule_version`
- `created_at`

## Scoring

El score no declara fraude. Prioriza revision humana.

Salidas minimas:

- `contract_key_canon`
- `risk_score`
- `risk_level`
- `flags_count`
- `top_flags`
- `score_version`
- `source_snapshot_id`

Salida agregada adicional del agente:

- `supplier_key`
- `supplier_name`
- `total_contracts`
- `total_importe_adjudicado`
- `activated_contract_ratio`
- `score_riesgo_agregado`
- `risk_level`
- `red_flags_recurrentes`

La agregación por adjudicatario combina tres señales:

- la media del score por contrato;
- el máximo score observado;
- la proporción de contratos activados dentro del total del adjudicatario.

Fórmula operativa:

`score_riesgo_agregado = 0.5 * mean_risk_score + 0.3 * max_risk_score + 0.2 * activated_contract_ratio * 100`

La idea es evitar que un único expediente extremo distorsione todo el perfil, pero sin perder el
peso de picos puntuales ni la recurrencia de activaciones.

## Validación de estabilidad

Agent2 incluye una comprobación sencilla sobre una muestra fija ordenada por `contract_key_canon`.
La muestra se vuelve a evaluar tras barajar las filas y se verifica que el score y la comparativa
se mantienen iguales.

La validación registra:

- tamaño de la muestra;
- número de filas evaluadas;
- coincidencia exacta de scores;
- coincidencia exacta de la comparativa;
- máxima diferencia observada en `risk_score`;
- número de contratos no coincidentes, si los hubiera.

Se usa como control de regresión y como evidencia de que el pipeline no depende del orden de
entrada de los datos.

Salida comparativa del agente:

- `iforest_anomaly_score`
- `iforest_anomaly_flag`
- `pu_probability`
- `pu_label`
- `agreement_iforest_rule`
- `agreement_pu_rule`

La comparativa no se interpreta como validación definitiva del modelo, sino como contraste
exploratorio con las limitaciones del canonico y de las etiquetas disponibles.
La aproximación PU debe leerse como una versión práctica y acotada para el TFM, no como una
implementación formal completa si no existen positivas y no etiquetadas suficientemente limpias.
La comparativa se construye sobre covariables del contrato y señales de completitud, no sobre el
propio `risk_score`, para evitar fuga de información desde las reglas hacia el modelo.

## Evaluación formal de la comparativa

Cuando no hay etiquetas de fraude verdaderas, la evaluación del contraste se hace contra
`rule_positive` como referencia proxy. Eso permite medir precisión, recall, F1, exactitud,
balanced accuracy y AUC de manera reproducible, pero no sustituye una validación supervisada real.

La salida de evaluación incluye, para Isolation Forest y para PU learning:

- soporte total;
- positivos de referencia;
- positivos predichos;
- TP, FP, TN y FN;
- accuracy;
- balanced accuracy;
- precision;
- recall;
- F1;
- ROC AUC cuando es calculable.

En la memoria conviene presentar esta evaluación como contraste técnico, no como estimación
definitiva de rendimiento frente a fraude real.

## Uso de PostgreSQL

Tablas destino:

- `risk_flags`
- `risk_scores`
- `agent2_supplier_risk_summary`
- `agent2_model_comparison`
- `agent_outputs`

Mientras PostgreSQL no este cargado, Agent2 puede leer Parquet, pero la salida debe disenar ya
con el esquema relacional final.

## Uso de Neo4j

Neo4j entra cuando haya que calcular patrones relacionales:

- compradores con adjudicatarios recurrentes;
- proveedores conectados por contratos/lotes;
- comunidades de entidades;
- centralidad o concentracion.

## Criterios de aceptacion

- Agent2 puede ejecutarse sobre el canonico sin depender de documentos.
- Cada flag es trazable a columnas o evidencias concretas.
- El score incluye version de regla y no borra historico.
- Las limitaciones de datos faltantes quedan registradas como `confidence` menor, `no_evaluable`
  o flag no aplicable.
- No se fuerza comparación entre fuentes, modelos o etiquetas cuando la evidencia de entrada no
  alcanza para sostenerla.
