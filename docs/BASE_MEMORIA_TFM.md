# Base documental para la memoria del TFM

Este documento no es la memoria. Es una guía de lectura para separar qué está implementado, qué
está en roadmap y qué solo puede presentarse como evaluación proxy.

## Cómo interpretar la documentación

- `PLAN_*.md`: define el diseño y el objetivo. No todo lo que aparece ahí está cerrado.
- `SEGUIMIENTO_*.md`: recoge el estado real y las decisiones ya tomadas.
- `STACK_*.md` y `ARQUITECTURA_*.md`: describen capa técnica y evolución prevista.
- Los docs de `PLAN_AGENTE*.md` mezclan en algunos puntos objetivo, implementación y limitación;
  deben leerse con atención a los títulos de sección.

## Qué está suficientemente implementado para escribirlo como estado actual

- Agent1:
  - ingesta y normalización de BOE, PLACE y OpenTender;
  - dataset canónico para Agent2;
  - cobertura y calidad de datos;
  - política documentada de `contract_key_canon`;
  - diagnóstico agregado de cobertura entre fuentes.
- Agent2:
  - red flags deterministas;
  - score por contrato;
  - score agregado por adjudicatario;
  - persistencia analítica en PostgreSQL;
  - validación de estabilidad;
  - comparación con Isolation Forest y PU learning;
  - evaluación proxy formal de la comparativa.
- Batch:
  - orquesta Agent1 y Agent2 en ejecuciones semanales o mensuales;
  - guarda snapshots de entrada y salida para trazabilidad;
  - genera un `freeze_manifest.json` en ejecuciones mensuales o forzadas como base reproducible
    para el TFM sin multiplicar los parquets.

## Qué debe presentarse como parcial o limitado

- Agent1:
  - las intersecciones BOE/PLACE/OpenTender siguen siendo 0;
  - la trazabilidad del cruce existe, pero no prueba coincidencia real entre fuentes;
  - algunas métricas no cumplen objetivo, aunque sí están medidas.
- Agent2:
  - la evaluación comparativa no es validación supervisada real;
  - `rule_positive` se usa como proxy porque no hay etiquetas de fraude confirmadas.
- Arquitectura futura:
  - Agent3, Agent4, grafo completo y capa documental avanzada siguen en roadmap.

## Qué es temporal y no debe versionarse

- `data/tmp/` se usa solo como espacio intermedio para descargas o descompresiones temporales;
  debe limpiarse al terminar y no formar parte de la evidencia final.

## Qué es evaluación proxy

Usar una señal operativa o derivada como referencia de contraste cuando no existe ground truth.
En este proyecto:

- `rule_positive` sirve para comparar Isolation Forest y PU learning;
- la evaluación es reproducible y útil;
- pero no se debe presentar como medición final de fraude real.

## Cómo redactarlo en la memoria

- Separar siempre:
  - implementado;
  - medido pero no alcanzado;
  - no evaluable;
  - roadmap.
- Cuando un objetivo no se cumple, decirlo y explicar por qué.
- No convertir un plan técnico en un resultado cerrado.
- No presentar una evaluación proxy como validación supervisada.

## Documentos de apoyo directo

- `docs/PLANIFICACION_TFM.md`
- `docs/STACK_TECNICO_PROYECTO.md`
- `docs/SEGUIMIENTO_AGENTES.md`
- `docs/SEGUIMIENTO_AGENT1.md`
- `docs/PLAN_AGENTE1_PIPELINE.md`
- `docs/PLAN_AGENTE2_SCORING.md`
