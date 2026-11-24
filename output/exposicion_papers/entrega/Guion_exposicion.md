# Guion de exposición: cuatro papers y aportes a SiGAD

Duración orientativa: 45–60 minutos. Las diapositivas pueden exponerse por bloques.

## 1. Cómo comprender, dirigir y verificar el análisis de datos con LLM

- Cuatro estudios de interacción humano–IA
- Lectura crítica y aportes para SiGAD

Presentar el hilo de la exposición: los LLM pueden ejecutar análisis, pero el usuario necesita comprender las decisiones y comprobar sus consecuencias. Esta revisión conecta los cuatro artículos con el guiado contextual y adaptativo de SiGAD. Las aplicaciones a la tesis son propuestas propias, identificadas como tales.

## 2. Los cuatro papers responden preguntas diferentes

- Kazemitabaar: ¿cómo dividir el análisis para poder intervenir?
- LightVA: ¿cómo convertir un objetivo en tareas y visualizaciones?
- WaitGPT: ¿cómo visualizar y corregir operaciones del código?
- Gu: ¿cómo verifican los analistas lo que produce la IA?

Cada bloque cubre motivación, problema, objetivo, fundamento conceptual, propuesta y módulos, evaluación, resultados, limitaciones y trabajos futuros. Cuando un artículo no presenta una comparación experimental o un modelo cognitivo formal, se indica expresamente. El orden sigue la lista de la asesora.

## 3. Problema: el chat dificulta revisar decisiones intermedias

- Motivación: el análisis exige programación, estadística y conocimiento de los datos.
- Problema: respuestas extensas y supuestos implícitos dificultan verificar y corregir.
- Objetivo: comparar dos interfaces de descomposición con un asistente conversacional.

Título: Improving Steering and Verification in AI-Assisted Data Analysis with Interactive Task Decomposition. El estudio formativo con 15 participantes identifica dificultades para dirigir al agente y verificar sus resultados. Steering significa intervenir para que el sistema produzca el resultado deseado. Fuente: 2407.02651v2, introducción y sección 3, pp. 2–5 del PDF.

## 4. La descomposición crea momentos para reflexionar

- Stepwise: revisar supuestos y código para cada subobjetivo.
- Phasewise: revisar supuestos, plan y código de la tarea completa.
- Fundamento: descomposición, reflexión metacognitiva y compromiso temprano.
- El trabajo no estima el dominio de habilidades del usuario.

El artículo discute cómo los pasos pequeños pueden actuar como apoyo metacognitivo, y usa Cognitive Dimensions of Notations para analizar el compromiso prematuro. Esto es un fundamento para el diseño de interacción, no un modelo BKT ni una evaluación de aprendizaje. Phasewise no representa las fases PPDAC. Fuente: secciones 1, 4 y 7 de 2407.02651v2.

## 5. Phasewise separa supuestos, plan y código

- Supuestos: columnas, significado y salida esperada.
- Plan: pasos editables y acciones opcionales.
- Código: ejecución y revisión de variables intermedias.

Recorrer la figura de arriba hacia abajo. El usuario puede modificar los supuestos antes de generar el plan y cambiar el plan antes de ejecutar el código. La inspección de variables intermedias permite contrastar transformaciones. Las modificaciones pueden regenerar componentes posteriores. Fuente: sección 4.1 de 2407.02651v2.

## 6. Stepwise permite intervenir en cada subobjetivo

- Cada paso vincula supuestos, acciones, código y salida.
- El usuario revisa el paso antes de solicitar el siguiente.
- Conversaciones laterales: preguntar, generar código o consultar los datos.
- Las ramas conservan versiones previas de las modificaciones.

Explicar la diferencia con Phasewise: aquí los supuestos y el código se presentan por subobjetivo, no para toda la tarea de una vez. Ask Question explica código. Generate Code produce cambios. Run Side Query explora datos sin alterar el flujo principal. El versionado permite volver a alternativas anteriores. Fuente: secciones 4.1.3–4.1.7.

## 7. 18 participantes compararon las tres interfaces

- Tareas: seis problemas derivados de ARCADE, con datos modificados para exigir corrección.
- Línea base: asistente conversacional con código y supuestos no editables directamente.
- Diseño: medidas repetidas y orden contrabalanceado mediante cuadrado latino.
- Medidas: finalización, tiempo, pistas, escalas Likert y análisis de pensar en voz alta.

Todos los participantes utilizaron Stepwise, Phasewise y Conversational. Se asignaron dos tareas por condición, con un máximo de 15 minutos por tarea. Las tareas se probaron previamente para provocar fallos iniciales del agente. Por eso no es un benchmark general de exactitud del LLM. El análisis de escalas emplea Friedman y comparaciones Wilcoxon con corrección Bonferroni. Fuente: sección 5, pp. 9–11 del PDF.

## 8. Mejoró el control percibido y la facilidad de verificación

- Control percibido: Stepwise p=.001 y Phasewise p=.004 frente a la línea base.
- Las dos interfaces facilitaron la verificación y la intervención correctiva.
- El tiempo de finalización no mostró diferencias significativas.
- La facilidad percibida para dirigir a la IA tampoco difirió significativamente.

Interpretar con cuidado: el estudio respalda percepciones de control y verificación, no una mejora demostrada en aprendizaje. Se completaron 101 de 108 episodios. En 31 episodios el usuario declaró terminar con errores restantes y recibió una pista del investigador. El número de tareas incompletas fue demasiado pequeño para comparar estadísticamente. Fuente: sección 6.1–6.3 de 2407.02651v2.

## 9. La estructura ayuda, pero también exige más decisiones

- Conclusión: los supuestos editables y los pasos favorecen la revisión del análisis.
- Límites: tareas alteradas, uso breve y participantes con experiencia en programación.
- Problema técnico: un cambio anterior puede sobrescribir ediciones posteriores.
- Futuro: combinar interacción flexible y estructurada, mejorar propagación y estudiar uso prolongado.

No afirmar que Stepwise siempre supera a Phasewise. El artículo identifica preferencias y compromisos: la revisión paso a paso puede aumentar esfuerzo y retrasar la salida, mientras el plan completo puede exigir decisiones antes de conocer su impacto. Propone adaptarse al contexto y combinar modalidades. Fuente: secciones 7–9.

## 10. Aporte principal: hacer visibles las decisiones del proceso

- PPDAC: presentar decisiones y evidencias dentro de cada fase.
- Preprocesamiento: revisar el supuesto y la acción antes de transformar datos.
- Guiado: conservar oportunidades para que el estudiante explique su decisión.
- Evaluación: medir control y verificación junto con aprendizaje autónomo.

Esta diapositiva es interpretación para SiGAD. El paper respalda un diseño con puntos de revisión, pero no valida la política de ayuda ni el modelo BKT de la tesis. Un ejemplo sería pedir al estudiante que justifique qué hacer con los faltantes antes de ejecutar el tratamiento. Evitar equiparar la finalización asistida con dominio aprendido.

## 11. Problema: construir y usar análisis visual requiere mucho trabajo

- Motivación: los objetivos analíticos evolucionan al explorar los datos.
- Problema: generar un gráfico aislado ofrece poco apoyo para planificar un análisis complejo.
- Objetivo: conectar objetivos, tareas, visualizaciones y hallazgos mediante colaboración humano–agente.

Título: LightVA: Lightweight Visual Analytics with LLM Agent-Based Task Planning and Execution. Se utiliza la versión 2411.05651v2, que incluye el apéndice de pruebas del LLM. Lightweight alude a reducir el esfuerzo de desarrollo y uso de sistemas de análisis visual. Fuente: resumen e introducción.

## 12. El análisis progresa mediante tareas que pueden descomponerse

- Objetivo: intención analítica de alto nivel.
- Tarea: variables, tipo de análisis y métodos necesarios.
- Hallazgo: resultado estructurado que puede motivar nuevas tareas.
- Marco conceptual: planificación iterativa y colaboración de iniciativa mixta.

Se trata de un marco de trabajo de análisis visual, no de un modelo cognitivo validado del aprendiz. El sistema recomienda tareas, las ejecuta y decide con el usuario si necesita descomponerlas. Las subtareas pueden ser independientes mediante AND o secuenciales mediante DOWN. Fuente: sección III y sección IV de 2411.05651v2.

## 13. Planificador, ejecutor y controlador coordinan el análisis

- Planificador: recomienda y descompone tareas.
- Ejecutor: genera análisis, visualizaciones y hallazgos.
- Controlador: coordina la recursión y la finalización.

Leer la figura en tres zonas: recomendación, ejecución y descomposición. El historial conecta resultados previos con recomendaciones futuras. El ejecutor incorpora restricciones de consistencia visual. El controlador organiza las llamadas al planificador y ejecutor y los límites de descomposición. El usuario puede revisar la propuesta del agente. Fuente: sección IV-A.

## 14. Cuatro vistas conectan conversación, tareas y datos

- Chat: proponer tareas y revisar descomposición.
- Visualizaciones: explorar resultados e interacciones.
- Flujo y tabla: rastrear tareas y cobertura de los datos.

Identificar en la figura A, chat y control; B, visualización; C, flujo de tareas; D, tabla con data lens. El flujo permite controlar y revisar tareas, y las visualizaciones pueden combinarse en vistas vinculadas. Las respuestas al análisis alimentan nuevas recomendaciones. Fuente: sección IV-B.

## 15. La evidencia combina expertos y pruebas del modelo

- Caso de uso: mensajes del VAST Challenge y detección de eventos.
- Estudio: dos expertos en análisis visual y un experto de dominio.
- Datos adicionales: automóviles y ventas de Superstore.
- Comparación técnica: GPT-3.5-turbo y GPT-4-turbo en el apéndice B.

No hay un experimento de usuarios con asignación aleatoria contra otro sistema. La comparación con Tableau Ask Data es una discusión de capacidades, no una prueba controlada de superioridad. El apéndice B informa 160 resultados iniciales y reintentos para analizar fallos, reparación y tiempos. La descripción del número de tareas y su fórmula contiene inconsistencias internas, por lo que aquí se conserva la cifra de resultados reportada sin reconstruir un benchmark propio. Fuente: secciones V–VII y apéndice B.

## 16. La autorreparación resolvió parte de los fallos de generación

- 160 resultados iniciales en las pruebas técnicas.
- 44 presentaron errores en la primera ronda.
- 18 de esos errores se resolvieron en la segunda ronda.
- 26 permanecieron: ejecutar sin error tampoco garantiza validez analítica.

Las cifras corresponden al apéndice B y no al estudio con tres expertos. El paper clasifica errores por desconocimiento de datos, referencias a variables, serialización, transformación y sintaxis. Los expertos valoraron la descomposición y la reducción de trabajo manual, pero pidieron recomendaciones más pertinentes y explicaciones de los planes. Las últimas palabras de la diapositiva son una interpretación metodológica: un script ejecutable puede producir una conclusión incorrecta. Fuente: sección VI y apéndice B.

## 17. La planificación flexible necesita controles de calidad

- Conclusión: el marco integra planificación, ejecución y exploración visual.
- Límites: tres expertos, planes no siempre fiables y dificultades con tareas complejas.
- Futuro: ampliar evaluación, mejorar edición y versiones, y aportar conocimiento de dominio.
- También propone explorar personalización, caché y detección de errores factuales.

La comparación de esfuerzo del caso de uso es contextual: usa datos ya preprocesados y compara con un proyecto anterior. No debe presentarse como una mejora de velocidad general demostrada experimentalmente. El trabajo reconoce límites con faltantes, conocimiento de dominio y estabilidad del LLM. Fuente: secciones V y VII.

## 18. Aporte principal: separar responsabilidades de los componentes

- Distinguir recomendación, ejecución y control del flujo.
- Registrar el objetivo, las tareas y los resultados que motivan cada decisión.
- Revisar planes antes de aplicar operaciones de preprocesamiento.
- SiGAD añade una política pedagógica sustentada en evidencias del desempeño.

Esta es una propuesta para la tesis. El controlador recursivo de LightVA no equivale al motor que selecciona el grado de ayuda de SiGAD. BKT estima dominio y la política de asistencia utiliza esa evidencia. El LLM puede producir orientación dentro de restricciones explícitas. LightVA aporta separación funcional, no validación de esa adaptación pedagógica.

## 19. Problema: el código generado oculta la lógica del análisis

- Motivación: el usuario necesita supervisar cómo el agente transforma los datos.
- Problema: leer código extenso y corregir mediante nuevos prompts exige esfuerzo.
- Objetivo: mostrar y editar operaciones mediante una representación visual que crece durante la generación.

Título: WaitGPT: Monitoring and Steering Conversational LLM Agent in Data Analysis with On-the-Fly Code Visualization. El estudio formativo con ocho participantes motiva el diseño. La propuesta combina una representación estática de las operaciones con información dinámica de ejecución. Fuente: secciones 1 y 3 de 2408.01703v1.

## 20. La representación visual ofrece andamiaje para verificar

- Abstracción: centrar la atención en operaciones, parámetros y resultados.
- Estados: mostrar los datos antes y después de una transformación.
- Interacción: preguntar por una operación o corregir un parámetro local.
- El andamiaje visual no incluye un modelo de dominio del aprendiz.

El artículo usa explícitamente interactive visual scaffolding para describir la propuesta y formula cuatro consideraciones de diseño. Esto aproxima el trabajo al interés de SiGAD por apoyar la comprensión, pero su evaluación se centra en interacción y verificación, no en aprendizaje ni retirada progresiva de ayuda. Fuente: sección 3.3.

## 21. El sistema combina análisis de código y estados de ejecución

- Analizar: extraer operaciones del código.
- Ejecutar: recuperar estados de las tablas.
- Combinar: crear primitivas visuales interactivas.

El analizador estático procesa el árbol de sintaxis abstracta e identifica operaciones. Antes de ejecutar, el sistema separa cadenas de métodos e inserta instrucciones para recuperar estados intermedios. El renderizador vincula operaciones y estados con nodos visuales. La interfaz se implementa con React y Monaco, y el backend usa Flask. Fuente: sección 6.

## 22. El diagrama permite inspeccionar y corregir una operación

- Nodos de tabla: datos y tamaño intermedio.
- Nodos de operación: transformación y parámetros.
- Interacción: consultar, editar y volver al código.

Recorrer las zonas de la interfaz: la conversación y el código permanecen accesibles; el diagrama agrega operaciones y anima el paso de datos. Al seleccionar una tabla se accede a su contenido. El usuario puede formular preguntas contextuales o modificar parámetros del nodo para actualizar el código. Fuente: secciones 4 y 5.

## 23. 12 participantes compararon WaitGPT con una interfaz sin diagrama

- Datos: Employee y Flight, más una exploración libre con datos sintéticos.
- Tareas: seis consultas A y cuatro B, basadas en ARCADE y Text2Analysis.
- Línea base: misma apariencia, código comentado y resaltado de sintaxis, sin diagrama.
- Medidas: juicio de corrección, tiempo, NASA-TLX, utilidad e entrevistas.

Diseño intraparticipante contrabalanceado. Las primeras respuestas se fijaron con prompts preparados para dar contenido inicial idéntico. Los participantes eran estudiantes de posgrado con distintas especialidades, generalmente familiarizados con análisis y Pandas. No representar la muestra como personas sin experiencia en datos. Fuente: sección 7.1–7.3.

## 24. Mejoró la valoración de utilidad, con resultados variables por tarea

- NASA-TLX: el artículo reporta menor demanda percibida con WaitGPT.
- 10 de 12 participantes reportaron más confianza en la corrección.
- A1: éxito de 83% con WaitGPT y 33% con la línea base.
- A4: éxito de 67% y 83%, respectivamente.

Los porcentajes proceden de la tabla 2 y cada tarea tiene seis personas por condición. Son ejemplos descriptivos, no una ventaja significativa universal. El tiempo varía por tarea y muestra desviaciones altas. Las escalas de utilidad favorecen WaitGPT, pero confianza y exactitud son variables distintas. Fuente: sección 7.4 y tabla 2, pp. 10–11 del PDF.

## 25. Ver operaciones ayuda a supervisar el análisis

- Conclusión: el diagrama facilita comprender y ajustar el código del agente.
- Límites: muestra pequeña, posibles sesgos de preferencia y cobertura técnica limitada.
- Futuro: ampliar operaciones y lenguajes, conectar representaciones y mejorar interacción.
- La evaluación no demuestra retención de conocimientos ni transferencia.

La cobertura de operaciones del parser limita lo que puede visualizarse. Los autores también señalan que pedir ver la representación puede alterar el comportamiento natural y que el diseño de la línea base puede influir en preferencias. La última afirmación delimita el alcance de la evaluación, no constituye una limitación formulada necesariamente por los autores. Fuente: secciones 8 y 9.

## 26. Aporte principal: mostrar la consecuencia de cada transformación

- Faltantes: visualizar qué filas o columnas afecta una decisión.
- Atípicos: distinguir candidatos detectados de errores confirmados.
- Verificación: comparar datos y resúmenes antes y después.
- Guiado adaptativo: variar la pista y conservar la posibilidad de inspeccionar.

Ejemplo propuesto: antes de imputar, el estudiante identifica la distribución de faltantes y explica si el método corresponde al contexto. Después comprueba registros afectados y cambios en la distribución. El grado de apoyo lo decide la política de SiGAD, no el diagrama. La capacidad de explicar una decisión sin ayuda requiere una evaluación adicional.

## 27. Problema: un análisis convincente puede ser incorrecto

- Motivación: la IA puede interpretar mal la intención, los datos o los cálculos.
- Problema: todavía se comprende poco cómo los analistas verifican sus respuestas.
- Objetivo: observar estrategias de comprensión y verificación con distintos artefactos.

Título: How Do Analysts Understand and Verify AI-Assisted Data Analyses? Se utiliza 2309.10947v2. Es un estudio empírico de comportamientos, no una propuesta de automatización superior a otros sistemas. El prototipo es una sonda de diseño para observar prácticas. Fuente: resumen e introducción.

## 28. Verificar exige relacionar procedimiento y datos

- Procedimiento: ¿qué hizo la IA?
- Datos: ¿qué significan y qué muestran?
- El analista contrasta ambos para juzgar el resultado.

La figura contrasta análisis manual, análisis con código y análisis asistido por IA. El trabajo encuadra la verificación como parte de la construcción de sentido o sensemaking. Los comportamientos orientados al procedimiento y a los datos son categorías analíticas derivadas del estudio. No son estados de conocimiento ni una secuencia obligatoria. Fuente: introducción y sección 6.

## 29. La sonda permite contrastar explicaciones, código y tablas

- Respuesta de IA: explicación en lenguaje natural, código y comentarios.
- Datos originales e intermedios: tablas filtrables y ordenables.
- Resúmenes: distribuciones, estadísticas e información de columnas.
- Navegación coordinada: relacionar cada tabla con su operación.

Esta es una descripción funcional de la sonda, no una arquitectura de agentes. La interfaz separa artefactos del procedimiento y artefactos de datos, pero permite usarlos conjuntamente. Los investigadores restringen la conversación posterior para centrarse en verificar la respuesta existente. Fuente: sección 4.1–4.2 de 2309.10947v2.

## 30. El usuario puede inspeccionar evidencia intermedia

- Izquierda: intención, explicación y código.
- Derecha: datos originales y resultados intermedios.
- La navegación vincula procedimientos y tablas.

Mostrar que la interfaz ofrece evidencia que el usuario puede consultar, no solamente una explicación persuasiva del LLM. Las tablas incorporan operaciones habituales y resúmenes. La representación de transformaciones atómicas permite revisar cómo se produjo un resultado. Fuente: sección 4.2 y figura 2.

## 31. 22 analistas verificaron respuestas preparadas

- Tareas: diez consultas principales y un tutorial, derivados de ARCADE.
- Respuestas: ejemplos correctos y errores de interpretación o cálculo.
- Método: estudio cualitativo, pensar en voz alta, grabaciones y entrevistas.
- Línea base: no aplica una comparación experimental entre sistemas.

Se reclutaron profesionales de una empresa de software con diversidad de herramientas y experiencia. Los participantes evaluaron consultas y respuestas que no habían redactado. El análisis codifica comportamientos y artefactos de verificación, y reconstruye los flujos. Las medidas de frecuencia describen patrones, no un efecto causal de la interfaz. Fuente: secciones 4.3 y 5, tabla 1.

## 32. Los analistas alternan entre revisar la lógica y revisar los datos

- 52 flujos observados, 39 de ellos con errores en el análisis presentado.
- Los comportamientos de datos y procedimiento se apoyan mutuamente.
- La experiencia con operaciones de datos influye en cómo se verifica.

La cifra 39 no significa 39 errores descubiertos ni una tasa de detección. Describe los flujos asociados con análisis que contenían errores. Los analistas pasan de entender a notar una sospecha y confirmar o descartar el fallo. Las tablas intermedias pueden apoyar la revisión del código y la explicación puede orientar la exploración de datos. Fuente: sección 6 y pie de figura 4.

## 33. La verificación necesita más que una explicación del LLM

- Conclusión: ofrecer datos, procedimientos y supuestos a distintas escalas ayuda a verificar.
- Límites: tareas centradas en manipulación y exploración, con consultas de terceros.
- Futuro: estudiar análisis estadístico y modelado, y permitir interacción más completa.
- También propone apoyar estrategias y pruebas de verificación.

El trabajo destaca conocer operaciones comunes, formular expectativas y usar comprobaciones de plausibilidad. La muestra y el contexto limitan generalización. No ofrece evidencia de que una explicación por sí sola garantice corrección o aprendizaje. Los autores proponen comunicar supuestos y conectar artefactos. Fuente: sección 7.

## 34. Aporte principal: convertir la verificación en una actividad del estudiante

- Pedir una expectativa antes de observar el resultado.
- Solicitar evidencia para aceptar o rechazar una transformación.
- Distinguir explicaciones generadas de valores calculados por el backend.
- Evaluar si el estudiante detecta y explica errores sin ayuda.

Esta aplicación es una interpretación para SiGAD. Puede operacionalizar alfabetización mediante tareas donde el estudiante explique una operación, identifique un supuesto y compruebe una consecuencia. Una rúbrica y su validez necesitan evaluación propia. El paper no valida BKT ni demuestra que usar la sonda aumente la alfabetización.

## 35. Cada trabajo aporta una pieza distinta a SiGAD



La tabla sintetiza el análisis propio a partir de los cuatro PDF. Kazemitabaar es prioritario para puntos de intervención. Gu fundamenta la importancia de verificación y conocimiento de datos. WaitGPT ofrece mecanismos visuales. LightVA aporta separación funcional y planificación. Ninguna de estas evaluaciones valida la política pedagógica específica de SiGAD.

## 36. Una tarea de faltantes conecta los cuatro aportes

- Diagnóstico: explorar distribución y contexto de los faltantes.
- Decisión: explicar el supuesto y elegir un tratamiento.
- Ejecución: mostrar la operación y los registros afectados.
- Verificación: contrastar resultados y justificar si el tratamiento fue adecuado.

Flujo conceptual propuesto para la tarea que pidió la asesora. De Kazemitabaar se toman puntos de revisión. De LightVA, responsabilidades del plan y ejecución. De WaitGPT, visualización de operaciones. De Gu, contraste entre procedimiento y datos. El alcance de la tarea y los tratamientos permitidos dependen del conjunto de datos. SiGAD debe recoger evidencia propia del estudiante y no atribuirle una solución prescrita.

## 37. SiGAD debe evaluar comprensión, autonomía y calidad del guiado

- Los cuatro trabajos ayudan a diseñar interacción, planificación y verificación.
- Sus estudios ofrecen evidencias distintas y no son intercambiables.
- La tesis debe comprobar aprendizaje con medidas iniciales y un grupo de comparación.
- La consistencia del LLM requiere repeticiones controladas y revisión de corrección.

Conectar con los objetivos acordados en propuesta_sigad_revisada.md. Calidad del guiado: criterios seleccionados de GUIAVisWeb. Alfabetización: evaluación de aprendizaje con medida inicial y grupo de comparación. Consistencia: repetir contextos y comparar campos estructurados, distinguiendo estabilidad de corrección. Esta revisión no basta para afirmar que ningún trabajo previo estudia adaptación o aprendizaje en todo el campo.

## 38. Artículos utilizados en la exposición

- Kazemitabaar et al. (2024). Improving Steering and Verification… UIST. arXiv:2407.02651v2.
- Zhao et al. LightVA: Lightweight Visual Analytics… TVCG. arXiv:2411.05651v2.
- Xie et al. (2024). WaitGPT: Monitoring and Steering… UIST. arXiv:2408.01703v1.
- Gu et al. (2024). How Do Analysts Understand and Verify… CHI. arXiv:2309.10947v2.

Fuentes primarias: los cuatro PDF aportados por el usuario. DOI: Kazemitabaar, 10.1145/3654777.3676345. LightVA, 10.1109/TVCG.2024.3496112. Los números de página de la presentación corresponden a la posición de la página en el PDF aportado. Las figuras se reproducen con atribución a sus autores. Las aplicaciones a SiGAD son síntesis propias. Enlaces: https://arxiv.org/abs/2407.02651 ; https://arxiv.org/abs/2411.05651 ; https://arxiv.org/abs/2408.01703 ; https://arxiv.org/abs/2309.10947 .