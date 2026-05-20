# Guía de Entrevista: ProcureWatch Analytics

## Objetivo de la Guía

Este documento resume cómo explicar el TFM en una entrevista técnica o de RR. HH. El enfoque está alineado con un perfil de **Data Analyst / Data & AI Consultant**, orientado a datos, automatización, visualización, ingeniería analítica e IA generativa.

Se ha revisado la carpeta `CV/`. El PDF `CV_Sebastian_Alfonso_DataAnalyst.pdf` no se ha podido extraer limpiamente desde el entorno porque está generado como PDF con imagen y flujos comprimidos, pero sí se ha podido leer `Apuntes_Estudio_CV_Sebastian.doc`, que resume los conceptos del CV: Python, pandas, PostgreSQL, KPIs, BI, GenAI, RAG, LangChain, LangGraph, Flowise, extracción documental, IoT, FIWARE, Docker, FastAPI, Spark/PySpark y bases SQL/NoSQL.

## Pitch Corto: 30 Segundos

Estoy desarrollando un TFM llamado **ProcureWatch Analytics**, una plataforma analítica y multiagente para detectar patrones de riesgo en contratación pública española. Trabajo con datos abiertos de contratación, especialmente contratos BOE 2014-2024 y el dominio CPV 71, que corresponde a servicios de arquitectura, ingeniería e inspección.

El proyecto combina limpieza y modelado de datos, indicadores de riesgo o red flags, análisis de redes entre organismos y proveedores, web scraping documental con NLP/RAG, orquestación de agentes con **LangChain y LangGraph**, y visualización explicable mediante dashboard. Mi objetivo no es declarar fraude, sino priorizar contratos que merecen revisión mediante señales objetivas, trazables y reproducibles.

## Pitch Técnico: 2 Minutos

El proyecto parte de un problema real: la contratación pública genera mucho volumen de datos, pero los sistemas de control suelen ser reactivos y tienen limitaciones para revisar todos los expedientes. ProcureWatch propone un prototipo de analítica preventiva.

La arquitectura se organiza en varios bloques. Primero, construyo un pipeline de ingesta y limpieza para normalizar datos de contratación según criterios cercanos al estándar **OCDS**. Después implemento un motor de **red flags** con indicadores como baja concurrencia, concentración de adjudicaciones, desviaciones de importe, plazos anómalos o recurrencia organismo-proveedor.

El tercer bloque usa **análisis de redes**: represento organismos y proveedores como un grafo bipartito, calculo métricas de centralidad, concentración y comunidades, y uso esas señales como variables adicionales de riesgo. El cuarto bloque explora **web scraping y NLP** sobre anuncios BOE/PLACE y documentos textuales reutilizables para extraer entidades y posibles criterios restrictivos.

La parte de IA generativa se plantea como una **orquestación multiagente**: cada agente tiene una responsabilidad concreta, por ejemplo ingesta, scoring, análisis de red, análisis documental, validación y explicación final. Uso **LangChain** para conectar modelos, prompts, herramientas y recuperación de información, y **LangGraph** para definir el flujo con estados, nodos, condiciones, reintentos y pasos de validación. Finalmente, integro los resultados en un dashboard con filtros, KPIs, explicaciones de riesgo y visualización de relaciones.

Para una empresa, este proyecto demuestra que puedo convertir un problema de negocio complejo en un sistema de datos reproducible: desde la fuente hasta el insight accionable.

## Stack Tecnológico

### Datos y Backend Analítico

- **Python**: lenguaje principal para ingesta, limpieza, análisis y scoring.
- **pandas / NumPy**: transformación, agregación y análisis exploratorio.
- **scikit-learn**: detección de anomalías, modelos baseline y evaluación.
- **Parquet / CSV**: almacenamiento intermedio reproducible.
- **OCDS**: referencia conceptual para estructurar datos de contratación.

### Grafos y Redes

- **NetworkX**: construcción de grafos organismo-proveedor y cálculo de métricas.
- **Louvain / Leiden**: detección de comunidades y estructuras recurrentes.
- **Neo4j**: opción de arquitectura para consultas de relaciones complejas.

### NLP y Documentos

- **BeautifulSoup**: extracción y parsing de páginas HTML del BOE/PLACE.
- **spaCy**: extracción de entidades y procesamiento lingüístico en español.
- **LLMs locales como Mistral/Qwen**: posible extensión para clasificación o extracción asistida, sin depender necesariamente de servicios cloud.
- **requests / lxml**: apoyo para descarga, parseo y normalización de contenido web cuando BeautifulSoup no sea suficiente.

### IA Generativa y Orquestación Multiagente

- **LangChain**: conexión de LLMs con prompts, herramientas, loaders, retrievers, embeddings y cadenas de procesamiento.
- **LangGraph**: definición de agentes como grafo de estados, con nodos, ramas condicionales, memoria, validación y control del flujo.
- **RAG**: recuperación de contexto desde documentación, contratos, pliegos o normativa antes de generar una respuesta.
- **Flowise**: prototipado visual de flujos LLM y RAG.
- **Prompt engineering**: diseño de instrucciones, formatos de salida, criterios de calidad y límites.
- **Evaluación de respuestas**: revisión de trazabilidad, fuentes, consistencia y reducción de alucinaciones.

### Visualización y Producto

- **Streamlit o Plotly Dash**: dashboard analítico rápido y demostrable.
- **Plotly**: visualización interactiva de KPIs, distribuciones y rankings.
- **Sigma.js / Cytoscape.js**: alternativas para visualización web de grafos.

### Calidad, Reproducibilidad y Proyecto

- **Git**: control de versiones.
- **pytest**: pruebas de reglas de scoring y transformaciones.
- **ruff**: linting y formato en Python.
- **Markdown / LaTeX**: documentación técnica y memoria académica.
- **Docker / FastAPI**: posible empaquetado y exposición de servicios analíticos.
- **PostgreSQL / Neo4j / MongoDB**: almacenamiento relacional, grafo y documental según el tipo de dato.

### Stack Complementario Alineado con el CV

- **SQL avanzado**: CTEs, joins, window functions, agregaciones y validación.
- **PostgreSQL y esquema estrella**: modelado analítico de hechos y dimensiones.
- **PowerBI / Tableau / Grafana**: BI, reporting y visualización operacional.
- **Spark / PySpark / Hadoop**: base conceptual para procesamiento distribuido.
- **MQTT / Node-RED / FIWARE / TimescaleDB**: experiencia relacionada con IoT y datos temporales.

## Cómo Alinearlo con un Perfil Data Analyst

Este TFM refuerza competencias típicas de Data Analyst y las amplía hacia Data Science aplicada:

- **Extracción y limpieza de datos**: trabajo con fuentes públicas heterogéneas, datos incompletos y normalización.
- **Análisis exploratorio**: identificación de patrones por año, organismo, proveedor, CPV e importe.
- **Definición de KPIs**: diseño de indicadores de riesgo interpretables.
- **Visualización**: creación de dashboards orientados a toma de decisiones.
- **Automatización**: conversión de análisis manual en pipelines reproducibles.
- **Storytelling con datos**: explicación de hallazgos sin sobredimensionar conclusiones.
- **Pensamiento crítico**: distinción entre anomalía, riesgo e irregularidad probada.
- **IA aplicada a negocio**: uso de LLMs, RAG y agentes con controles, no como una capa decorativa.
- **Ingeniería analítica**: estructura raw/processed, trazabilidad, logging, SQL y diseño de modelos de datos.

Frase útil:

> Lo conecto con mi perfil de Data Analyst porque el núcleo del proyecto es transformar datos públicos complejos en indicadores claros y accionables para apoyar decisiones de supervisión.

También puedes conectarlo con Data & AI Consultant:

> Lo conecto con consultoría de datos e IA porque no solo analizo datos: diseño una solución completa con pipeline, reglas, agentes, validación, visualización y una narrativa comprensible para negocio.

## Orquestación Multiagente con LangChain y LangGraph

La orquestación multiagente es una de las partes más diferenciales del TFM. La idea es dividir el sistema en agentes especializados, cada uno con una responsabilidad clara, y coordinarlos mediante un grafo de ejecución.

### Agentes Propuestos

- **Agente de ingesta**: localiza, carga y normaliza datos de contratos.
- **Agente de calidad**: revisa nulos, duplicados, formatos, importes, fechas y consistencia.
- **Agente de red flags**: calcula indicadores de riesgo tabulares.
- **Agente de grafos**: construye relaciones organismo-proveedor y calcula métricas de red.
- **Agente documental**: procesa anuncios, páginas públicas y documentos textuales con web scraping/NLP y extrae entidades o criterios.
- **Agente evaluador**: revisa coherencia, detecta posibles errores y valida que haya evidencias.
- **Agente explicador**: genera una explicación final trazable para dashboard o informe.

### Papel de LangChain

LangChain sirve como capa de integración. Permite conectar el LLM con herramientas concretas: lectura de documentos, consultas a bases de datos, recuperación RAG, llamadas a funciones Python, prompts estructurados y parsers de salida. En una entrevista, conviene decir que LangChain no sustituye al pipeline de datos; lo uso para conectar razonamiento LLM con herramientas controladas.

### Papel de LangGraph

LangGraph permite modelar el flujo como un grafo con estado. Esto encaja mejor que una cadena lineal porque el análisis de riesgo tiene bifurcaciones: si faltan datos, se vuelve a calidad; si hay documentos, se activa NLP; si el score no tiene evidencias suficientes, se envía a validación; si todo está correcto, se genera explicación final.

Ejemplo de flujo:

```text
Ingesta -> Calidad -> Scoring -> Grafos -> Documentos -> Validación -> Explicación -> Dashboard
              ^                         |              |
              |                         v              |
              +--------- Revisión / reintento <--------+
```

### Cómo Explicarlo en Entrevista

> Uso LangGraph porque necesito controlar un proceso con estado, ramas y validaciones. No quiero una llamada simple al LLM, sino un flujo donde cada agente produce una salida verificable y el sistema puede decidir si continuar, reintentar o pedir más contexto.

> Uso LangChain para conectar el modelo con herramientas: documentos, embeddings, consultas, funciones de scoring y prompts estructurados. LangGraph coordina el orden y la lógica; LangChain aporta conectores y componentes.

### Qué Demuestra Esta Parte

- Comprensión de arquitecturas GenAI más allá del prompt.
- Capacidad de diseñar agentes con responsabilidades separadas.
- Control de calidad, trazabilidad y validación de salidas LLM.
- Criterio para decidir cuándo usar reglas deterministas y cuándo usar LLM.
- Alineación con proyectos reales de consultoría de datos e IA.

## Qué Estoy Aprendiendo

- A diseñar un pipeline analítico de extremo a extremo.
- A trabajar con datos reales, incompletos y con problemas de calidad.
- A traducir literatura académica en reglas e indicadores implementables.
- A usar grafos para detectar relaciones que no aparecen en tablas simples.
- A aplicar web scraping y NLP a documentos administrativos publicados en HTML o formatos textuales reutilizables.
- A construir explicabilidad alrededor de modelos e indicadores.
- A presentar resultados con cautela: el sistema detecta riesgo, no culpabilidad.
- A orquestar agentes con LangChain y LangGraph para coordinar análisis, validación y explicación.
- A diseñar soluciones GenAI con RAG, herramientas y control de flujo, no solo prompts aislados.

## Qué Problema Resuelve

La contratación pública mueve grandes volúmenes de dinero y documentación. Revisar manualmente todos los contratos no es escalable. El proyecto ayuda a priorizar la revisión detectando señales como:

- proveedores con adjudicaciones recurrentes en un mismo organismo;
- contratos con baja concurrencia;
- importes o plazos atípicos;
- concentración de mercado;
- comunidades de organismos y empresas con relaciones inusuales;
- documentos con criterios técnicos potencialmente restrictivos.

## Por Qué Elegí CPV 71

Elegí CPV 71 porque es un dominio suficientemente relevante y controlable para validar el prototipo. Incluye servicios de arquitectura, construcción, ingeniería e inspección. Según el análisis disponible, contiene **3.443 contratos adjudicados**, más de **2.179 millones de euros**, **394 organismos contratantes** y **2.031 empresas adjudicatarias**.

Además, es un sector adecuado porque los servicios de ingeniería tienen entregables y criterios técnicos comparables, generan relaciones interesantes entre organismos y proveedores, y contienen documentación técnica útil para validar el módulo NLP.

## Cómo Explicar la Arquitectura

Puedes explicarla como un flujo:

1. **Ingesta**: recopilo datos públicos de contratación.
2. **Normalización**: limpio campos, fechas, importes, organismos, proveedores y CPV.
3. **Feature engineering**: creo variables de riesgo e indicadores.
4. **Scoring**: calculo una puntuación explicable por contrato, proveedor y organismo.
5. **Grafos**: analizo relaciones organismo-proveedor y comunidades.
6. **Scraping/NLP/RAG**: extraigo información de anuncios y documentos contractuales reutilizables.
7. **Agentes LangChain/LangGraph**: coordino scoring, grafos, documentos, validación y explicación.
8. **Dashboard**: muestro KPIs, filtros, rankings y explicación del riesgo.

Frase útil:

> Es un proyecto end-to-end: no me quedo solo en un notebook, sino que busco una arquitectura reproducible que conecte datos, análisis, modelos y visualización.

## Preguntas Probables y Respuestas

### ¿Esto detecta fraude?

No. Detecta **patrones de riesgo**. La diferencia es importante: una anomalía estadística o una red flag no prueba fraude. Sirve para priorizar auditorías o revisiones humanas con criterios objetivos.

### ¿Por qué no usar solo machine learning?

Porque en este dominio no siempre hay etiquetas fiables de fraude. Por eso combino reglas explicables basadas en literatura, análisis no supervisado y métricas de red. Es más defendible y transparente.

### ¿Por qué usar agentes?

Porque el problema no es una única predicción. Hay varias tareas encadenadas: limpiar datos, calcular reglas, analizar redes, leer documentos, validar evidencias y explicar resultados. Los agentes permiten separar responsabilidades y LangGraph permite controlar el flujo con estados y validaciones.

### ¿Qué diferencia hay entre LangChain y LangGraph?

LangChain me ayuda a conectar el LLM con herramientas, documentos, prompts y recuperación de contexto. LangGraph me permite orquestar esos pasos como un grafo con estado, condiciones, ciclos y reintentos. En resumen: LangChain aporta componentes; LangGraph coordina el proceso.

### ¿Dónde usarías RAG?

Lo usaría para que el agente documental o explicador consulte pliegos, normativa, descripciones de CPV, taxonomías de red flags y documentación interna antes de generar una explicación. Así la respuesta queda apoyada en contexto recuperado, no solo en conocimiento del modelo.

### ¿Qué parte es más valiosa técnicamente?

La integración. El valor está en combinar datos tabulares, scoring explicable, grafos y documentos. Cada fuente aporta una señal distinta del riesgo.

### ¿Qué harías si tuvieras más tiempo?

Ampliaría la integración con PLACE, incorporaría más CPVs para comparar sectores, validaría con expertos en contratación pública y mejoraría el módulo NLP con más documentos etiquetados.

### ¿Cuál fue la mayor dificultad?

La calidad y heterogeneidad de los datos. En contratación pública hay diferencias de formato, campos incompletos, criterios cambiantes y ambigüedad entre contrato, lote, expediente y adjudicación.

### ¿Cómo evalúas el sistema si no hay etiquetas?

Uso validación indirecta: distribución de scores, análisis de sensibilidad, comparación con literatura, revisión de casos extremos y coherencia de métricas de red. También se puede validar con expertos.

## Cómo Venderlo Según el Tipo de Entrevista

### Para Data Analyst

Enfatiza limpieza, KPIs, dashboard, storytelling, SQL/Python, calidad de datos y toma de decisiones.

Mensaje:

> Este proyecto demuestra que puedo transformar datos complejos en indicadores claros y visualizaciones útiles para negocio.

### Para Data Scientist

Enfatiza anomalías, scoring, grafos, NLP, evaluación sin etiquetas y explicabilidad.

Mensaje:

> Trabajo con un caso real donde no basta con aplicar un modelo; hay que diseñar señales robustas, interpretables y validables.

### Para Data & AI Consultant

Enfatiza GenAI aplicada, RAG, agentes, LangChain, LangGraph, trazabilidad, control de riesgo y traducción del caso de uso a arquitectura.

Mensaje:

> Este proyecto me permite explicar cómo paso de una necesidad de negocio a una solución de datos e IA: pipeline, reglas, agentes, validación y dashboard.

### Para Data Engineer Junior

Enfatiza pipelines, estructura de repositorio, datos raw/processed, reproducibilidad, testing y documentación.

Mensaje:

> Estoy aprendiendo a convertir análisis exploratorio en procesos repetibles y mantenibles.

### Para Consultoría / Sector Público

Enfatiza transparencia, eficiencia, priorización de revisión, trazabilidad y limitaciones jurídicas.

Mensaje:

> La propuesta no sustituye al auditor, sino que le ayuda a enfocar recursos donde hay más señales objetivas de riesgo.

## Frases Potentes para Entrevista

- "El proyecto convierte datos públicos dispersos en señales de riesgo interpretables."
- "No busco predecir culpabilidad; busco priorizar revisión con evidencia objetiva."
- "La parte diferencial es combinar red flags, grafos y NLP en un mismo flujo analítico."
- "Uso LangGraph para que el sistema no sea una cadena rígida, sino un flujo con estados, validaciones y reintentos."
- "LangChain conecta el LLM con herramientas; LangGraph organiza la lógica de los agentes."
- "Trabajo con datos reales, así que el reto principal es la calidad y la trazabilidad."
- "El dashboard está pensado para explicar por qué un contrato tiene riesgo, no solo para mostrar un score."
- "Me ha ayudado a pasar de análisis en notebook a una arquitectura más cercana a producto de datos."

## Demo Recomendada

Si tienes que enseñarlo en una entrevista, prepara una demo de 5 minutos:

1. Mostrar el problema: volumen de contratación y necesidad de priorización.
2. Enseñar el dataset filtrado por CPV 71.
3. Mostrar 3 red flags calculadas.
4. Enseñar un grafo simple organismo-proveedor.
5. Explicar el flujo multiagente: scoring, grafo, documento, validación y explicación.
6. Abrir el dashboard con filtros y ranking de riesgo.
7. Explicar un contrato concreto: score, señales, evidencias y limitaciones.

## Qué Evitar

- No digas que el sistema "detecta corrupción" de forma concluyente.
- No presentes modelos avanzados si aún son PoC.
- No sobrecargues la explicación con demasiadas librerías.
- No hables solo de tecnología: conecta siempre con el problema y el valor.
- No ocultes limitaciones; en este proyecto, reconocerlas suma credibilidad.
- No presentes los agentes como autónomos sin control: insiste en validación, trazabilidad y reglas.

## Resumen Final para Memorizar

ProcureWatch Analytics es mi TFM y consiste en construir un prototipo de analítica de riesgo para contratación pública española. Uso Python para limpiar y transformar datos, diseño red flags explicables basadas en literatura, aplico análisis de redes para detectar relaciones organismo-proveedor, exploro web scraping/NLP sobre documentos contractuales reutilizables y orquesto agentes con LangChain y LangGraph para coordinar análisis, validación y explicación. El proyecto está alineado con mi perfil de Data Analyst / Data & AI Consultant porque combina datos reales, KPIs, automatización, visualización, RAG, agentes y comunicación de insights, pero además me permite crecer hacia analítica avanzada, grafos, machine learning interpretable e IA generativa aplicada.
