# Guion ampliado: exposición de cuatro papers

Ocho diapositivas, dos por artículo. Duración orientativa: 5–7 minutos por artículo, ajustable al tiempo disponible. Las notas siguientes también están incorporadas en el PowerPoint.

## 1. Improving Steering and Verification in AI-Assisted Data Analysis with Interactive Task Decomposition

### Diapositiva 1: problema, propuesta y arquitectura

IDEA CENTRAL PARA ABRIR
Este paper investiga cómo dar al usuario oportunidades concretas para dirigir y verificar un análisis generado con IA. No busca solamente que el LLM produzca una respuesta más rápido.

PROBLEMA Y MOTIVACIÓN
El análisis exige combinar programación, estadística y conocimiento de los datos. En un chat, la IA puede resolver toda la consulta antes de que la persona intervenga. Si interpreta mal una columna, el error puede propagarse por toda la solución. El estudio formativo con 15 participantes y ChatGPT con Noteable identifica dificultades de seguimiento, verificación y corrección.

CÓMO EXPLICAR LA FIGURA
Leer las tres columnas de izquierda a derecha. Conversational produce supuestos, código y salida para toda la tarea; el usuario corrige mediante otra consulta. Phasewise primero hace editables los supuestos, luego un plan de ejecución y finalmente el código. Stepwise presenta pares de supuestos y código para cada subobjetivo y permite revisar antes de avanzar. Los nombres de estas fases describen la solución computacional y no corresponden a PPDAC.

FUNCIONES COMPLEMENTARIAS
La inspección de variables intermedias ayuda a comprobar qué produjo una operación. Ask Question explica el código. Generate Code permite pedir cambios. Run Side Query explora los datos sin alterar el flujo principal. El versionado mediante ramas conserva alternativas de edición.

FUNDAMENTO COGNITIVO
La descomposición divide información y crea momentos de reflexión. El artículo discute demandas metacognitivas y compromiso prematuro mediante Cognitive Dimensions of Notations. Revisar muchos pasos puede aumentar esfuerzo, mientras aprobar un plan global puede exigir decisiones cuyo efecto todavía no se conoce. No propone un modelo de habilidades como BKT.

EJEMPLO ILUSTRATIVO PROPIO
Si una columna contiene categorías separadas por comas, el usuario puede revisar el supuesto de separación antes de agrupar y contar. El ejemplo ilustra el mecanismo, no añade un resultado experimental.

TRANSICIÓN
La pregunta siguiente es si estas formas de control cambian el desempeño o principalmente la experiencia del usuario.
Fuente: 2407.02651v2, secciones 1, 3, 4 y 7.

### Diapositiva 2: evaluación, hallazgos y discusión

CÓMO SE EVALUÓ
Los 18 participantes usaron las tres interfaces en un diseño intraparticipante. Cada uno realizó dos tareas por condición. El orden se contrabalanceó mediante cuadrado latino. Las tareas se derivaron de ARCADE y se modificaron deliberadamente para exigir que la persona detectara y corrigiera fallos iniciales del agente. Por tanto, el estudio no estima la exactitud general de los LLM sobre ARCADE.

MÉTRICAS Y ANÁLISIS
Se observó si la solución quedaba correcta dentro de 15 minutos, el tiempo, las pistas del investigador, las percepciones mediante Likert y el comportamiento de pensar en voz alta. Las comparaciones de escalas usaron Friedman y después Wilcoxon con Bonferroni. Una p pequeña respalda una diferencia bajo el análisis realizado, pero no informa por sí sola de su magnitud o relevancia práctica.

QUÉ RESULTÓ
Los usuarios reportaron mayor control con Stepwise y Phasewise frente al chat. También percibieron más facilidad para verificar y corregir. No hubo diferencia significativa en tiempo, en número de pistas ni en facilidad percibida para dirigir la IA. De 108 episodios, 101 terminaron correctamente. En 31, el usuario declaró terminar cuando todavía existían problemas y el investigador tuvo que señalar el problema restante.

INTERPRETACIÓN
La estructura mejora aspectos percibidos de la interacción, pero no permite afirmar que mejora todas las medidas objetivas. Tampoco demuestra que la persona haya aprendido a analizar de manera autónoma.

LÍMITES Y FUTURO
Las tareas alteradas garantizan oportunidades de intervención, pero reducen naturalidad. Los participantes tenían experiencia con Python y el uso fue breve. El sistema puede perder ediciones posteriores cuando regenera componentes. Los autores proponen combinar flexibilidad y estructura y estudiar experiencias prolongadas.

RELACIÓN CON SiGAD
Se pueden tomar puntos de revisión donde el estudiante justifique supuestos y decisiones. La política adaptativa y el aprendizaje deben evaluarse por separado. El paper puede orientar una condición comparativa de interacción, pero no basta para seleccionar una línea base pedagógica definitiva.

PREGUNTA POSIBLE
¿Stepwise es mejor que Phasewise? No universalmente. El estudio identifica ventajas y preferencias diferentes. Stepwise distribuye la revisión, mientras Phasewise facilita examinar la estrategia completa.
Fuente: 2407.02651v2, secciones 5–8.

## 2. LightVA: Lightweight Visual Analytics with LLM Agent-Based Task Planning and Execution

### Diapositiva 3: problema, propuesta y arquitectura

IDEA CENTRAL PARA ABRIR
LightVA intenta reducir el trabajo necesario para construir y utilizar un sistema de análisis visual. Lightweight se refiere al esfuerzo de desarrollo y uso, no a que utilice un modelo pequeño.

PROBLEMA
Un objetivo como identificar eventos de riesgo no corresponde a un único gráfico. Puede requerir analizar tiempo, localización, categorías y relaciones. Además, un hallazgo puede cambiar el siguiente paso. El trabajo intenta integrar esa planificación con generación de visualizaciones e interacción.

CÓMO LEER LA ARQUITECTURA
La zona izquierda recibe el objetivo y los datos y recomienda tareas. El historial guarda tareas exploradas y resultados para recomendar acciones adicionales o revisar tareas pendientes. La zona central ejecuta tareas y genera visualizaciones y hallazgos con restricciones de color, interacción y composición. La zona derecha valora si hace falta descomponer y produce subtareas. El controlador coordina el recorrido y el retorno de resultados.

MÓDULOS
El planificador reúne recomendación y descomposición. El ejecutor produce código de análisis, visualizaciones y hallazgos. El controlador organiza las llamadas y la recursión. AND indica subtareas independientes que pueden ejecutarse en paralelo. DOWN representa dependencia y ejecución secuencial. El límite de profundidad evita descomposición indefinida.

INTERFAZ
Chat view permite conversar y revisar planes. Visualization view muestra vistas e interacciones. Task flow view representa el árbol y progreso de tareas. Data table view incorpora una lente para revisar los datos explorados. El usuario puede elegir tareas y corregir decisiones.

MODELO CONCEPTUAL
Es un marco de análisis visual de iniciativa mixta. No modela el conocimiento del estudiante. La adaptación a resultados de una tarea no equivale a adaptar la ayuda pedagógica según habilidades.

EJEMPLO DEL CASO DE USO
En mensajes de VAST Challenge se exploran frecuencia de palabras, sentimiento y distribución espacial. Los resultados llevan a descomponer análisis espacial en tareas adicionales y a combinar vistas para investigar eventos.
Fuente: 2411.05651v2, secciones III–V.

### Diapositiva 4: evaluación, hallazgos y discusión

TIPOS DE EVIDENCIA
Separar el caso de uso, el estudio con expertos y las pruebas técnicas del apéndice. No son tres réplicas del mismo experimento ni permiten la misma conclusión.

ESTUDIO CON EXPERTOS
Participan dos expertos en análisis visual y uno de dominio. Se presenta el sistema, se permite explorar pensando en voz alta y se recogen comentarios. Los datos incluyen automóviles y ventas de Superstore. Los expertos valoran la reducción de trabajo manual y la descomposición, pero señalan que las tareas deben explicarse y no siempre son fiables o suficientemente focalizadas.

LÍNEA BASE
La discusión de capacidades respecto a Tableau Ask Data no es un experimento controlado contra Tableau. La comparación de tiempo con un proyecto previo de VAST es contextual y no demuestra una ganancia general de velocidad. En el caso se cargan datos ya preprocesados.

PRUEBAS DEL LLM
El apéndice B compara GPT-3.5-turbo y GPT-4-turbo mediante generación de código y hallazgos. Reporta 160 resultados iniciales, 44 con error. Se reintenta con mensajes de error: 18 se reparan y 26 persisten. Son fallos de ejecución o generación clasificados por los autores. No son 160 usuarios ni 160 tareas de aprendizaje. La explicación del número de tareas y su fórmula presenta inconsistencias internas, así que conviene referirse a resultados iniciales reportados.

QUÉ SIGNIFICAN LAS MÉTRICAS
Reducir errores de ejecución mide robustez técnica. No certifica que el método elegido sea apropiado ni que la conclusión sea válida. El propio paper reconoce problemas factuales, tareas complejas, faltantes y conocimiento de dominio.

CONCLUSIÓN Y TRABAJOS FUTUROS
El aporte principal es integrar planificación y ejecución con revisión humana. Para generalizar harían falta más participantes y comparaciones controladas. El trabajo propone mejorar edición y versiones, incluir conocimiento de dominio, explorar caché, personalización y controles de errores.

RELACIÓN CON SiGAD
La arquitectura ayuda a definir responsabilidades y trazabilidad. SiGAD necesita además evaluar evidencias del estudiante, estimar dominio y decidir la ayuda de forma explícita. El controlador de LightVA coordina tareas; no valida esa política pedagógica.

PREGUNTA POSIBLE
¿LightVA prepara automáticamente todos los datos? No. El caso reconoce que el data wrangling complejo todavía exige intervención humana.
Fuente: 2411.05651v2, secciones V–VII y apéndice B.

## 3. WaitGPT: Monitoring and Steering Conversational LLM Agent in Data Analysis with On-the-Fly Code Visualization

### Diapositiva 5: problema, propuesta y arquitectura

IDEA CENTRAL PARA ABRIR
WaitGPT cambia la representación del código para que una persona pueda seguir las operaciones del análisis y corregir un paso sin reiniciar toda la conversación.

MOTIVACIÓN
El código puede ejecutar sin errores y aun así agrupar, filtrar o agregar incorrectamente. Leer toda la sintaxis no siempre deja ver la lógica. El estudio formativo con ocho participantes informa cuatro consideraciones de diseño: abstraer operaciones, visualizar datos y estados, permitir preguntas y modificaciones locales e integrar el diagrama en el chat.

CÓMO LEER LA FIGURA
User Instruction produce una respuesta con código, salida y análisis. Parse identifica operaciones y sus parámetros. Execute obtiene estados de tablas. Combine asocia la estructura estática con información dinámica y produce primitivas visuales. El usuario puede inspeccionar y modificar la representación.

IMPLEMENTACIÓN
El sistema analiza el árbol de sintaxis abstracta o AST del código. Identifica variables tabulares y operaciones como cargar, seleccionar, filtrar, ordenar, transformar, agrupar, agregar, unir y visualizar. Antes de ejecutar, separa cadenas de métodos e inserta instrucciones para recuperar número de filas, columnas y nombres. Después vincula esos datos con los nodos del diagrama.

REPRESENTACIÓN E INTERACCIÓN
Un nodo de tabla representa un dataframe. Un nodo de operación muestra el tipo y sus parámetros. Un nodo de resultado representa valores o visualizaciones. Los enlaces indican entradas, asignaciones o secuencias de transformación. Los glifos de tablas permiten notar cambios de tamaño. El usuario puede ver tablas intermedias, volver al código, preguntar por una operación y editar parámetros.

FUNDAMENTO COGNITIVO
El trabajo denomina este mecanismo andamiaje visual interactivo. La abstracción ayuda a enfocar la lógica y relacionar una operación con su efecto. No estima habilidades ni retira apoyo según conocimiento, como se propone para SiGAD.

EJEMPLO ILUSTRATIVO PROPIO
Si se elimina una fila por tener un faltante, mostrar cuántos registros quedan permite comprobar el alcance de la operación. Que el tamaño sea esperable no basta: también hay que revisar si el criterio de eliminación corresponde al objetivo.
Fuente: 2408.01703v1, secciones 3, 5 y 6.

### Diapositiva 6: evaluación, hallazgos y discusión

DISEÑO DE LA EVALUACIÓN
Doce estudiantes de posgrado con distintas especialidades comparan WaitGPT y una versión sin diagrama. Se conserva apariencia, comentarios del código y resaltado de sintaxis. El diseño intraparticipante contrabalanceado busca reducir diferencias debidas a orden. Las primeras respuestas se preparan para que el contenido inicial sea comparable. Los participantes conocen análisis de datos y Pandas en distintos grados, por lo que no representan necesariamente principiantes.

TAREAS
Hay seis consultas sobre Employee y cuatro sobre Flight, más una exploración libre con un conjunto sintético. Algunas respuestas tienen fallos y otras son correctas. Cada tarea de las dos primeras series tiene seis participantes por condición.

MÉTRICAS
Se registra si el usuario juzga correctamente el análisis, cuánto tarda en notar un posible problema y tomar una decisión, y si inspecciona datos o código. NASA-TLX mide carga de trabajo percibida, no conocimiento adquirido. El cuestionario de utilidad usa siete puntos. Las entrevistas ayudan a explicar comportamientos y preferencias.

RESULTADOS
El artículo reporta menor demanda percibida con WaitGPT y mejores valoraciones de utilidad. Diez de doce participantes indican más confianza en la corrección. La tabla 2 muestra variaciones por tarea: en A1, ordenar texto incorrectamente, el éxito es 83% frente a 33%; en A4, omitir un filtro sobre empleados activos, es 67% frente a 83%. Estos ejemplos son descriptivos y no justifican afirmar superioridad en todas las tareas. Tampoco se demuestra una reducción uniforme del tiempo.

INTERPRETACIÓN
La representación visual puede ayudar a seguir la lógica, pero el usuario todavía tiene que conocer el significado de los datos y revisar condiciones omitidas. Aumentar confianza sin verificar exactitud puede ser insuficiente.

LÍMITES Y FUTURO
La muestra es pequeña. La cobertura del analizador limita las operaciones representables. Los participantes reciben indicaciones para mirar la representación, lo que puede influir en su uso. Se propone ampliar cobertura e interacción y conectar más estrechamente representaciones.

RELACIÓN CON SiGAD
Es especialmente útil para diseñar la visualización del antes y después del preprocesamiento. La tesis tendría que comprobar además si el estudiante puede explicar el tratamiento y verificar su efecto sin ayuda.

PREGUNTA POSIBLE
¿Es visualización del resultado final? No solamente: representa operaciones del código y estados intermedios, que permiten revisar el procedimiento.
Fuente: 2408.01703v1, sección 7, tabla 2 y sección 8.

## 4. How Do Analysts Understand and Verify AI-Assisted Data Analyses?

### Diapositiva 7: problema, propuesta y arquitectura

IDEA CENTRAL PARA ABRIR
Este artículo investiga lo que hacen los analistas cuando reciben una respuesta de IA. El aporte principal es conocimiento sobre comportamientos de verificación. La interfaz se usa como sonda para observarlos, no como un sistema cuya superioridad se quiera demostrar.

PROBLEMA
Un script puede ejecutar y producir una tabla plausible, pero responder una pregunta distinta o calcular algo incorrecto. La verificación requiere relacionar intención, procedimiento y datos. El estudio se pregunta qué patrones aparecen, qué artefactos ayudan y cómo influye la experiencia previa.

CÓMO EXPLICAR LA FIGURA
En la izquierda se muestran la consulta, explicación en lenguaje natural, código y comentarios. A la derecha están las tablas originales e intermedias, estadísticas y distribuciones. El usuario puede filtrar, ordenar e inspeccionar. La coordinación de navegación permite conectar una operación con la tabla que produce.

MODELO CONCEPTUAL
Los comportamientos orientados al procedimiento preguntan qué hace la IA y si su lógica es adecuada. Los orientados a datos preguntan si los valores, relaciones y resultados tienen sentido. El analista puede usar una tabla para revisar código o leer una explicación para decidir qué datos inspeccionar. No son dos perfiles excluyentes de personas ni una secuencia rígida.

SUPUESTOS
Conocer el significado de una columna es tan importante como leer la función que la utiliza. Una columna con 2021 en el nombre, por ejemplo, puede ser una bandera y no un ranking. El estudio incluye ese tipo de confusiones.

EJEMPLO DEL ESTUDIO
En una consulta sobre vuelos, el análisis puede contar filas de reservas en lugar de vuelos únicos. El código puede ser sintácticamente válido. Para verificar se necesita entender la unidad de análisis y contrastar identificadores, agrupación y resultado.

DIFERENCIA CON LOS OTROS PAPERS
Aquí la pregunta es cómo verifica la persona cuando dispone de evidencia. Kazemitabaar y WaitGPT comparan formas de interacción. LightVA organiza planificación y ejecución. Gu ayuda a justificar qué evidencia debe estar disponible y qué competencia necesita la persona.
Fuente: 2309.10947v2, secciones 1, 4 y 6.

### Diapositiva 8: evaluación, hallazgos y discusión

DISEÑO DEL ESTUDIO
Se reclutan 22 analistas profesionales con diversidad de experiencia y herramientas. Las sesiones remotas duran aproximadamente una hora: tutorial, actividad con tareas y entrevista. El escenario plantea que un tercero formuló la consulta y la IA respondió. El participante juzga si la respuesta resuelve correctamente el problema. Esto evita estudiar formulación de prompts, pero limita el realismo de un flujo completo propio.

DATOS Y PROCEDIMIENTO
Las tareas proceden de ARCADE e incluyen datos de compras, vuelos, hoteles y contenido audiovisual, entre otros. Hay diez consultas principales y un tutorial. Las respuestas incluyen casos correctos y fallos de intención, interpretación de columnas o cálculo. No existe una condición experimental comparativa para afirmar que la interfaz mejora el desempeño frente a otro sistema.

ANÁLISIS
Se usan grabaciones, pensar en voz alta, confirmación por tarea y entrevistas. Los investigadores reconstruyen flujos desde el inicio de la verificación hasta confirmar o rechazar que hay un error. Codifican qué artefactos se usan y si la intención principal es revisar datos o procedimiento. Notice registra una sospecha y Confirm la conclusión sobre el error.

HALLAZGOS
Se observan 52 flujos, 39 asociados a análisis que contenían errores. La cifra no significa que se detectaron 39 errores. Dieciocho de 22 participantes siguen parte del procedimiento de IA en algún momento, en 44 de 52 flujos. Los artefactos se usan conjuntamente: datos intermedios apoyan la revisión de pasos y las explicaciones orientan búsquedas en los datos. La experiencia con operaciones y herramientas influye en la forma de comprobar resultados.

CONCLUSIÓN
Una explicación del LLM es una fuente que también debe verificarse. Disponer de tablas, operaciones y supuestos permite contrastar evidencia. La familiaridad con operaciones comunes puede ayudar incluso cuando el usuario no domina Python.

LÍMITES Y FUTURO
Las tareas se centran en manipulación y exploración. Los participantes no eligen el problema ni redactan la consulta y la interacción posterior está restringida. Se propone estudiar tareas estadísticas y de modelado, flujos más completos, comunicación de supuestos y apoyo a estrategias o pruebas de verificación.

RELACIÓN CON SiGAD
Una actividad posible es pedir al estudiante una expectativa antes de ejecutar, luego una comprobación y una justificación. La tesis debe evaluar si puede hacerlo sin asistencia. Esa tarea puede aportar evidencia a una rúbrica, pero el paper no valida la rúbrica ni BKT.

PREGUNTA POSIBLE
¿El paper demuestra que el prototipo enseña alfabetización? No. Describe prácticas de analistas y fundamenta implicaciones de diseño; el aprendizaje exige otro estudio.
Fuente: 2309.10947v2, secciones 5–7, tabla 1 y figura 4.

## Vocabulario para la exposición

- **Steering:** dirigir o corregir las acciones del agente.
- **Verificación:** comprobar si el procedimiento y los resultados responden al objetivo.
- **Benchmark:** conjunto de tareas y datos de referencia. Usar tareas derivadas de un benchmark no equivale a ejecutar su evaluación estándar completa.
- **Línea base:** condición o método con el que se compara una propuesta. No todos los trabajos tienen una.
- **Diseño intraparticipante:** cada persona usa las condiciones comparadas.
- **Contrabalanceo:** variar el orden para reducir efectos de práctica y fatiga.
- **AST:** representación estructural del código que permite identificar operaciones.
- **NASA-TLX:** cuestionario de carga de trabajo percibida.
- **Andamiaje:** apoyo para realizar una actividad. El apoyo visual no implica por sí mismo adaptación pedagógica.
- **Sensemaking:** construcción de una comprensión de los datos y del procedimiento mediante exploración y contraste.

## Referencias primarias

- Kazemitabaar et al.: https://arxiv.org/abs/2407.02651
- Zhao et al.: https://arxiv.org/abs/2411.05651
- Xie et al.: https://arxiv.org/abs/2408.01703
- Gu et al.: https://arxiv.org/abs/2309.10947
