# Evaluacion de diez fichas de caso

- Casos: **10**
- Composicion: `{'high_score': 5, 'medium_risk': 3, 'control': 2}`
- Cobertura de evidencia de reglas: 100.00%
- Relaciones disponibles: 100.00%
- Casos con evidencia documental: 0.00%
- Validacion practica: **pass**

| Caso | Grupo | Fuente | Score | Nivel | Reglas | Evidencia doc. |
|---|---|---|---:|---|---|---:|
| CS-01 | high_score | place | 65 | alto | RF-05, RF-03, RF-04 | 0 |
| CS-02 | high_score | place | 65 | alto | RF-05, RF-03, RF-04 | 0 |
| CS-03 | high_score | place | 65 | alto | RF-05, RF-03, RF-04 | 0 |
| CS-04 | high_score | place | 65 | alto | RF-05, RF-03, RF-04 | 0 |
| CS-05 | high_score | place | 65 | alto | RF-05, RF-03, RF-04 | 0 |
| CS-06 | medium_risk | place | 45 | medio | RF-05, RF-03 | 0 |
| CS-07 | medium_risk | boe | 45 | medio | RF-02, RF-05 | 0 |
| CS-08 | medium_risk | opentender | 40 | medio | RF-03, RF-04 | 0 |
| CS-09 | control | place | 0 | bajo | ninguna | 0 |
| CS-10 | control | boe | 0 | bajo | ninguna | 0 |

## Limitaciones

- La seleccion usa la muestra reproducible de 3.437 contratos, no el canonico completo.
- No existen etiquetas de fraude ni revision experta externa para estos diez casos.
- La ausencia de evidencia documental se registra sin sustituirla por contenido sintetico.
- Los importes y codigos de procedimiento deben verificarse en la fuente original.

**Limite de decision:** Las fichas evaluan priorizacion y explicacion para revision humana; no declaran fraude.
