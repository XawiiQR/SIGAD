# Fundamentación del método — para sustentar con la asesora

## 1. El problema, en dos vacíos (no uno)

**Vacío de alcance.** Los sistemas de *guidance* existentes (GuidedStats, VIZTA) acompañan una sola fase puntual del análisis —un procedimiento estadístico o la lectura de un gráfico ya construido— y no cubren el ciclo completo desde la formulación de la pregunta hasta la interpretación final.

**Vacío de fundamento.** Los marcos de *guidance* que sí son transversales y técnicamente sólidos, como el de Ceneda et al. (2016), no están fundamentados en teoría del aprendizaje. Explican *qué tipo* de ayuda dar, pero no *por qué* ni *cuándo* debería graduarse esa ayuda para fortalecer la competencia del usuario, en lugar de solo resolver su tarea inmediata.

Tu tesis ataca los dos vacíos a la vez: cubre el ciclo completo (PPDAC) y fundamenta pedagógicamente cómo se gradúa el guidance en cada fase.

---

## 2. El método: tres pilares teóricos

### Pilar 1 — Grados de guiado en Visualización Analítica
**Ceneda, D., Gschwandtner, T., May, T., Miksch, S., Schulz, H.-J., Streit, M., & Tominski, C. (2016).** *Characterizing Guidance in Visual Analytics*. IEEE Transactions on Visualization and Computer Graphics, 23(1), 111–120.

Aporta el **qué tipo de ayuda**: tres grados de intensidad —**Orientar** (pistas visuales para reconstruir el mapa mental, sin señalar la solución), **Dirigir** (mostrar un conjunto de alternativas para que el usuario elija) y **Prescribir** (el sistema decide y ejecuta la acción). No es una secuencia obligatoria: el diseñador ajusta el grado según la brecha detectada. El modelo solo activa un grado cuando detecta una **brecha de conocimiento**; si no hay brecha, no hay guiado — este "estado cero" ya está implícito en el propio marco de Ceneda.

### Pilar 2 — Andamiaje instruccional y Zona de Desarrollo Próximo
**Vygotsky, L.S. (1978).** *Mind in Society: The Development of Higher Psychological Processes*. Harvard University Press.
**Wood, D.J., Bruner, J.S., & Ross, G. (1976).** *The Role of Tutoring in Problem Solving*. Journal of Child Psychology and Psychiatry, 17(2), 89–100.

Aporta el **por qué y cuándo** escalar o retirar la ayuda, que es justo lo que le falta a Ceneda. Vygotsky define la Zona de Desarrollo Próximo: la distancia entre lo que el aprendiz puede hacer solo y lo que logra con ayuda de alguien más capaz — el aprendizaje ocurre en esa franja. Wood, Bruner & Ross convierten esa idea en seis funciones de andamiaje observables: *recruitment* (enganchar al aprendiz con el material de la tarea), reducción de grados de libertad (simplificar la tarea a un tamaño manejable), mantenimiento de la dirección, marcar características críticas, control de la frustración y demostración. Su conclusión central: el apoyo debe **retirarse progresivamente** (*fading*) conforme el aprendiz gana competencia.

### Pilar 3 — Justificación del intento autónomo inicial
**Kalyuga, S., Ayres, P., Chandler, P., & Sweller, J. (2003).** *The Expertise Reversal Effect*. Educational Psychologist, 38(1), 23–31.
**Kapur, M. (2008).** *Productive Failure*. Cognition and Instruction, 26(3), 379–424.

Aporta la razón para **no saltarse el intento libre** antes de ayudar, incluso con una población nominalmente homogénea de "novatos". Kalyuga et al. muestran que dar ayuda a quien no la necesita no es neutro, sino contraproducente (consume memoria de trabajo en procesar guía redundante) — y "novato en ciencia de datos" es un rango, no un nivel único. Kapur muestra que dejar que el aprendiz intente y falle antes de recibir instrucción estructurada mejora la comprensión conceptual posterior, frente a darle la instrucción de entrada.

---

## 3. Cómo operan juntos (la lógica que ya implementaste)

1. **Nivel 1 (intento autónomo, con temporizador):** se muestran los datos/materiales disponibles (función *recruitment*, siempre presente, no cuenta como ayuda) y el usuario intenta resolver solo. Esto mide su nivel de desarrollo real (Vygotsky), evita el efecto de reversión de la pericia (Kalyuga) y aprovecha el fracaso productivo (Kapur).
2. **Si hay brecha (timeout o error), se escala por los tres grados de Ceneda:** Nivel 2 = Orientar, Nivel 3 = Dirigir, Nivel 4 = Prescribir — cada uno ejecutando una función de andamiaje concreta (marcar características críticas, reducir grados de libertad, demostración).
3. **Esta misma lógica se repite de forma transversal en cada fase del ciclo PPDAC** (Wild & Pfannkuch, 1999; adaptado a alfabetización de datos por Wolff et al., 2016): Problema, Plan y Datos ya están implementados en tu sistema (Fases 1, 2 y 3); Análisis y Conclusión quedan como diseño propuesto para completar el ciclo. Lo único que cambia entre fases es el contenido pedagógico específico, no el mecanismo.

---

## 4. Comparación con el paper de referencia (el que usarás para contrastar)

**Palomino Valdivia, F.d.L., & Huillcen Baca, H.A. (2025).** *Guidance for Interactive Visual Analysis in Multivariate Time Series Preprocessing*. Sensors, 25, 5617.

Su sistema, GUIAVisWeb, usa exactamente los mismos tres grados de Ceneda para dar guidance técnico en preprocesamiento de series de tiempo (nulos, outliers, normalización, transformación), con explicabilidad basada en Musleh et al. y evaluación de confianza del usuario. Pero **no tiene fundamento pedagógico**: no cita a Vygotsky, ni a Wood/Bruner/Ross, ni ninguna teoría de aprendizaje — su terminología de guiado viene de Schulz et al. (2013), un trabajo de visualización, no de pedagogía. Mide usabilidad y confianza, no aprendizaje ni alfabetización.

**Este es tu ángulo diferenciador:** tomas el mismo marco técnico de guidance que usa el trabajo de comparación, pero lo fundamentas pedagógicamente para que, en vez de solo ayudar a decidir bien en el momento, ayude a **aprender**.

---

## 5. Dónde va cada pieza en el documento de tesis

- **Contexto y Motivación (Introducción):** ya insertado — el párrafo que nombra el vacío de Ceneda (sin declarar todavía la solución).
- **Definición del Problema:** pendiente de expandir — ahí se nombran los dos vacíos explícitamente (alcance + fundamento pedagógico).
- **Marco Teórico (Cap. 2):** se explica cada pilar por separado (Ceneda; Vygotsky + Wood/Bruner/Ross; Kalyuga + Kapur; PPDAC), y al final el Estado del Arte comparando contra GUIAVisWeb, GuidedStats y VIZTA.
- **Propuesta / Metodología (Cap. 3):** aquí se aplica todo — arquitectura del Motor de Guidance, tabla Niveles ↔ Grados de Ceneda ↔ Funciones de andamiaje, aplicación fase por fase del PPDAC, y el catálogo de tareas de Análisis para datos temporales multivariados (con su alcance justificado por ZPD).

---

## 6. Referencias completas (formato para tu `.bib`)

```bibtex
@article{ceneda2016characterizing,
  author  = {Ceneda, Davide and Gschwandtner, Theresia and May, Thorsten and Miksch, Silvia and Schulz, Hans-J{\"o}rg and Streit, Marc and Tominski, Christian},
  title   = {Characterizing Guidance in Visual Analytics},
  journal = {IEEE Transactions on Visualization and Computer Graphics},
  year    = {2016}, volume = {23}, number = {1}, pages = {111--120},
  doi     = {10.1109/TVCG.2016.2598468}
}

@book{vygotsky1978mind,
  author = {Vygotsky, Lev S.},
  title  = {Mind in Society: The Development of Higher Psychological Processes},
  publisher = {Harvard University Press}, address = {Cambridge, MA}, year = {1978}
}

@article{wood1976role,
  author  = {Wood, David and Bruner, Jerome S. and Ross, Gail},
  title   = {The Role of Tutoring in Problem Solving},
  journal = {Journal of Child Psychology and Psychiatry},
  year    = {1976}, volume = {17}, number = {2}, pages = {89--100}
}

@article{kalyuga2003expertise,
  author  = {Kalyuga, Slava and Ayres, Paul and Chandler, Paul and Sweller, John},
  title   = {The Expertise Reversal Effect},
  journal = {Educational Psychologist},
  year    = {2003}, volume = {38}, number = {1}, pages = {23--31}
}

@article{kapur2008productive,
  author  = {Kapur, Manu},
  title   = {Productive Failure},
  journal = {Cognition and Instruction},
  year    = {2008}, volume = {26}, number = {3}, pages = {379--424}
}

@article{palomino2025guidance,
  author  = {de Luz Palomino Valdivia, Flor and Huillcen Baca, Herwin Alayn},
  title   = {Guidance for Interactive Visual Analysis in Multivariate Time Series Preprocessing},
  journal = {Sensors},
  year    = {2025}, volume = {25}, pages = {5617},
  doi     = {10.3390/s25185617}
}
```
