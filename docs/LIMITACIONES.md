# Limitaciones del prototipo

ProcureWatch es un prototipo para **priorizar revisión humana** de contratos públicos. No declara
fraude ni sustituye una auditoría. Este documento recoge, con cifras verificables en el
repositorio, qué no está validado todavía y cómo debe leerse cada resultado.

## 1. Sin verdad de referencia (ground truth)

- No existe un conjunto etiquetado de contratos irregulares con el que medir precisión o recall
  del scoring. Ninguna métrica de Agent2 es de acierto: son métricas de cobertura, evaluabilidad
  y estabilidad.
- La validación disponible es **proxy**: sensibilidad de umbrales (±10 %) y diez fichas
  cualitativas revisables a mano (`data/processed_sample/case_studies/`).
- Consecuencia: un score alto significa "más señales activas", no "más probabilidad de fraude".

## 2. Umbrales y pesos no calibrados

- Los pesos (RF-01=15, RF-02=20, RF-03=20, RF-04=20, RF-05=25, RF-06=15; suma 115, recortada a 100)
  y los umbrales (desviación 10 %, recurrencia ≥ 2, concentración ≥ 50 %, resolución ≤ 2 días)
  son decisiones de diseño inspiradas en la literatura de red flags, no estimadas con datos.
- La evaluación de sensibilidad muestra estabilidad local: con factor 0,9 cambia el score del
  0,20 % de los contratos y con factor 1,1 del 4,89 %. Esto mide robustez frente a pequeñas
  variaciones, no corrección de los valores elegidos.

## 3. Cobertura desigual de las reglas en la muestra

Sobre la muestra reproducible de 3.437 contratos (CPV 71, 2024), con el scoring v3.0.0:

| Regla | Evaluable | Motivo principal |
|---|---:|---|
| RF-01 licitador único | 0 % | la muestra no conserva `source_tender_id` |
| RF-02 procedimiento | 99,65 % | |
| RF-03 recurrencia | 67,88 % | 1.104 contratos sin adjudicatario (DQ-01) |
| RF-04 concentración | 42,04 % | faltan importes adjudicados |
| RF-05 desviación de importe | 52,25 % | falta importe estimado o adjudicado |
| RF-06 plazo anómalo | 0 % | ninguna fila tiene ambas fechas válidas |

Ningún contrato es completamente evaluable. Un contrato sin señales puede ser, simplemente, un
contrato al que no se le han podido aplicar las reglas: por eso cada score publica
`evaluable_rules_count`, `not_evaluable_rules` y `evaluation_status`.

## 4. Calidad y cruce de fuentes

- 1.104 contratos de la muestra (32 %) no informan adjudicatario. Se publican como DQ-01 (calidad
  del dato) y no suman al score.
- Las intersecciones exactas BOE/PLACE/OpenTender por `contract_key_canon` son 0: el sistema no
  contrasta todavía la misma adjudicación entre fuentes.
- La evaluación se hace sobre la muestra de 3.437 filas, no sobre el canónico completo de 51.720.

## 5. Agent4 (RAG) evaluado sobre corpus sintético

- El corpus documental tiene 3 documentos sintéticos y el set de evaluación 3 casos (2 con
  evidencia y 1 negativo). Los resultados del 100 % en precisión@k, recall y trazabilidad de citas
  validan el **mecanismo** (recuperación, citas, contrato correcto, prudencia), no su rendimiento
  sobre pliegos reales.
- Las diez fichas de casos reales tienen 0 % de evidencia documental: el corpus no contiene sus
  documentos. Esa ausencia se publica como tal y no se interpreta como ausencia de riesgo.
- La calidad generativa del LLM local (qwen3:8b vía Ollama) no está evaluada; la evaluación
  offline cubre recuperación y estructura de la ficha.

## 6. Alcance de la demo

- El panel Streamlit reconstruye un caso sintético (`PW-2024-0001`) para la defensa; la pestaña
  de evolución temporal usa, por separado, la evaluación real de Agent2 sobre la muestra.
- No es una plataforma productiva: no hay autenticación, multiusuario ni ingesta continua.

## Trabajo futuro que resolvería cada limitación

1. Construir un conjunto de casos de referencia (resoluciones de tribunales de contratos,
   informes de órganos de control) para medir precisión de las reglas y calibrar pesos.
2. Conservar `source_tender_id` y las fechas en la normalización para hacer evaluables RF-01 y RF-06.
3. Mejorar el matching entre fuentes (identificadores de expediente, NIF de comprador y proveedor).
4. Ampliar el corpus de Agent4 con pliegos y adjudicaciones reales y evaluar el LLM con el mismo
   protocolo (p. ej. RAGAS).
5. Repetir la evaluación sobre el canónico completo de 51.720 contratos.
