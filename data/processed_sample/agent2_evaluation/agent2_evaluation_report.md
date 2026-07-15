# Evaluacion de sensibilidad de Agent2

- Contratos de la muestra: 3437
- Snapshot: `9e983848aad0a1af35f7230f820da982ab04d8d9172648d0d615d6b0d655e377`
- Reglas: RF-01 a RF-06
- Escenarios: umbrales x0.9, x1.0 y x1.1

## Evaluabilidad del escenario base

| Regla | Evaluables | No evaluables | Cobertura |
|---|---:|---:|---:|
| RF-01 | 3437 | 0 | 100.00% |
| RF-02 | 3425 | 12 | 99.65% |
| RF-03 | 2333 | 1104 | 67.88% |
| RF-04 | 1445 | 1992 | 42.04% |
| RF-05 | 1796 | 1641 | 52.25% |
| RF-06 | 0 | 3437 | 0.00% |

## Frecuencia de flags

| Regla | -10 % | Base | +10 % |
|---|---:|---:|---:|
| RF-01 | 1104 | 1104 | 1104 |
| RF-02 | 12 | 12 | 12 |
| RF-03 | 730 | 730 | 566 |
| RF-04 | 36 | 34 | 3 |
| RF-05 | 545 | 540 | 539 |
| RF-06 | 0 | 0 | 0 |

## Distribucion de riesgo

| Escenario | Sin flags | Bajo >0 | Medio | Alto | Critico | Media score |
|---|---:|---:|---:|---:|---:|---:|
| lower | 1368 | 1496 | 560 | 13 | 0 | 13.31 |
| base | 1371 | 1500 | 553 | 13 | 0 | 13.26 |
| upper | 1516 | 1375 | 546 | 0 | 0 | 12.12 |

## Estabilidad frente al escenario base

| Escenario | Score sin cambio | Nivel sin cambio | Flags sin cambio |
|---|---:|---:|---:|
| lower | 99.80% | 99.80% | 99.80% |
| upper | 95.11% | 99.04% | 95.11% |

## Campos ausentes o no validos

| Campo | Filas |
|---|---:|
| `buyer_name` | 0 |
| `supplier_name` | 1104 |
| `procedure` | 12 |
| `estimated_value_eur_missing_or_nonpositive` | 150 |
| `awarded_value_eur` | 1511 |
| `publication_date_invalid` | 2461 |
| `award_date_invalid` | 3067 |
| `pair_metric_unavailable` | 1104 |
| `concentration_metric_unavailable` | 1992 |

## Limitaciones

- The evaluation uses the 3,437-row reproducible sample, not the 51,720-row full run.
- The results prioritise human review and do not classify or confirm fraud.
- The sensitivity analysis evaluates deterministic rules without labelled outcomes.
