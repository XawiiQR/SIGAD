# -*- coding: utf-8 -*-
"""
Motor de Guidance Pedagógico — seguimiento de conocimiento y ajuste adaptativo
del nivel de apoyo, por habilidad de alfabetización de datos.

Separa deliberadamente dos mecanismos:

1) Escalamiento intra-tarea (RastreadorConocimiento):
   Dentro de UNA misma tarea, si el nivel de entrada no basta, se sube un grado
   (Orientar -> Dirigir -> Prescribir) hasta que el estudiante logra completarla.
   Esto garantiza que ninguna tarea quede sin resolver. La probabilidad de dominio
   P(sabe) se actualiza con Bayesian Knowledge Tracing (Corbett & Anderson, 1994)
   después de cada intento, tratando el timeout como evidencia atenuada (no es lo
   mismo no responder que responder e intentarlo mal, dado que puede deberse a
   distracción, mala lectura, etc., y no a una brecha real de conocimiento).

2) Adaptación entre tareas (MotorAdaptativoPorHabilidad):
   El nivel con el que INICIA la siguiente tarea comparable de la misma habilidad
   se ajusta según la confianza (P(sabe)) alcanzada al cerrar la tarea anterior.
   Esto implementa el retiro progresivo de apoyo ("fading"; Wood, Bruner & Ross,
   1976) sin forzar, tarea tras tarea, un intento autónomo cuando ya hay evidencia
   probabilística de que el estudiante necesita (o ya no necesita) ayuda. Que el
   fading ocurra solo cuando P(sabe) es alta —y no automáticamente por haber
   acertado una vez— es lo que evita el efecto de reversión de la pericia
   (Kalyuga, Ayres, Chandler & Sweller, 2003): retirar apoyo antes de tiempo es
   tan costoso como no retirarlo nunca.
"""

from dataclasses import dataclass, field
from typing import Dict


NIVELES = {1: "Autonomía", 2: "Orientar", 3: "Dirigir", 4: "Prescribir"}


class RastreadorConocimiento:
    """
    Bayesian Knowledge Tracing simplificado (Corbett & Anderson, 1994) para decidir
    cuándo escalar el nivel de guidance DENTRO de una tarea, en vez de usar un solo
    timeout o error como señal definitiva.
    """

    def __init__(self, p_inicial=0.5, p_aprendizaje=0.15,
                 p_slip=0.15, p_guess=0.25, umbral_escalada=0.4):
        self.p_sabe = p_inicial
        self.p_aprendizaje = p_aprendizaje
        self.p_slip = p_slip
        self.p_guess = p_guess
        self.umbral_escalada = umbral_escalada

    def actualizar(self, resultado: str) -> float:
        """
        resultado: 'correcto', 'incorrecto' o 'timeout'.
        'timeout' se trata como evidencia atenuada: no es lo mismo no responder
        que responder e intentarlo mal.
        """
        if resultado == "correcto":
            num = self.p_sabe * (1 - self.p_slip)
            den = num + (1 - self.p_sabe) * self.p_guess
        elif resultado == "incorrecto":
            num = self.p_sabe * self.p_slip
            den = num + (1 - self.p_sabe) * (1 - self.p_guess)
        elif resultado == "timeout":
            slip_atenuado = (self.p_slip + 1) / 2
            guess_atenuado = 1 - (1 - self.p_guess) / 2
            num = self.p_sabe * slip_atenuado
            den = num + (1 - self.p_sabe) * guess_atenuado
        else:
            raise ValueError("resultado debe ser 'correcto', 'incorrecto' o 'timeout'")

        p_post = num / den
        self.p_sabe = p_post + (1 - p_post) * self.p_aprendizaje
        return self.p_sabe

    def necesita_escalar(self) -> bool:
        return self.p_sabe < self.umbral_escalada


@dataclass
class EstadoHabilidad:
    rastreador: RastreadorConocimiento
    nivel_actual: int = 1  # primer encuentro de la habilidad -> Nivel 1 (Autonomía)


class MotorAdaptativoPorHabilidad:
    """
    Gestiona, para cada habilidad (p.ej. "detectar_nulos", "leer_correlaciones"),
    un RastreadorConocimiento independiente y el nivel de apoyo con el que debe
    iniciar la PRÓXIMA tarea comparable de esa misma habilidad.

    Uso típico dentro de una tarea:

        motor = MotorAdaptativoPorHabilidad()

        nivel = motor.nivel_de_entrada("detectar_nulos")   # p.ej. 1
        # ... se muestra el apoyo de ese nivel, el estudiante responde ...
        motor.registrar_intento("detectar_nulos", nivel, "incorrecto")
        nivel = nivel + 1                                   # escalar intra-tarea
        # ... se muestra el apoyo del nuevo nivel ...
        motor.registrar_intento("detectar_nulos", nivel, "correcto")

        # la tarea terminó con éxito en `nivel`:
        motor.cerrar_tarea("detectar_nulos", nivel_final_exitoso=nivel)

        # la SIGUIENTE tarea sobre "detectar_nulos" debe empezar en:
        motor.nivel_de_entrada("detectar_nulos")
    """

    def __init__(self, umbral_fade: float = 0.75, umbral_recupera: float = 0.4,
                 **kwargs_bkt):
        if umbral_recupera >= umbral_fade:
            raise ValueError("umbral_recupera debe ser menor que umbral_fade")
        self.umbral_fade = umbral_fade
        self.umbral_recupera = umbral_recupera
        self._kwargs_bkt = kwargs_bkt
        self._estados: Dict[str, EstadoHabilidad] = {}

    def _estado(self, habilidad: str) -> EstadoHabilidad:
        if habilidad not in self._estados:
            self._estados[habilidad] = EstadoHabilidad(
                rastreador=RastreadorConocimiento(**self._kwargs_bkt)
            )
        return self._estados[habilidad]

    def nivel_de_entrada(self, habilidad: str) -> int:
        """Nivel (1-4) con el que debe iniciar la tarea actual para esta habilidad."""
        return self._estado(habilidad).nivel_actual

    def p_sabe(self, habilidad: str) -> float:
        return self._estado(habilidad).rastreador.p_sabe

    def registrar_intento(self, habilidad: str, nivel_usado: int, resultado: str) -> float:
        """
        Se llama en CADA intento dentro de una tarea (puede llamarse varias veces si
        hay escalamiento intra-tarea). Actualiza P(sabe) y devuelve la probabilidad
        posterior. `nivel_usado` no afecta hoy el cálculo de BKT (que ya pondera vía
        p_slip/p_guess), pero se recibe explícitamente para permitir, si se desea,
        ponderar el aprendizaje según cuánta ayuda se dio (ver nota metodológica:
        una respuesta correcta con mucha ayuda no debe interpretarse igual que una
        correcta en autonomía).
        """
        estado = self._estado(habilidad)
        return estado.rastreador.actualizar(resultado)

    def cerrar_tarea(self, habilidad: str, nivel_final_exitoso: int) -> int:
        """
        Se llama UNA vez, cuando la tarea terminó con éxito en `nivel_final_exitoso`.
        Ajusta nivel_actual para la PRÓXIMA tarea comparable de la misma habilidad:

          - P(sabe) >= umbral_fade      -> FADING: baja un grado (mínimo Nivel 1)
          - P(sabe) <  umbral_recupera  -> RECUPERAR: sube un grado (máximo Nivel 4)
          - en otro caso                -> MANTENER: se queda en nivel_final_exitoso
        """
        estado = self._estado(habilidad)
        p = estado.rastreador.p_sabe

        if p >= self.umbral_fade:
            nuevo_nivel = max(1, nivel_final_exitoso - 1)
        elif p < self.umbral_recupera:
            nuevo_nivel = min(4, nivel_final_exitoso + 1)
        else:
            nuevo_nivel = nivel_final_exitoso

        estado.nivel_actual = nuevo_nivel
        return nuevo_nivel


if __name__ == "__main__":
    # Ejemplo: una habilidad que requiere Prescribir la primera vez, y cómo el
    # nivel de entrada se retira progresivamente en tareas sucesivas si el
    # estudiante sigue demostrando dominio.
    motor = MotorAdaptativoPorHabilidad()
    habilidad = "detectar_nulos"

    # Tarea 1: falla en Nivel 1 y 2, resuelve en Nivel 3 (Dirigir)
    for nivel, resultado in [(1, "incorrecto"), (2, "incorrecto"), (3, "correcto")]:
        p = motor.registrar_intento(habilidad, nivel, resultado)
    nuevo = motor.cerrar_tarea(habilidad, nivel_final_exitoso=3)
    print(f"Tarea 1 -> P(sabe)={p:.2f} -> próximo nivel de entrada: {nuevo} ({NIVELES[nuevo]})")

    # Tarea 2: entra directo en el nivel indicado y resuelve ahí mismo
    nivel = motor.nivel_de_entrada(habilidad)
    p = motor.registrar_intento(habilidad, nivel, "correcto")
    nuevo = motor.cerrar_tarea(habilidad, nivel_final_exitoso=nivel)
    print(f"Tarea 2 -> entró en {NIVELES[nivel]}, P(sabe)={p:.2f} -> próximo nivel: {nuevo} ({NIVELES[nuevo]})")
