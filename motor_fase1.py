"""BKT y andamiaje de la fase Problema. Parámetros de prototipo, no calibrados."""
from dataclasses import dataclass, field

NIVELES = {1: "Autónomo", 2: "Orientar", 3: "Dirigir", 4: "Prescribir"}
HABILIDADES = ("proposito", "alcance", "variables", "viabilidad")
RUBRICA = {
    "proposito": "Expresa con claridad qué desea conocer.",
    "alcance": "Delimita periodo, población o unidad compatibles con la cobertura.",
    "variables": "Utiliza variables existentes y pertinentes.",
    "viabilidad": "Es respondible con los datos y operaciones disponibles, sin inferir causalidad.",
}


@dataclass
class Habilidad:
    probabilidad: float = 0.5
    tareas_correctas: set = field(default_factory=set)


class MotorFase1:
    habilidades_definidas = HABILIDADES

    def __init__(self, inicial=0.5, slip=0.15, guess=0.25, aprendizaje=0.15,
                 umbral=0.85, evidencia_minima=2):
        if not all(0 < x < 1 for x in (inicial, slip, guess, aprendizaje, umbral)):
            raise ValueError("Los parámetros BKT deben estar entre 0 y 1.")
        if evidencia_minima < 2:
            raise ValueError("Se requieren al menos dos tareas distintas para fading.")
        self.slip, self.guess, self.aprendizaje = slip, guess, aprendizaje
        self.umbral, self.evidencia_minima = umbral, evidencia_minima
        self.habilidades = {k: Habilidad(inicial) for k in self.habilidades_definidas}
        self.nivel = self.siguiente_nivel = 1
        self.base_verificacion = None
        self.intentos = set()
        self.timeouts = set()
        self.decision = {"regla": "inicio_autonomo", "anterior": 1, "seleccionado": 1}

    def ayuda(self, regla="solicitud_ayuda"):
        anterior = self.nivel
        self.nivel = min(4, self.nivel + 1)
        self.decision = {"regla": regla, "anterior": anterior, "seleccionado": self.nivel}

    def prescribir(self):
        anterior = self.nivel
        self.nivel = 4
        self.decision = {"regla": "salto_solicitado_a_prescribir", "anterior": anterior, "seleccionado": 4}

    def registrar_timeout(self, tarea):
        """La inactividad activa ayuda, pero no acredita error de conocimiento."""
        clave = (tarea, self.nivel)
        if clave in self.timeouts or self.nivel >= 4:
            return False
        self.timeouts.add(clave)
        self.ayuda("inactividad_sin_evidencia")
        return True

    def registrar(self, tarea, intento, puntuaciones):
        """Una observación por intento; prescripción no aporta aciertos a BKT."""
        if intento in self.intentos:
            raise ValueError("Intento ya registrado.")
        self.intentos.add(intento)
        nivel_usado = self.nivel
        for k, estado in self.habilidades.items():
            correcta = puntuaciones[k] == 2
            if correcta and nivel_usado == 4:
                continue
            p = estado.probabilidad
            num = p * (1 - self.slip if correcta else self.slip)
            den = num + (1 - p) * (self.guess if correcta else 1 - self.guess)
            posterior = num / den
            estado.probabilidad = posterior + (1 - posterior) * self.aprendizaje
        completada = all(puntuaciones[k] == 2 for k in self.habilidades_definidas)
        if completada:
            # Evidencia de tareas distintas, no de reintentos de la misma pregunta.
            if nivel_usado < 4:
                for k, estado in self.habilidades.items():
                    if puntuaciones[k] == 2:
                        estado.tareas_correctas.add(tarea)
            suficiente = all(
                e.probabilidad >= self.umbral and
                len(e.tareas_correctas) >= self.evidencia_minima
                for e in self.habilidades.values()
            )
            base = max(nivel_usado, self.base_verificacion or nivel_usado)
            self.siguiente_nivel = max(1, base - 1) if suficiente else base
            self.decision = {"regla": "umbral_y_evidencia" if suficiente else "conservar_apoyo",
                             "anterior": nivel_usado, "seleccionado": nivel_usado,
                             "siguiente_tarea": self.siguiente_nivel}
        else:
            self.ayuda("dificultad_en_rubrica")
        return completada, nivel_usado

    def nueva_tarea(self, verificacion=False):
        # Prueba diagnóstica solicitada explícitamente, no retiro automático.
        # El apoyo habitual se conserva hasta superar umbral y evidencia mínima.
        self.base_verificacion = self.siguiente_nivel if verificacion else None
        self.nivel = 1 if verificacion else self.siguiente_nivel
        self.decision = {"regla": "verificacion_autonoma" if verificacion else "nueva_tarea",
                         "seleccionado": self.nivel}

    def resumen(self):
        return {"nivel": self.nivel, "nombre_nivel": NIVELES[self.nivel],
                "siguiente_nivel": self.siguiente_nivel,
                "decision": dict(self.decision),
                "umbral": self.umbral, "evidencia_minima": self.evidencia_minima,
                "habilidades": {k: {"probabilidad": round(v.probabilidad, 6),
                                    "tareas_correctas": len(v.tareas_correctas)}
                                for k, v in self.habilidades.items()}}
