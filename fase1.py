"""Perfil, gráficos y sesiones adaptativas de la fase Problema."""
import copy
import hashlib
import json
import threading
import time
import uuid
from collections import OrderedDict

import numpy as np
import pandas as pd
from flask import jsonify, request
from agente import CredencialGroqAusente
from motor_fase1 import HABILIDADES, RUBRICA, MotorFase1

VARIABLES = {
    "No": ("Número de registro", "Identificador del registro; confirma su significado con el diccionario de datos."),
    "year": ("Año", "Componente de la fecha de cada observación."),
    "month": ("Mes", "Componente de la fecha; también permite agrupar observaciones por mes."),
    "day": ("Día", "Componente de la fecha de cada observación."),
    "hour": ("Hora", "Componente temporal; permite explorar patrones horarios."),
    "PM2.5": ("Partículas finas", "Concentración de partículas de hasta 2,5 micrómetros. Pueden penetrar profundamente en los pulmones."),
    "PM10": ("Partículas inhalables", "Concentración de partículas de hasta 10 micrómetros, como parte del polvo suspendido en el aire."),
    "SO2": ("Dióxido de azufre", "Gas contaminante que se libera al quemar combustibles que contienen azufre. Puede dificultar la respiración."),
    "NO2": ("Dióxido de nitrógeno", "Gas contaminante producido al quemar combustibles, por ejemplo, en motores de vehículos. En concentraciones altas puede irritar las vías respiratorias."),
    "CO": ("Monóxido de carbono", "Gas contaminante que se produce cuando un combustible se quema de forma incompleta. En concentraciones altas reduce el oxígeno que transporta la sangre."),
    "O3": ("Ozono a nivel del suelo", "Gas contaminante que se forma cuando otras emisiones reaccionan con la luz solar. Puede irritar las vías respiratorias."),
    "TEMP": ("Temperatura", "Temperatura del aire registrada en la estación."),
    "PRES": ("Presión atmosférica", "Presión del aire registrada en la estación."),
    "DEWP": ("Punto de rocío", "Temperatura a la que comienza la condensación del vapor de agua."),
    "RAIN": ("Precipitación", "Cantidad de precipitación registrada."),
    "wd": ("Dirección del viento", "Dirección de procedencia del viento."),
    "WSPM": ("Velocidad del viento", "Velocidad del viento registrada en la estación."),
    "station": ("Estación de medición", "Lugar donde se registraron los datos."),
}
NO_ANALITICAS = {"no", "id", "year", "month", "day", "hour"}
VISTAS = ("evolucion", "ciclicidad", "distribucion", "variabilidad", "relaciones", "frecuencias", "comparacion")


def fechas_del_dataset(df):
    if {"year", "month", "day"}.issubset(df.columns):
        cols = [k for k in ("year", "month", "day", "hour") if k in df.columns]
        return pd.to_datetime(df[cols], errors="coerce")
    for col in df.columns:
        if str(col).lower() in {"datetime", "date", "fecha", "timestamp"}:
            return pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_localize(None)
    return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")


def validar_seleccion_multiple(explorador, variable, vista, columnas):
    if not isinstance(columnas, list) or any(not isinstance(c, str) for c in columnas):
        raise ValueError('La selección debe ser una lista de columnas.')
    columnas = list(dict.fromkeys(columnas))
    for c in columnas:
        if c not in explorador.roles:
            raise ValueError('Variable inexistente en la selección.')
        if vista == 'comparacion':
            compatible = c in explorador.opciones(variable)['comparacion'].get('pares', [])
        elif vista == 'relaciones':
            compatible = c in explorador.numericas and explorador.numerica(c).nunique() > 1
        else:
            compatible = explorador.opciones(c)[vista]['disponible']
        if not compatible:
            raise ValueError(f'{c} no es compatible con la vista seleccionada.')
    return columnas


class Explorador:
    def __init__(self, df):
        self.df = df.copy()
        self.fechas = fechas_del_dataset(self.df)
        self.roles = {str(c): self.rol(c) for c in df.columns}
        self.numericas = [str(c) for c in df.columns if self.roles[str(c)] == "medida"]
        self.categoricas = [str(c) for c in df.columns if self.roles[str(c)] == "categoria"]
        self.perfil = self._perfil()
        self.cache = OrderedDict()
        self.lock = threading.RLock()

    def rol(self, col):
        nombre = str(col).lower()
        if nombre in {"no", "id", "index", "unnamed: 0"}:
            return "identificador"
        if nombre in {"year", "month", "day", "hour", "datetime", "date", "fecha", "timestamp"}:
            return "tiempo"
        if nombre in {"lat", "latitude", "latitud", "lon", "lng", "longitude", "longitud"}:
            return "coordenada"
        if nombre in {"station", "wd"} or not pd.api.types.is_numeric_dtype(self.df[col]):
            return "categoria"
        return "medida"

    def espacial(self):
        nombres = {str(c).lower(): str(c) for c in self.df.columns}
        lat = next((nombres[k] for k in ("lat", "latitude", "latitud") if k in nombres), None)
        lon = next((nombres[k] for k in ("lon", "lng", "longitude", "longitud") if k in nombres), None)
        validos = 0
        espaciotemporal = False
        if lat and lon:
            mascara = (self.numerica(lat).between(-90, 90) &
                       self.numerica(lon).between(-180, 180))
            validos = int(mascara.sum())
            espaciotemporal = bool((mascara & self.fechas.notna()).any())
        return {"latitud": lat, "longitud": lon, "registros_validos": validos,
                "espaciotemporal": espaciotemporal,
                "nota": ("Coordenadas candidatas detectadas; confirma que usan grados geográficos. Vista de mapa pendiente."
                         if validos else "Para un mapa se necesitan coordenadas válidas o un catálogo de ubicaciones; station por sí sola no ubica los registros.")}

    def numerica(self, col):
        return pd.to_numeric(self.df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)

    def opciones(self, col):
        if col not in self.roles:
            raise ValueError("Columna inexistente.")
        rol = self.roles[col]
        if rol != "medida":
            motivo = {"identificador": "Identifica registros; no representa una medida.",
                      "tiempo": "Construye el eje temporal de las medidas; no se analiza como magnitud.",
                      "coordenada": "Ubica registros; requiere su coordenada complementaria.",
                      "categoria": "Selecciona frecuencias o una medida para comparar categorías."}[rol]
            opciones = {vista: {"disponible": False, "motivo": motivo} for vista in VISTAS}
            if rol == "categoria":
                opciones["frecuencias"] = {"disponible": bool(self.df[col].notna().any()), "motivo": "Cuenta registros por categoría, incluso si solo hay una."}
                pares = [c for c in self.numericas if (self.df[col].notna() & self.numerica(c).notna()).any()]
                opciones["comparacion"] = {"disponible": bool(pares), "pares": pares,
                    "motivo": "Compara la media de una medida entre categorías; una sola categoría no permite contrastes."}
            return opciones
        s = self.numerica(col)
        validas = s.notna()
        temporal = validas & self.fechas.notna()
        fechas = self.fechas[temporal]
        hay_tiempo = fechas.nunique() >= 2
        meses = fechas.dt.to_period("M").nunique()
        pares = [c for c in self.numericas if c != col and
                 (validas & self.numerica(c).notna()).sum() >= 3 and
                 self.numerica(c).nunique() > 1]
        activa = s.nunique() > 1
        return {
            "frecuencias": {"disponible": False, "motivo": "Selecciona una categoría."},
            "comparacion": {"disponible": False, "motivo": "Selecciona una categoría y una medida."},
            "evolucion": {"disponible": hay_tiempo and activa, "motivo": "Requiere fechas válidas y valores con variación."},
            "ciclicidad": {"disponible": hay_tiempo and activa and meses >= 2,
                           "motivo": "Explora mes y hora; la cobertura no demuestra un ciclo."},
            "distribucion": {"disponible": bool(activa and validas.sum() >= 3), "motivo": "Requiere tres valores válidos y variación."},
            "variabilidad": {"disponible": activa and meses >= 2, "motivo": "Requiere al menos dos meses con observaciones."},
            "relaciones": {"disponible": bool(activa and bool(pares)), "motivo": "Requiere dos variables con variación y registros coincidentes.", "pares": pares},
        }

    def _perfil(self):
        dates = self.fechas.dropna().sort_values()
        deltas = dates.drop_duplicates().diff().dropna().dt.total_seconds()
        frecuencia = float(deltas.mode().iloc[0]) if len(deltas) else None
        variables = []
        for col in self.df.columns:
            col = str(col)
            nombre, descripcion = VARIABLES.get(col, (col, "Significado por confirmar con el diccionario de datos."))
            grupo = ("Tiempo e identificadores" if col.lower() in NO_ANALITICAS else
                     "Contaminación" if col in {"PM2.5", "PM10", "SO2", "NO2", "CO", "O3"} else
                     "Meteorología" if col in {"TEMP", "PRES", "DEWP", "RAIN", "wd", "WSPM"} else "Otras")
            s = self.numerica(col) if col in self.numericas else self.df[col]
            variables.append({"columna": col, "nombre": nombre, "descripcion": descripcion,
                              "grupo": grupo, "numerica": col in self.numericas, "rol": self.roles[col],
                              "uso": self.opciones(col)["frecuencias"]["motivo"] if self.roles[col] != "medida" else "Medida numérica para analizar.",
                              "faltantes": int(s.isna().sum()),
                              "faltantes_porcentaje": round(float(s.isna().mean() * 100), 2) if len(s) else 0,
                              "vistas": self.opciones(col)})
        return {"filas": len(self.df), "variables": variables, "espacial": self.espacial(),
                "temporal": {"inicio": dates.min().isoformat() if len(dates) else None,
                             "fin": dates.max().isoformat() if len(dates) else None,
                             "fechas_invalidas": int(self.fechas.isna().sum()),
                             "fechas_duplicadas": int(dates.duplicated().sum()),
                             "intervalo_segundos": frecuencia,
                             "intervalos_irregulares": int((deltas != frecuencia).sum()) if frecuencia else 0},
                "version": hashlib.sha256(pd.util.hash_pandas_object(self.df, index=True).values.tobytes()).hexdigest()[:16]}

    def grafico(self, variable, vista, secundaria=None, variables=None):
        if vista in VISTAS and vista != 'evolucion' and variables is not None:
            if variable not in self.roles:
                raise ValueError('Variable inexistente.')
            columnas = validar_seleccion_multiple(self, variable, vista, variables)
            paneles = []
            if vista == 'relaciones':
                from itertools import combinations
                for a, b in combinations(columnas, 2):
                    if b in self.opciones(a)['relaciones'].get('pares', []):
                        paneles.append(self.grafico(a, vista, b))
                    else:
                        paneles.append({'variable': a, 'secundaria': b, 'vista': vista,
                                        'puntos': [], 'nota': 'No hay suficientes pares válidos para comparar estas variables.'})
            elif vista == 'comparacion':
                paneles = [self.grafico(variable, vista, c) for c in columnas]
            else:
                paneles = [self.grafico(c, vista) for c in columnas]
            return {'vista': vista, 'variable': variable, 'secundaria': secundaria,
                    'variables': columnas, 'paneles': paneles,
                    'puntos': paneles[0]['puntos'] if paneles else [],
                    'nota': 'Paneles con unidades originales. Selecciona al menos dos medidas para comparar relaciones.' if vista == 'relaciones'
                    else 'Cada panel conserva la escala y las unidades de su variable. Los faltantes se excluyen de los cálculos.'}
        if vista == 'evolucion' and variables is not None:
            if not isinstance(variables, list) or any(
                    not isinstance(c, str) or c not in self.numericas or
                    not self.opciones(c)['evolucion']['disponible'] for c in variables):
                raise ValueError('Selecciona medidas con evolución temporal disponible.')
            columnas = list(dict.fromkeys(variables))
            series = [{'variable': c, 'puntos': self.grafico(c, vista)['puntos']} for c in columnas]
            if series:
                fechas = sorted({p['fecha'] for serie in series for p in serie['puntos']})
                calendario = pd.date_range(fechas[0], fechas[-1], freq='MS')
                for serie in series:
                    puntos = {p['fecha']: p for p in serie['puntos']}
                    serie['puntos'] = [puntos.get(f.isoformat(), {'fecha': f.isoformat(), 'valor': None, 'n': 0}) for f in calendario]
            return {'vista': vista, 'variable': columnas[0] if columnas else variable,
                    'variables': columnas, 'secundaria': None, 'series': series,
                    'puntos': series[0]['puntos'] if series else [],
                    'nota': 'Medias mensuales; con varias variables, las curvas se muestran normalizadas de 0 a 1 por variable para comparar patrones, no magnitudes. Faltantes excluidos y huecos conservados. La coincidencia de curvas no confirma una relación.'}
        if variable not in self.roles or vista not in VISTAS:
            raise ValueError("Variable o vista no válida.")
        opciones = self.opciones(variable)
        if not opciones[vista]["disponible"]:
            raise ValueError(opciones[vista]["motivo"])
        if vista in {"relaciones", "comparacion"} and secundaria not in opciones[vista]["pares"]:
            raise ValueError("Selecciona una segunda variable compatible.")
        key = variable, vista, secundaria
        with self.lock:
            if key in self.cache:
                return self.cache[key]
        s = self.numerica(variable)
        d = pd.DataFrame({"fecha": self.fechas, "valor": s}).dropna()
        puntos = []
        nota = "Unidades según el diccionario del dataset; faltantes excluidos."
        if vista in {"frecuencias", "comparacion"}:
            categorias = self.df[variable].astype("string")
            if vista == "frecuencias":
                conteos = categorias.dropna().value_counts()
                puntos = [{"categoria": str(k), "n": int(n)} for k, n in conteos.iloc[:20].items()]
                if len(conteos) > 20:
                    puntos.append({"categoria": "Otras categorías (agrupadas)", "n": int(conteos.iloc[20:].sum())})
                nota = "Frecuencias de registros; categorías faltantes excluidas. Hasta 20 categorías y el resto agrupado."
            else:
                pares = pd.DataFrame({"categoria": categorias, "valor": self.numerica(secundaria)}).dropna()
                grupos = pares.groupby("categoria")["valor"].agg(["mean", "count"]).sort_values("count", ascending=False)
                puntos = [{"categoria": str(k), "valor": float(r["mean"]), "n": int(r["count"])} for k, r in grupos.iloc[:20].iterrows()]
                nota = "Media por categoría; pares con faltantes excluidos. Hasta 20 categorías con más registros; no demuestra causalidad."
                if len(grupos) == 1:
                    nota += " Solo hay una categoría: no es posible contrastar grupos."
                if len(grupos) > 20:
                    nota += f" Se omiten {len(grupos) - 20} categorías."
        elif vista == "evolucion":
            # Mantener huecos explícitos; no unir meses sin observaciones.
            grupos = d.set_index("fecha")["valor"].resample("MS").agg(["mean", "count"])
            puntos = [{"fecha": idx.isoformat(), "valor": float(r["mean"]) if r["count"] else None,
                       "n": int(r["count"])} for idx, r in grupos.iterrows()]
            nota += " Media mensual, no valores horarios originales."
        elif vista == "ciclicidad":
            d["mes"], d["hora"] = d.fecha.dt.month, d.fecha.dt.hour
            for (mes, hora), g in d.groupby(["mes", "hora"]):
                puntos.append({"mes": int(mes), "hora": int(hora), "valor": float(g.valor.mean()), "n": len(g)})
            nota += " Mes × hora; años agrupados. Patrones aparentes no confirman periodicidad."
        elif vista == "distribucion":
            hist, edges = np.histogram(s.dropna(), bins=20)
            puntos = [{"desde": float(edges[i]), "hasta": float(edges[i+1]), "n": int(v)} for i, v in enumerate(hist)]
        elif vista == "variabilidad":
            for mes, g in d.groupby(d.fecha.dt.month):
                v = g.valor.to_numpy()
                q1, mediana, q3 = np.percentile(v, [25, 50, 75])
                iqr = q3 - q1
                centrales = v[(v >= q1-1.5*iqr) & (v <= q3+1.5*iqr)]
                puntos.append({"mes": int(mes), "q1": float(q1), "mediana": float(mediana), "q3": float(q3),
                               "min": float(centrales.min()), "max": float(centrales.max()),
                               "extremos": int(len(v)-len(centrales)), "n": len(v)})
            nota += " Cajas por mes, años agrupados; bigotes hasta 1,5 IQR."
        else:
            pares = pd.DataFrame({"x": self.numerica(secundaria), "y": s}).dropna()
            total = len(pares)
            muestras = pares.iloc[np.linspace(0, total-1, min(total, 800), dtype=int)]
            puntos = [{"x": float(r.x), "y": float(r.y)} for r in muestras.itertuples()]
            nota += f" {len(puntos)} puntos de {total} pares; muestra espaciada por filas, no aleatoria. Asociación no implica causalidad."
        result = {"vista": vista, "variable": variable, "secundaria": secundaria, "puntos": puntos, "nota": nota}
        with self.lock:
            self.cache[key] = result
            if len(self.cache) > 100:
                self.cache.popitem(last=False)
        return result


def validar_evaluacion(resultado, columnas):
    if isinstance(resultado, str):
        resultado = json.loads(resultado)
    if not isinstance(resultado, dict) or set(resultado.get("criterios", {})) != set(HABILIDADES):
        raise ValueError("Rúbrica inválida.")
    if type(resultado.get("es_viable")) is not bool:
        raise ValueError("Falta la decisión de viabilidad.")
    if not isinstance(resultado.get("pregunta_formulada"), str) or not resultado["pregunta_formulada"].strip():
        raise ValueError("Falta la pregunta formulada.")
    if resultado.get("vista_sugerida") not in VISTAS:
        raise ValueError("La vista sugerida no es válida.")
    for criterio in resultado["criterios"].values():
        if not isinstance(criterio, dict) or type(criterio.get("puntuacion")) is not int or criterio["puntuacion"] not in (0, 1, 2):
            raise ValueError("Puntuación inválida.")
        if not isinstance(criterio.get("explicacion"), str) or not criterio["explicacion"].strip():
            raise ValueError("Falta explicación del criterio.")
    # La decisión visible se deriva de la misma rúbrica descrita en la
    # metodología: los cuatro criterios deben alcanzar la puntuación máxima.
    resultado["es_viable"] = all(
        criterio["puntuacion"] == 2
        for criterio in resultado["criterios"].values()
    )
    utilizadas = resultado.get("variables_utilizadas")
    if not isinstance(utilizadas, list) or any(not isinstance(c, str) or c not in columnas for c in utilizadas) or (resultado["es_viable"] and not utilizadas):
        raise ValueError("El evaluador devolvió variables inexistentes o un esquema incompleto.")
    if not isinstance(resultado.get("feedback"), str) or not resultado["feedback"].strip():
        raise ValueError("Falta retroalimentación.")
    sugerida = resultado.get("pregunta_sugerida")
    if sugerida is not None and (not isinstance(sugerida, str) or not 1 <= len(sugerida.strip()) <= 4000):
        raise ValueError("Reformulación sugerida inválida.")
    return resultado


def validar_recomendaciones(resultado, columnas):
    if isinstance(resultado, str):
        resultado = json.loads(resultado)
    opciones = resultado.get("opciones") if isinstance(resultado, dict) else None
    if not isinstance(opciones, list) or len(opciones) != 4:
        raise ValueError("Se esperaban exactamente cuatro opciones.")
    limpias = []
    for opcion in opciones:
        if not isinstance(opcion, dict):
            raise ValueError("Opción inválida.")
        titulo, pregunta, motivo = (opcion.get(k) for k in ("titulo", "pregunta", "motivo"))
        variables = opcion.get("variables")
        if any(not isinstance(x, str) or not x.strip() for x in (titulo, pregunta, motivo)):
            raise ValueError("La opción está incompleta.")
        if not isinstance(variables, list) or not variables or any(v not in columnas for v in variables):
            raise ValueError("La opción utiliza variables inexistentes.")
        limpias.append({"titulo": titulo.strip(), "pregunta": pregunta.strip(),
                        "motivo": motivo.strip(), "variables": variables})
    if len({opcion["pregunta"].casefold() for opcion in limpias}) != 4:
        raise ValueError("Las cuatro preguntas deben ser diferentes.")
    return limpias


def validar_prescripcion(resultado):
    if isinstance(resultado, str):
        resultado = json.loads(resultado)
    if not isinstance(resultado, dict) or type(resultado.get("indice")) is not int:
        raise ValueError("Prescripción inválida.")
    if resultado["indice"] not in range(4) or not isinstance(resultado.get("explicacion"), str) or not resultado["explicacion"].strip():
        raise ValueError("Prescripción incompleta.")
    return {"indice": resultado["indice"], "explicacion": resultado["explicacion"].strip()}


def contexto_valido(datos, explorador):
    variable, vista = datos.get('variable'), datos.get('vista')
    if variable not in explorador.roles or vista not in VISTAS:
        raise ValueError('Selecciona una variable y una vista válidas.')
    secundaria = datos.get('secundaria')
    if 'variables' in datos:
        if vista == 'comparacion' and explorador.roles[variable] != 'categoria':
            raise ValueError('Selecciona una categoría para agrupar las medidas.')
        columnas = validar_seleccion_multiple(explorador, variable, vista, datos['variables'])
        contexto = {'variable': variable if vista == 'comparacion' or not columnas else columnas[0],
                    'vista': vista, 'variables': columnas, 'secundaria': None}
        if vista == 'relaciones':
            contexto['secundaria'] = columnas[1] if len(columnas) > 1 else None
        elif vista == 'comparacion':
            contexto['secundaria'] = columnas[0] if columnas else None
        return contexto
    if not explorador.opciones(variable)[vista]['disponible']:
        raise ValueError('La vista no está disponible para esa variable.')
    if vista in {'relaciones', 'comparacion'} and secundaria not in explorador.opciones(variable)[vista]['pares']:
        raise ValueError('Selecciona una segunda variable compatible.')
    contexto = {'variable': variable, 'vista': vista,
                'secundaria': secundaria if vista in {'relaciones', 'comparacion'} else None}
    if vista == 'evolucion':
        contexto['variables'] = [variable]
    return contexto


def guidance(contexto, nivel):
    v, otra, vista = contexto["variable"], contexto["secundaria"], contexto["vista"]
    pistas = {"evolucion": "Observa los ejes y qué periodos te interesan.",
              "ciclicidad": "Observa las franjas de color por mes y hora; comprueba su cobertura.",
              "distribucion": "Observa en qué intervalos se concentran las observaciones.",
              "variabilidad": "Observa las medianas y la altura de las cajas.",
              "relaciones": "Observa cómo se distribuyen los puntos entre las dos variables."}
    acciones = {"evolucion": "Elige dos periodos y formula qué diferencia quieres investigar.",
                "ciclicidad": "Compara la misma hora entre dos meses. No asumas que la repetición ya está confirmada.",
                "distribucion": "Elige si investigarás los valores frecuentes o la cola de valores altos.",
                "variabilidad": "Compara dos meses y decide si preguntarás por nivel o dispersión.",
                "relaciones": "Delimita una pregunta sobre asociación; no atribuyas causalidad."}
    ejemplos = {"evolucion": f"¿Cómo varía {v} entre los meses del periodo registrado?",
                "ciclicidad": f"¿Cómo varía el perfil horario de {v} entre los meses del año?",
                "distribucion": f"¿Cómo se distribuyen los valores de {v} durante el periodo registrado?",
                "variabilidad": f"¿Qué diferencias hay en la mediana y la dispersión de {v} entre dos meses?",
                "relaciones": f"¿Qué relación existe entre {otra} y {v} en el periodo registrado?"}
    pistas.update(frecuencias="Observa qué categorías tienen más registros y cuáles faltan.",
                  comparacion="Observa la media y cuántos registros sustentan cada categoría.")
    acciones.update(frecuencias="Elige las categorías cuya frecuencia deseas comparar.",
                    comparacion="Elige qué grupos compararás y delimita el periodo disponible.")
    ejemplos.update(frecuencias=f"¿Cómo se distribuyen los registros entre las categorías de {v}?",
                    comparacion=f"¿Cómo varía la media de {otra} entre las categorías de {v}?")
    if nivel == 1:
        return {"mensaje": "", "ejemplo": None}
    texto = pistas[vista] if nivel == 2 else acciones[vista] if nivel == 3 else (
        "Revisa qué mide cada variable del gráfico y qué periodo o grupo quieres estudiar. "
        "Luego escribe una pregunta que puedas responder con esos datos.")
    return {"mensaje": texto, "ejemplo": ejemplos[vista] if nivel == 4 else None}


def validar_apoyo(resultado):
    if isinstance(resultado, str):
        resultado = json.loads(resultado)
    if (not isinstance(resultado, dict) or set(resultado) != {"mensaje", "ejemplo"}
            or not isinstance(resultado["mensaje"], str)
            or not 1 <= len(resultado["mensaje"].strip()) <= 1200
            or resultado["ejemplo"] is not None):
        raise ValueError("Se esperaba una pista breve sin solución ni ejemplo resuelto.")
    return {"mensaje": resultado["mensaje"].strip(), "ejemplo": None}


def registrar_fase1(app, df, evaluar, recomendar=None, prescribir=None, generar_apoyo=None,
                    *, planificador=None):
    explorador = Explorador(df)
    sesiones, lock = OrderedDict(), threading.RLock()
    app.extensions["fase1"] = {"explorador": explorador, "sesiones": sesiones, "lock": lock}

    def recuperar():
        token = request.headers.get("X-SiGAD-Session", "")
        if token not in sesiones:
            raise KeyError("La sesión venció. Inicia una nueva sesión.")
        s = sesiones[token]
        s["ultima_actividad"] = time.monotonic()
        sesiones.move_to_end(token)
        return s

    def estado(s):
        return {"tarea": s["tarea"], "revision": s["revision"], "completada": s["completada"],
                "contexto": s["contexto"], "motor": s["motor"].resumen(),
                "guidance": s.get("apoyo") or guidance(s["contexto"], s["motor"].nivel),
                "resultado": s.get("resultado"), "objetivo": s.get("objetivo"),
                "avanzado": s.get("avanzado"), "lightva": planificador is not None,
                "plan_lightva": s.get("plan_lightva") if s.get("plan_vigente") else None}

    def contexto_recomendacion(s):
        seleccionadas = list(s['contexto'].get('variables', [s['contexto']['variable']]))
        if s["contexto"].get("secundaria"):
            seleccionadas.append(s["contexto"]["secundaria"])
        if s['contexto']['vista'] == 'comparacion':
            seleccionadas.append(s['contexto']['variable'])
        seleccionadas = list(dict.fromkeys(seleccionadas))
        return {"seleccion": copy.deepcopy(s["contexto"]), "temporal": explorador.perfil["temporal"],
                "variables_disponibles": [v["columna"] for v in explorador.perfil["variables"]],
                "roles": dict(explorador.roles),
                "operaciones_disponibles": explorador.opciones(s["contexto"]["variable"]),
                "espacial": explorador.perfil["espacial"],
                "variables_seleccionadas": seleccionadas,
                "grado_seleccionado": s["motor"].nivel,
                "dominio": s["motor"].resumen()["habilidades"],
                "evaluacion": copy.deepcopy(s.get("resultado")),
                "respuesta_usuario": s.get("ultima_respuesta"),
                "historial_ayuda": [copy.deepcopy(e) for e in s["eventos"]
                    if e["tarea"] == s["tarea"] and e["tipo"] in
                    ("ayuda", "timeout", "apoyo_generado")][-5:],
                "restricciones": ["Respetar el grado seleccionado; no modificar BKT.",
                                  "Usar únicamente variables y cobertura disponibles."],
                "nota_grafico": explorador.grafico(s["contexto"]["variable"],
                                                    s["contexto"]["vista"],
                                                    s["contexto"].get("secundaria"),
                                                    s['contexto'].get('variables'))["nota"]}

    @app.get('/api/fase1/perfil')
    def perfil_f1():
        return jsonify(explorador.perfil)

    @app.get('/api/fase1/grafico')
    def grafico_f1():
        try:
            columnas = request.args.getlist('variables') if 'variables' in request.args else None
            if columnas == ['']:
                columnas = []
            return jsonify(explorador.grafico(request.args.get("variable"), request.args.get("vista"), request.args.get("secundaria"), columnas))
        except ValueError as e:
            return jsonify(error=str(e)), 400

    @app.post('/api/fase1/sesion')
    def sesion_f1():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error="Solicitud inválida."), 400
        try:
            contexto = contexto_valido(datos, explorador)
        except ValueError as e:
            return jsonify(error=str(e)), 400
        with lock:
            ahora = time.monotonic()
            for key in list(sesiones):
                if ahora - sesiones[key]["ultima_actividad"] > 24*3600:
                    del sesiones[key]
            token = str(uuid.uuid4())
            s = {"motor": MotorFase1(**app.config.get("FASE1_BKT", {})), "tarea": str(uuid.uuid4()), "contexto": contexto,
                 "revision": 0, "completada": False, "eventos": [], "respuestas": {},
                 "ocupada": False, "ultima_actividad": ahora}
            sesiones[token] = s
            if len(sesiones) > 500:
                sesiones.popitem(last=False)
            return jsonify(sesion=token, **estado(s))

    @app.get('/api/fase1/estado')
    def estado_f1():
        with lock:
            try:
                return jsonify(estado(recuperar()))
            except KeyError:
                return jsonify(error="La sesión venció. Inicia una nueva sesión."), 404

    @app.post('/api/fase1/accion')
    def accion_f1():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error="Solicitud inválida."), 400
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error="Sesión no encontrada."), 404
            if s["ocupada"] or datos.get("revision") != s["revision"]:
                return jsonify(error="La sesión cambió. Actualiza e intenta nuevamente."), 409
            accion = datos.get("accion")
            if planificador is not None and not s.get("resultado") and accion in ("ayuda", "prescribir", "timeout"):
                return jsonify(estado(s))
            if accion == "ayuda" and not s["completada"]:
                s["motor"].ayuda()
                s["eventos"].append({"tipo": "ayuda", "tarea": s["tarea"], "nivel": s["motor"].nivel})
            elif accion == "prescribir" and not s["completada"]:
                s["motor"].prescribir()
                s["eventos"].append({"tipo": "salto_a_prescribir", "tarea": s["tarea"], "nivel": 4})
            elif accion == "timeout" and not s["completada"] and s["motor"].nivel < 4:
                nivel_anterior = s["motor"].nivel
                actualizado = s["motor"].registrar_timeout(s["tarea"])
                if planificador is not None and not actualizado:
                    return jsonify(estado(s))
                if actualizado:
                    s["eventos"].append({"tipo": "timeout", "tarea": s["tarea"],
                                         "nivel": nivel_anterior,
                                         "bkt": s["motor"].resumen()})
            elif accion == "contexto" and not s["completada"]:
                try:
                    s["contexto"] = contexto_valido(datos, explorador)
                except ValueError as e:
                    return jsonify(error=str(e)), 400
                # El apoyo recibido se conserva al cambiar el gráfico.
                s.pop("opciones", None)
                s.pop("avanzado", None)
            elif accion == "nueva" and s["completada"]:
                s["motor"].nueva_tarea(verificacion=datos.get("verificacion") is True)
                s["tarea"], s["completada"] = str(uuid.uuid4()), False
                s.pop("resultado", None)
                s.pop("ultima_respuesta", None)
                s.pop("objetivo", None)
                s.pop("opciones", None)
                s.pop("avanzado", None)
                s.pop("plan_lightva", None)
            elif accion == "completar_subtarea" and not s["completada"] and s.get("plan_vigente"):
                identificador = datos.get("subtarea")
                respuesta = datos.get("respuesta")
                if not isinstance(respuesta, str) or not respuesta.strip() or len(respuesta) > 4000:
                    return jsonify(error="Escribe la respuesta a la subtarea (máximo 4000 caracteres)."), 400
                plan = s["plan_lightva"]
                activas = {sub["id"]: sub for sub in plan["subtareas"] if not sub["motivo_invalidacion"]}
                subtarea = activas.get(identificador) if isinstance(identificador, str) else None
                if not subtarea or subtarea["estado"] != "pendiente":
                    return jsonify(error="La subtarea ya no está pendiente o no se encuentra disponible."), 409
                if any(activas.get(dep, {}).get("estado") != "completada" for dep in subtarea["dependencias"]):
                    return jsonify(error="Completa primero los pasos previos."), 409
                subtarea.update(estado="completada", respuesta=respuesta.strip())
                s["revision"] += 1
                return jsonify(estado(s))
            else:
                return jsonify(error="Acción no disponible en esta tarea."), 400
            s.pop("apoyo", None)
            s.pop("plan_vigente", None)
            s["revision"] += 1
            return jsonify(estado(s))

    @app.post('/api/fase1/apoyo')
    def apoyo_f1():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error="Solicitud inválida."), 400
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error="Sesión no encontrada."), 404
            if s["ocupada"] or datos.get("revision") != s["revision"]:
                return jsonify(error="La sesión cambió. Actualiza e intenta nuevamente."), 409
            if planificador is not None:
                if s["completada"] or not s.get("resultado") or s["motor"].nivel == 1 or s.get("plan_vigente"):
                    return jsonify(estado(s))
                contexto = contexto_recomendacion(s)
                criterios = (contexto["evaluacion"] or {}).get("criterios", {})
                pendientes = [f"{clave}: {valor['explicacion']}" for clave, valor in criterios.items()
                              if valor["puntuacion"] < 2]
                if not pendientes:
                    pendientes = ["Todavía no hay una evaluación con criterios pendientes. Ayuda a formular la pregunta desde la exploración actual."]
                exploraciones = [contexto["nota_grafico"]] if contexto["nota_grafico"] else []
                espacial = contexto["espacial"]
                if espacial["registros_validos"]:
                    exploraciones.append(
                        f"Coordenadas candidatas: {espacial['latitud']}, {espacial['longitud']}. "
                        f"Hay {espacial['registros_validos']} registros con coordenadas válidas. {espacial['nota']}"
                    )
                entrada = {
                    "nivel": s["motor"].nivel,
                    "variables": contexto["variables_seleccionadas"],
                    "vista": contexto["seleccion"]["vista"],
                    "exploraciones": exploraciones,
                    "respuesta": contexto["respuesta_usuario"],
                    "dificultades": pendientes,
                    "anterior": copy.deepcopy(s.get("plan_lightva")),
                }
            else:
                if s["completada"] or s["motor"].nivel != 2 or s.get("apoyo") or generar_apoyo is None:
                    return jsonify(estado(s))
                contexto = contexto_recomendacion(s)
            s["ocupada"] = True
        try:
            if planificador is not None:
                plan = planificador(**entrada)
                apoyo = {"mensaje": plan["intervencion"], "plan": copy.deepcopy(plan)}
            else:
                apoyo = validar_apoyo(generar_apoyo(contexto))
        except Exception:
            with lock:
                s["ocupada"] = False
            return jsonify(error="No se pudo generar una ayuda válida. Reintenta; BKT no cambió."), 502
        with lock:
            s["ocupada"] = False
            s["apoyo"] = apoyo
            if planificador is not None:
                s["plan_lightva"] = plan
                s["plan_vigente"] = True
            s["eventos"].append({"tipo": "apoyo_generado", "tarea": s["tarea"],
                                 "nivel": s["motor"].nivel, "contenido": copy.deepcopy(apoyo)})
            s["revision"] += 1
            return jsonify(estado(s))

    @app.post('/api/fase1/apoyo-avanzado')
    def apoyo_avanzado_f1():
        if planificador is not None:
            return apoyo_f1()
        datos = request.get_json(silent=True) or {}
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error="Sesión no encontrada."), 404
            if s["completada"]:
                return jsonify(estado(s))
            if s["motor"].nivel < 3:
                return jsonify(error="El apoyo avanzado todavía no corresponde."), 400
            if s["ocupada"] or datos.get("revision") != s["revision"]:
                return jsonify(error="La sesión cambió. Actualiza e intenta nuevamente."), 409
            if s.get("avanzado") and (s["motor"].nivel == 3 or s["avanzado"].get("modo") == "prescribir"):
                return jsonify(estado(s))
            if recomendar is None or (s["motor"].nivel == 4 and prescribir is None):
                return jsonify(error="El generador de recomendaciones no está configurado."), 503
            s["ocupada"] = True
            contexto = contexto_recomendacion(s)
            opciones_existentes = copy.deepcopy(s.get("opciones"))
            nivel = s["motor"].nivel
        try:
            opciones = opciones_existentes or validar_recomendaciones(recomendar(contexto), explorador.df.columns)
            receta = validar_prescripcion(prescribir(opciones, contexto)) if nivel == 4 else None
        except Exception:
            with lock:
                s["ocupada"] = False
            return jsonify(error="No se pudieron generar recomendaciones válidas. Reintenta; BKT no cambió."), 502
        with lock:
            s["ocupada"] = False
            s["opciones"] = opciones
            if nivel == 3:
                s["avanzado"] = {"modo": "dirigir", "opciones": opciones}
            else:
                opcion = opciones[receta["indice"]]
                s["avanzado"] = {"modo": "prescribir", "opcion": opcion,
                                  "explicacion": receta["explicacion"]}
                s["completada"] = True
                s["objetivo"] = {"pregunta": opcion["pregunta"], "variables": opcion["variables"],
                                 "origen": "prescrita", "contexto": s["contexto"]}
                s["eventos"].append({"tipo": "prescripcion", "tarea": s["tarea"],
                                     "nivel": 4, "objetivo": s["objetivo"]})
            s["revision"] += 1
            return jsonify(estado(s))

    @app.post('/api/fase1/seleccionar-opcion')
    def seleccionar_opcion_f1():
        datos = request.get_json(silent=True) or {}
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error="Sesión no encontrada."), 404
            indice = datos.get("indice")
            opciones = s.get("opciones")
            if (s["ocupada"] or s["completada"] or s["motor"].nivel != 3 or
                    datos.get("revision") != s["revision"]):
                return jsonify(error="La tarea cambió o la selección ya no está disponible."), 409
            if type(indice) is not int or not opciones or indice not in range(4):
                return jsonify(error="Selecciona una de las cuatro preguntas."), 400
            opcion = opciones[indice]
            s["completada"] = True
            s["objetivo"] = {"pregunta": opcion["pregunta"], "variables": opcion["variables"],
                             "origen": "sugerida", "contexto": s["contexto"]}
            s["avanzado"] = {"modo": "dirigir", "opciones": opciones, "seleccion": indice}
            s["eventos"].append({"tipo": "seleccion_asistida", "tarea": s["tarea"],
                                 "nivel": 3, "objetivo": s["objetivo"]})
            # Elegir una pregunta generada no constituye una observación correcta de BKT.
            s["revision"] += 1
            return jsonify(estado(s))

    @app.post('/api/fase1/evaluar')
    def evaluar_f1():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error="Solicitud inválida."), 400
        intento = datos.get("intento")
        if not isinstance(intento, str) or not 1 <= len(intento) <= 100:
            return jsonify(error="Identificador de intento inválido."), 400
        campos = ("pregunta",)
        if any(not isinstance(datos.get(c), str) or not datos[c].strip() or len(datos[c]) > 4000 for c in campos):
            return jsonify(error="Escribe una pregunta de análisis (máximo 4000 caracteres)."), 400
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error="Sesión no encontrada."), 404
            if intento in s["respuestas"]:
                return jsonify(s["respuestas"][intento])
            if s["ocupada"] or datos.get("revision") != s["revision"] or s["completada"]:
                return jsonify(error="La tarea cambió o ya fue completada."), 409
            if 'variables' in s['contexto'] and (not s['contexto']['variables'] or (s['contexto']['vista'] == 'relaciones' and len(s['contexto']['variables']) < 2)):
                return jsonify(error='Selecciona al menos una variable para evaluar tu pregunta.'), 400
            s["ocupada"] = True
            contexto = copy.deepcopy(s["contexto"])
            contexto["tarea"] = {"id": s["tarea"], "fase": "Problema",
                "consigna": "Formula una pregunta de análisis: propósito, variables y alcance, respondible con los datos disponibles."}
            contexto["rubrica"] = {"version": "fase1-v1", "criterios": dict(RUBRICA),
                                   "escala": {"0": "ausente o incorrecto", "1": "parcial", "2": "adecuado"}}
            contexto["ayuda_recibida"] = {"grado": s["motor"].nivel,
                "autonoma": s["motor"].nivel == 1,
                "contenido": copy.deepcopy(s.get("apoyo") or guidance(s["contexto"], s["motor"].nivel)),
                "avanzado": copy.deepcopy(s.get("avanzado")),
                "plan_lightva": copy.deepcopy(s.get("plan_lightva")) if s.get("plan_vigente") else None}
            contexto["ayuda_recibida"]["historial"] = [copy.deepcopy(e)
                for e in s["eventos"] if e["tarea"] == s["tarea"] and
                e["tipo"] in ("ayuda", "timeout", "apoyo_generado")][-5:]
            contexto["historial"] = [
                {"respuesta": e["respuesta"], "evaluacion": e["evaluacion"], "grado": e["nivel"]}
                for e in s["eventos"] if e["tipo"] == "evaluacion" and e["tarea"] == s["tarea"]
            ][-5:]
        try:
            # La rúbrica necesita estructura y cobertura, no todos los puntos del
            # gráfico. Mantener el contexto compacto reduce tokens, latencia y
            # errores del proveedor en vistas de dispersión con cientos de marcas.
            contexto["perfil"] = {
                "temporal": explorador.perfil["temporal"],
                "variables": [
                    {"columna": v["columna"], "nombre": v["nombre"],
                     "grupo": v["grupo"], "numerica": v["numerica"], "rol": v["rol"],
                     "faltantes": v["faltantes"], "faltantes_porcentaje": v["faltantes_porcentaje"]}
                    for v in explorador.perfil["variables"]
                ],
            }
            grafico = explorador.grafico(
                contexto["variable"], contexto["vista"], contexto["secundaria"], contexto.get('variables')
            )
            contexto["grafico"] = {
                "vista": grafico["vista"], "variable": grafico["variable"],
                "secundaria": grafico["secundaria"], "nota": grafico["nota"],
                "cantidad_marcas": len(grafico["puntos"]),
                'variables': grafico.get('variables', [grafico['variable']]),
                'cantidad_paneles': len(grafico.get('paneles', [])),
                'paneles': [{'variable': p['variable'], 'secundaria': p.get('secundaria'),
                             'cantidad_marcas': len(p['puntos']), 'nota': p['nota']}
                            for p in grafico.get('paneles', [])],
            }
            contexto["operaciones_disponibles"] = explorador.opciones(contexto["variable"])
            contexto["espacial"] = explorador.perfil["espacial"]
            evaluacion = validar_evaluacion(evaluar({k: datos[k].strip() for k in campos}, contexto), explorador.df.columns)
        except Exception as error:
            status = getattr(error, "status_code", None)
            app.logger.warning("Falló la evaluación de la fase 1: %s (HTTP %s)",
                               type(error).__name__, status)
            with lock:
                s["ocupada"] = False
            if isinstance(error, CredencialGroqAusente):
                return jsonify(error="Falta la clave de Groq. Configura GROQ_API_KEY u OPENAI_API_KEY "
                                     "en .env y reinicia SiGAD.", codigo="proveedor_sin_clave"), 503
            if status in (401, 403):
                return jsonify(error="Groq rechazó el acceso. Revisa la clave y los permisos del modelo.",
                               codigo="proveedor_autenticacion"), 502
            if status == 429:
                return jsonify(error="La IA alcanzó su límite de uso. Tu pregunta sigue en el formulario. "
                                     "Puedes reintentar cuando se restablezca la cuota.",
                               codigo="proveedor_limite"), 429
            if type(error).__name__ in ("APITimeoutError", "TimeoutError"):
                return jsonify(error="La IA tardó demasiado en responder. Puedes reintentar con la misma pregunta.",
                               codigo="proveedor_tiempo"), 504
            if type(error).__name__ in ("APIConnectionError", "ConnectionError"):
                return jsonify(error="No se pudo conectar con la IA. Comprueba la conexión y reintenta.",
                               codigo="proveedor_conexion"), 502
            return jsonify(error="No se pudo obtener una evaluación válida. Reintenta; tu nivel y BKT no cambiaron."), 502
        with lock:
            s["ocupada"] = False
            completada, nivel = s["motor"].registrar(
                s["tarea"], intento,
                {k: v["puntuacion"] for k, v in evaluacion["criterios"].items()},
            )
            s["completada"], s["resultado"] = completada, evaluacion
            s["ultima_respuesta"] = datos["pregunta"].strip()
            s.pop("apoyo", None)
            if not completada:
                s.pop("plan_vigente", None)
            s["eventos"].append({"tipo": "evaluacion", "tarea": s["tarea"], "intento": intento,
                                 "nivel": nivel, "respuesta": {k: datos[k] for k in campos},
                                 "entrada": contexto,
                                 "evaluacion": evaluacion, "bkt": s["motor"].resumen()})
            if completada:
                contexto_previo = copy.deepcopy(s['contexto'])
                vista_sugerida = evaluacion["vista_sugerida"]
                variable_actual = s["contexto"]["variable"]
                opciones_vista = explorador.opciones(variable_actual)
                if vista_sugerida not in {"relaciones", "comparacion"} and opciones_vista[vista_sugerida]["disponible"]:
                    s["contexto"] = {"variable": variable_actual,
                                      "vista": vista_sugerida, "secundaria": None}
                    if vista_sugerida == 'evolucion':
                        s['contexto']['variables'] = list(contexto.get('variables', [variable_actual]))
                elif vista_sugerida in {"relaciones", "comparacion"}:
                    utilizadas = evaluacion["variables_utilizadas"]
                    pares = opciones_vista[vista_sugerida].get("pares", [])
                    secundaria = next((v for v in utilizadas
                                       if v != variable_actual and v in pares), None)
                    if secundaria:
                        s["contexto"] = {"variable": variable_actual,
                                          "vista": vista_sugerida,
                                          "secundaria": secundaria}
                if s['contexto']['vista'] == contexto_previo['vista'] and 'variables' in contexto_previo:
                    s['contexto'] = contexto_previo
                s["objetivo"] = {"pregunta": evaluacion["pregunta_formulada"].strip(),
                                 "pregunta_original": datos["pregunta"].strip(),
                                 "origen": "usuario"}
                s["objetivo"]["variables"] = evaluacion["variables_utilizadas"]
                s["objetivo"]["contexto"] = copy.deepcopy(s["contexto"])
            s["revision"] += 1
            result = estado(s)
            s["respuestas"][intento] = copy.deepcopy(result)
            return jsonify(result)
