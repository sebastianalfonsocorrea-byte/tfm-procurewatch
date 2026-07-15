# Benchmark ProcureWatch

- Estado global: **warning**
- Metricas evaluadas: **34**

## Lectura en contexto de TFM

ProcureWatch queda evaluado como prototipo academico funcional. El estado warning preserva una limitacion metodologica relevante, no un fallo tecnico del pipeline.

El sistema es defendible para priorizacion, trazabilidad y discusion metodologica; una version institucional exigiria ampliar datos, validar matching interfuente y contrastar resultados con referencia externa.

## Matriz de alcance del TFM

| Componente | Implementado | Evaluado | Evidencia | Limite actual | Extension |
|---|---|---|---|---|---|
| Agent1 - ingesta y normalizacion | si | si | calidad de campos, duplicados y cobertura interfuente | cobertura canonica por fuente sin matching exacto transversal | validacion manual y politica auditable de matching |
| Agent2 - scoring de riesgo | si | parcial en demo integrada | score y red flags trazables | sin benchmark estadistico amplio | validar con dataset mayor y casos etiquetados |
| Agent3 - grafo y relaciones | si | si | nodos, aristas, comunidades, modularidad y cobertura de features | validado en muestra reproducible y demo local, no en el canonico completo | ejecucion sobre volumen completo y analisis longitudinal |
| Agent4 - capa documental | si | si | retrieval, citas, trazabilidad y prudencia del lenguaje | corpus local/sintetico y evaluacion RAGAS no representativa | corpus real ampliado y evaluacion comparativa de LLM local |
| Integracion y dashboard | demo | si | flujo Agent2-Agent3-Agent4 y validaciones integradas | no equivale a despliegue productivo institucional | servicios persistentes, seguridad y operacion continua |

## Conclusiones academicas

- La contribucion principal del TFM no es afirmar deteccion automatica de fraude, sino construir un pipeline trazable para priorizar revision.
- La ausencia de intersecciones utiles entre fuentes convierte la calidad del matching en un resultado empirico del trabajo.
- Las fichas documentales son evaluables por fidelidad, cobertura y citas, pero no sustituyen la interpretacion juridica ni la auditoria humana.

## Resumen por agente

| Agente | Estado | Metricas |
|---|---|---:|
| agent1 | warning | 9 |
| agent2 | pass | 3 |
| agent3 | pass | 7 |
| agent4 | pass | 8 |
| integrated | pass | 7 |

## Metricas

### agent1

| Metrica | Valor | Umbral | Estado | Evidencia |
|---|---:|---|---|---|
| Existe reporte de calidad Agent1 | True | true | pass | data\processed_sample\agent1_data_quality_summary.json |
| Cobertura de contract_key_canon | 1.0000 | >= 0.95 | pass | field_quality.contract_key_canon.coverage_ratio |
| Cobertura de source | 1.0000 | >= 0.95 | pass | field_quality.source.coverage_ratio |
| Cobertura de buyer_name | 1.0000 | >= 0.95 | pass | field_quality.buyer_name.coverage_ratio |
| Cobertura de cpv_codes_raw | 1.0000 | >= 0.95 | pass | field_quality.cpv_codes_raw.coverage_ratio |
| Duplicados por fuente y clave canonica | 0 | = 0 | pass | duplicate_source_contract_keys |
| Existe diagnostico de cobertura entre fuentes | True | true | pass | data\processed_sample\agent1_source_coverage_analysis.json |
| Intersecciones exactas entre fuentes | 0 | > 0 deseable | warning | exact_intersections |
| Candidatos aproximados de matching | 2 | informativo | pass | candidate_counts |

- No hay intersecciones exactas entre BOE, PLACE y OpenTender; el matching transversal no queda validado.

### agent2

| Metrica | Valor | Umbral | Estado | Evidencia |
|---|---:|---|---|---|
| Score Agent2 presente en demo integrada | 0.5000 | no nulo | pass | integrated.summary.agent2_risk_score |
| Red flags Agent2 presentes en demo integrada | 2 | > 0 | pass | integrated.summary.agent2_red_flags |
| Sensibilidad de umbrales Agent2 documentada | 3 | 3 escenarios y comparacion con base | pass | data\processed_sample\agent2_evaluation\agent2_evaluation_report.json |

- Agent2 se mide desde la demo integrada porque no hay scoring completo en processed_dir.

### agent3

| Metrica | Valor | Umbral | Estado | Evidencia |
|---|---:|---|---|---|
| Nodos del grafo | 11 | >= 1 | pass | nodes_rows |
| Aristas del grafo | 13 | >= 1 | pass | edges_rows |
| Comunidades detectadas | 2 | >= 1 | pass | community_count |
| Modularidad de la particion Louvain | 0.3166 | > 0.30 | pass | Q sobre el grafo simple no ponderado de Agent3 |
| Cobertura de features por contrato | 1.0000 | 100% | pass | agent2_features_rows / input_rows |
| Contratos sin proveedor en grafo | 0 | informativo | pass | contracts_without_supplier |
| Contratos sin CPV en grafo | 0 | informativo | pass | contracts_without_cpv |

### agent4

| Metrica | Valor | Umbral | Estado | Evidencia |
|---|---:|---|---|---|
| Accuracy de expectativas | 1.0000 | >= 0.90 | pass | summary.expectation_accuracy |
| Precision@k media | 1.0000 | >= 0.90 | pass | summary.average_precision_at_k |
| Recall medio de documentos esperados | 1.0000 | >= 0.90 | pass | summary.average_expected_document_recall |
| Trazabilidad media de citas | 1.0000 | >= 0.95 | pass | summary.average_citation_traceability |
| Consistencia media de contrato en citas | 1.0000 | >= 0.95 | pass | summary.average_contract_key_consistency |
| Ausencia de declaraciones de fraude no soportadas | 1.0000 | >= 1.00 | pass | summary.no_unsupported_fraud_claim_ratio |
| Validacion practica de fichas trazables | 1.0000 | >= 0.95 | pass | summary.practical_validation_pass_ratio |
| Evaluacion RAGAS | not_run | run deseable | not_applicable | ragas.status |

- Corpus sintetico demasiado pequeno para metricas RAGAS representativas.

### integrated

| Metrica | Valor | Umbral | Estado | Evidencia |
|---|---:|---|---|---|
| Demo integrada en estado ready | ready | ready | pass | integrated.status |
| Validaciones integradas superadas | 1.0000 | 100% | pass | integrated.validations |
| Score Agent2 integrado | 0.5000 | no nulo | pass | summary.agent2_risk_score |
| Features Agent3 integradas | 3 | > 0 | pass | summary.agent3_features |
| Evidencias y citas Agent4 integradas | 2/2 | > 0/> 0 | pass | summary.agent4_evidences / summary.agent4_citations |
| Diez fichas de caso trazables | {'cases': 10, 'selection': {'high_score': 5, 'medium_risk': 3, 'control': 2}, 'rule_evidence_coverage': 1.0, 'relationships_coverage': 1.0} | 10 casos; composicion 5/3/2; trazabilidad completa | pass | data\processed_sample\case_studies\case_studies_report.json |
| Validacion dashboard | ready | ready | pass | data\processed\agent3_agent4_demo_2026_06_23\dashboard_validation_report.json |

- Demo sintetica y offline: no usa raw completos ni descarga datos en vivo.
- No requiere Docker, PostgreSQL, Neo4j, Qdrant ni Ollama.
- Agent4 usa corpus documental local/sintetico y no declara fraude.

## Limitaciones globales

- agent1: No hay intersecciones exactas entre BOE, PLACE y OpenTender; el matching transversal no queda validado.
- agent2: Agent2 se mide desde la demo integrada porque no hay scoring completo en processed_dir.
- agent4: Corpus sintetico demasiado pequeno para metricas RAGAS representativas.
- integrated: Demo sintetica y offline: no usa raw completos ni descarga datos en vivo.
- integrated: No requiere Docker, PostgreSQL, Neo4j, Qdrant ni Ollama.
- integrated: Agent4 usa corpus documental local/sintetico y no declara fraude.
