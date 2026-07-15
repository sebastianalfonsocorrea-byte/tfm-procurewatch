# Evaluacion documental Agent4

- Modo: **offline**
- Casos: **3**
- Casos con evidencia: **2**
- Accuracy de expectativas: **100.00%**
- Precision@k media: **100.00%**
- Recall medio de documentos esperados: **100.00%**
- Cobertura media de citas: **100.00%**
- Trazabilidad media de citas: **100.00%**
- Consistencia media de contrato: **100.00%**
- Ratio de validacion practica: **100.00%**

## Evaluacion practica para el TFM

La capa documental se evalua como soporte explicativo del TFM: debe recuperar evidencia, citarla de forma trazable, conservar el contrato correcto y evitar afirmaciones no soportadas.

**LLM local:** La evaluacion offline valida recuperacion, citas y estructura de ficha. La calidad generativa del LLM local queda como contraste futuro con el mismo protocolo.

| Dimension | Metrica | Resultado | Lectura |
|---|---|---:|---|
| Fidelidad documental | average_precision_at_k | 100.00% | la evidencia recuperada coincide con documentos esperados |
| Cobertura documental | average_expected_document_recall | 100.00% | los documentos esperados aparecen en el contexto recuperado |
| Trazabilidad de citas | average_citation_traceability | 100.00% | las citas conservan document_id, chunk_id y contract_key_canon |
| Consistencia del contrato | average_contract_key_consistency | 100.00% | la evidencia usada pertenece al contrato consultado |
| Prudencia explicativa | no_unsupported_fraud_claim_ratio | 100.00% | la ficha no declara fraude sin soporte documental |
| Validacion practica | practical_validation_pass_ratio | 100.00% | los casos cumplen las condiciones minimas de ficha trazable |

### Alcance validado

- retrieval local sobre corpus sintetico
- citas trazables por documento, fragmento y contrato
- casos con evidencia y caso negativo sin evidencia
- frontera de decision orientada a revision humana

### Futuras iteraciones

- ampliar corpus con pliegos y adjudicaciones reales heterogeneas
- comparar modo offline, Qdrant y LLM local con el mismo set de evaluacion
- incorporar mas casos negativos y preguntas adversariales
- ejecutar RAGAS u otra evaluacion externa cuando el corpus sea representativo

## Casos

| Caso | Evidencia | Citas | Precision@k | Recall docs | Validacion |
|---|---:|---:|---:|---:|---|
| eval-pw-2024-0001-evidence | 2 | 2 | 100.00% | 100.00% | ok |
| eval-pw-2024-0002-evidence | 1 | 1 | 100.00% | 100.00% | ok |
| eval-pw-2024-9999-no-docs | 0 | 0 | n/a | n/a | ok |

## Limites

- La evaluacion local mide trazabilidad y retrieval, no correccion juridica.
- El corpus sintetico no representa la variabilidad documental real.
- Agent4 no declara fraude; solo resume evidencia para revision humana.
