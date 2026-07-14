# Diagnostico de cobertura entre fuentes

## Resumen cuantitativo

| Fuente | Claves canonicas |
|---|---:|
| BOE | 976 |
| PLACE | 1587 |
| OpenTender | 874 |
| Universo | 3437 |

## Intersecciones exactas

| Par de fuentes | Intersecciones |
|---|---:|
| boe_place | 0 |
| boe_opentender | 0 |
| place_opentender | 0 |

## Lectura en contexto de TFM

| Dimension | Estado | Lectura |
|---|---|---|
| Implementado | cerrado para el TFM | Ingesta, normalizacion canonica, trazabilidad de fuente y diagnostico de cobertura sobre 3437 claves. |
| Evaluado | medido con evidencias | Cobertura por fuente, duplicados, intersecciones exactas y candidatos aproximados de matching. |
| Resultado critico | warning metodologico | Las intersecciones exactas son 0; la cobertura es aditiva, no transversal. |
| Extension futura | fuera del cierre actual | Calibrar una politica de matching con muestra manual y decisiones auditables antes de fusionar fuentes. |

## Discusion analitica

- Para un TFM, el valor del resultado no esta solo en obtener mas cobertura, sino en demostrar que cobertura por fuente y cobertura transversal son propiedades distintas.
- Con intersecciones exactas nulas, el sistema sigue siendo robusto para analisis reproducible por fuente, pero pierde capacidad de triangulacion entre portales.
- Forzar fusiones aproximadas mejoraria artificialmente algunos indicadores, pero reduciria trazabilidad y aumentaria riesgo de falsos matches.

## Implicaciones para version institucional

- No se debe usar como registro consolidado unico sin validacion adicional.
- Los historiales comprador-proveedor pueden quedar fragmentados por fuente.
- Las metricas transversales deben marcarse como exploratorias.
- Una version institucional necesita reglas de matching revisables y auditables.

## Interpretacion

La cobertura actual es aditiva por fuente: el universo canonico conserva registros de BOE, PLACE y OpenTender, pero no acredita solapamiento exacto entre ellas.

Los candidatos aproximados son utiles como cola de revision, pero no deben usarse para fusionar contratos sin validacion adicional.

**Aportacion metodologica:** El resultado muestra que integrar datos abiertos de contratacion no depende solo de llevarlos a un esquema comun: requiere una politica explicita de identificadores, normalizacion y validacion de matches.

**Limite de uso:** El pipeline puede alimentar analisis por fuente, scoring exploratorio y dashboard trazable; no debe presentarse como contraste institucional consolidado entre fuentes.

## Robustez

- El scoring por fuente individual sigue siendo reproducible y trazable.
- La ausencia de intersecciones limita la triangulacion entre plataformas.
- Los historiales de comprador-proveedor pueden quedar fragmentados por fuente.
- Los indicadores que dependen de consolidacion transversal deben tratarse como exploratorios.

## Readiness institucional

| Componente | Estado | Evidencia |
|---|---|---|
| ingesta_y_trazabilidad_por_fuente | green | Hay claves canonicas generadas para BOE, PLACE y OpenTender. |
| cobertura_canonica_agent2 | green | Universo canonico: 3437 claves. |
| matching_transversal_validado | red | Las intersecciones exactas entre fuentes son 0. |
| cola_de_revision_de_matches | yellow | Existen candidatos aproximados para revision no destructiva. |
| uso_institucional | yellow | Apto como prototipo de priorizacion y auditoria metodologica; no como registro institucional consolidado hasta validar matching transversal. |

## Siguientes pasos

- No usar intersecciones entre fuentes como evidencia de contraste hasta resolver el matching.
- Mantener separados los resultados por fuente hasta validar pares candidatos.
- Priorizar normalizacion de expediente, comprador, fecha, titulo, importe y CPV.
- Crear una muestra revisada manualmente de pares candidato/no-match para calibrar umbrales.
- Registrar la decision de matching como dato auditable antes de fusionar contratos.
- Tratar cualquier metrica transversal como exploratoria mientras present_in_all sea 0.
