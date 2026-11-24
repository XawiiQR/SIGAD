"""Estimación y política del Plan; parámetros de prototipo, no calibrados."""
from motor_fase1 import MotorFase1

RUBRICA = {
    "coherencia": "Selecciona variables y decisiones pertinentes a la pregunta y alcance confirmados.",
    "calidad": "Elige revisar o tratar faltantes y atípicos presentes sin eliminar o rellenar indiscriminadamente.",
    "escalado": "Elige escalar o conservar unidades según el análisis; diferencias de rango no obligan a escalar.",
    "estructura": "Organiza fecha, categorías y ubicación según el objetivo; no inventa coordenadas ni trata identificadores como medidas.",
}
HABILIDADES = tuple(RUBRICA)


class MotorFase2(MotorFase1):
    habilidades_definidas = HABILIDADES
