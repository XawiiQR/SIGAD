from flask import Flask, jsonify, request, send_from_directory
import pandas as pd
import numpy as np
import os
from pathlib import Path
from functools import lru_cache

from agente import MotorAnalisis
from fase1 import registrar_fase1
from fase3 import registrar_fase3
from fase2 import registrar_fase2
from experimento_lightva import registrar_experimento
from lightva_fase1 import perfilar_datos, planificar

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
FRONT_DIR = BASE_DIR / "front"
COLUMNAS_NO_ANALITICAS = {"no", "id", "year", "month", "day", "hour"}

# Asegúrate de que esta ruta sea la correcta para tu archivo
CSV_PATH = Path(os.environ.get("SIGAD_CSV_PATH", "Data/Data.csv"))
if not CSV_PATH.is_absolute():
    CSV_PATH = BASE_DIR / CSV_PATH
if not CSV_PATH.is_file():
    raise FileNotFoundError(f"No se encontró el dataset: {CSV_PATH}. Configura SIGAD_CSV_PATH.")
df = pd.read_csv(CSV_PATH)


def evaluar_problema(respuesta, contexto):
    return MotorAnalisis().evaluar_problema_fase1(respuesta, contexto)


@lru_cache(maxsize=1)
def perfil_lightva_fase1():
    return perfilar_datos(df)


def planificar_problema(nivel, **contexto):
    plan, _ = planificar(perfil_lightva_fase1(), nivel, **contexto)
    return plan


registrar_fase1(app, df, evaluar_problema, planificador=planificar_problema)


def evaluar_plan(propuesta, entrada):
    return MotorAnalisis().evaluar_plan_fase2(propuesta, entrada)


def generar_apoyo_plan(entrada):
    return MotorAnalisis().generar_apoyo_plan_fase2(entrada)


registrar_fase2(app, evaluar_plan, generar_apoyo_plan)
registrar_fase3(app)
registrar_experimento(app, df, CSV_PATH.name)


@app.after_request
def permitir_frontend_externo(response):
    """Permite probar el frontend desde Live Server o una vista previa del IDE."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    if request.path.startswith("/front/") or request.path == "/":
        response.headers["Cache-Control"] = "no-store"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-SiGAD-Session, X-SiGAD-Phase2, X-SiGAD-Phase3"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def ejecutar_llm(funcion):
    """Ejecuta una acción del agente y convierte errores en respuestas JSON."""
    try:
        return jsonify({"respuesta": funcion()})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route('/', methods=['GET'])
def inicio():
    return send_from_directory(FRONT_DIR, 'index.html')


@app.route('/front/<path:archivo>', methods=['GET'])
def archivos_front(archivo):
    return send_from_directory(FRONT_DIR, archivo)

@app.route('/api/tarjeta-identidad', methods=['GET'])
def get_tarjeta():
    
    # 2. Calcular el peso del archivo en MB
    tamano_bytes = os.path.getsize(CSV_PATH)
    peso_mb = round(tamano_bytes / (1024 * 1024), 2)
    
    # 3. Lógica para detectar fecha
    cobertura = "No determinado"
    cols_fecha = ['year', 'month', 'day']
    
    if all(col in df.columns for col in cols_fecha):
        try:
            fechas = pd.to_datetime(df[cols_fecha])
            cobertura = f"{fechas.min().date()} a {fechas.max().date()}"
        except:
            pass
    else:
        for col in df.columns:
            if 'date' in col.lower() or 'time' in col.lower():
                try:
                    fechas = pd.to_datetime(df[col])
                    cobertura = f"{fechas.min().date()} a {fechas.max().date()}"
                    break
                except:
                    continue

    # 4. Retornar JSON completo
    return jsonify({
        "filas": int(df.shape[0]),
        "columnas": int(df.shape[1]),
        "peso_mb": peso_mb,
        "cobertura_temporal": cobertura
    })

# Supongamos que ya tienes cargado tu dataframe aquí


@app.route('/api/diagnostico-calidad', methods=['GET'])
def diagnostico_calidad():
    # 1. Nulos
    nulos_detalle = df.isnull().sum()
    nulos_dict = nulos_detalle[nulos_detalle > 0].to_dict()
    nulos_porcentaje = (
        (nulos_detalle[nulos_detalle > 0] / len(df) * 100).round(2).to_dict()
    )
    
    # 2. Outliers (Método IQR)
    outliers_dict = {}
    numericas = [
        col for col in df.select_dtypes(include=[np.number]).columns
        if col.lower() not in COLUMNAS_NO_ANALITICAS
    ]
    for col in numericas:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        count = df[(df[col] < lower_bound) | (df[col] > upper_bound)].shape[0]
        if count > 0:
            outliers_dict[col] = int(count)

    # 3. Estructura Temporal
    cols_necesarias = {'year', 'month', 'day', 'hour'}
    if cols_necesarias.issubset(df.columns):
        estado_temporal = {"formato": "separado , necesita transformacion", "columnas": list(cols_necesarias)}
    else:
        estado_temporal = {"formato": "completo"}

    return jsonify({
        "filas": int(df.shape[0]),
        "nulos": nulos_dict,
        "nulos_porcentaje": nulos_porcentaje,
        "outliers": outliers_dict,
        "tipos_variables": df.dtypes.astype(str).to_dict(),
        "estructura_temporal": estado_temporal
    })

@app.route('/api/taxonomia-variables', methods=['GET'])
def taxonomia_variables():
    taxonomia = {
        "temporales": [],
        "numericas": [],
        "categoricas": []
    }
    
    for col in df.columns:
        # Lógica simple de clasificación
        if col.lower() in ['year', 'month', 'day', 'hour', 'date', 'time']:
            taxonomia["temporales"].append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            taxonomia["numericas"].append(col)
        else:
            taxonomia["categoricas"].append(col)
            
    return jsonify(taxonomia)


@app.route('/api/analisis-escalado-transformacion', methods=['GET'])
def analisis_escalado_transformacion():
    """Resumen matemático de Pandas; no transforma ninguna columna."""
    objetivo = str(request.args.get("objetivo", "")).lower()
    # Se revisan todas las variables numéricas analíticas. Se excluyen índices y
    # componentes de fecha porque no son medidas comparables para normalización.
    columnas = [
        col for col in df.select_dtypes(include=[np.number]).columns
        if col.lower() not in COLUMNAS_NO_ANALITICAS
    ]

    resumen = {}
    for col in columnas:
        serie = df[col].dropna()
        if serie.empty:
            continue
        minimo = float(serie.min())
        maximo = float(serie.max())
        resumen[col] = {
            "min": round(minimo, 4),
            "max": round(maximo, 4),
            "rango": round(maximo - minimo, 4),
            "desviacion_estandar": round(float(serie.std()), 4),
        }

    rangos = [item["rango"] for item in resumen.values() if item["rango"] > 0]
    relacion_rangos = round(max(rangos) / min(rangos), 4) if rangos else 1
    amerita_escalado = len(resumen) >= 2 and relacion_rangos >= 10
    columnas_fecha_separadas = [
        col for col in ["year", "month", "day", "hour"] if col in df.columns
    ]
    columnas_fecha_texto = [
        col for col in df.columns
        if ("date" in col.lower() or "fecha" in col.lower() or "time" in col.lower())
        and pd.api.types.is_object_dtype(df[col])
    ]
    columnas_temporales = columnas_fecha_separadas or columnas_fecha_texto
    requiere_transformacion_temporal = bool(columnas_temporales)
    return jsonify({
        "objetivo_fase1": objetivo or "No especificado",
        "variables_numericas_evaluadas": list(resumen),
        "variables_excluidas_por_ser_indice_o_temporales": sorted(
            col for col in df.columns if col.lower() in COLUMNAS_NO_ANALITICAS
        ),
        "resumen_estadistico": resumen,
        "relacion_maxima_de_rangos": relacion_rangos,
        "amerita_escalado_si_se_combinan_variables": amerita_escalado,
        "interpretacion": (
            "Las variables evaluadas tienen escalas muy diferentes; el escalado "
            "debe considerarse si se usan conjuntamente en métodos sensibles a escala."
            if amerita_escalado
            else "No se detectó una diferencia de escala que obligue a escalar; "
            "la decisión depende del método analítico posterior."
        ),
        "nota_transformacion": (
            "Se recomienda construir una variable datetime a partir de las "
            f"columnas {', '.join(columnas_fecha_separadas)} para análisis temporal."
            if columnas_fecha_separadas
            else (
                "Las columnas temporales de texto requieren conversión a datetime: "
                f"{', '.join(columnas_fecha_texto)}."
                if columnas_fecha_texto
                else "No se detectaron columnas temporales que requieran una "
                "transformación evidente."
            )
        ),
        "requiere_transformacion_temporal": requiere_transformacion_temporal,
        "columnas_temporales_a_transformar": columnas_temporales,
    })


@app.route('/api/validar-pregunta', methods=['POST', 'OPTIONS'])
def validar_pregunta():
    if request.method == 'OPTIONS':
        return '', 204
    datos = request.get_json(silent=True) or {}
    pregunta = str(datos.get("pregunta", "")).strip()
    if not pregunta:
        return jsonify({"error": "La pregunta es obligatoria."}), 400

    motor = MotorAnalisis()
    return ejecutar_llm(lambda: motor.validar_pregunta_F1_1(pregunta))


@app.route('/api/describir-variables', methods=['GET'])
def describir_variables():
    motor = MotorAnalisis()
    return ejecutar_llm(motor.generar_descripcion_variables)


@app.route('/api/preguntas-sugeridas', methods=['GET'])
def preguntas_sugeridas():
    motor = MotorAnalisis()
    return ejecutar_llm(motor.generar_tres_preguntas_sugeridas)


@app.route('/api/prescribir-pregunta', methods=['POST', 'OPTIONS'])
def prescribir_pregunta():
    if request.method == 'OPTIONS':
        return '', 204
    datos = request.get_json(silent=True) or {}
    preguntas = datos.get("preguntas", [])
    if not isinstance(preguntas, list) or len(preguntas) != 3:
        return jsonify({"error": "Se requieren exactamente tres preguntas."}), 400

    motor = MotorAnalisis()
    return ejecutar_llm(lambda: motor.prescribir_pregunta(preguntas))


# Los endpoints anteriores permitían que el cliente y el LLM decidieran el grado.
# El flujo actual exige una sesión y usa /evaluar, /accion, /apoyo y /seleccionar.
@app.route('/api/fase2/evaluar-estrategia', methods=['POST', 'OPTIONS'])
@app.route('/api/fase2/explicar-alternativa-correcta', methods=['POST', 'OPTIONS'])
def fase2_endpoint_anterior():
    if request.method == 'OPTIONS':
        return '', 204
    return jsonify(error="Este endpoint fue sustituido por el flujo de sesiones de fase 2.",
                   sesion="/api/fase2/sesion", evaluar="/api/fase2/evaluar"), 410


# ─────────────────────────────────────────────
# FASE 3 — Preparación de datos
# Subprocesos: Fase3Nulos, Fase3Outlier, Fase3Normalizacion y Fase3Transformacion
# ─────────────────────────────────────────────

def _calcular_analisis_nulos(columna: str) -> dict:
    """Devuelve estadísticas Pandas + impacto mecánico de las 4 opciones de tratamiento.
    No llama al LLM; solo calcula. El agente es quien envía esto al LLM."""
    if columna not in df.columns:
        raise ValueError(f"La columna '{columna}' no existe en el dataset.")

    serie = df[columna]
    total = int(len(serie))
    nulos = int(serie.isnull().sum())
    es_numerica = pd.api.types.is_numeric_dtype(serie)

    if nulos == 0:
        return {"columna": columna, "tipo": "numerica" if es_numerica else "texto/categorica",
                "total_filas": total, "nulos": 0,
                "mensaje": "Sin valores nulos. No requiere tratamiento."}

    pct_nulos = round(nulos / total * 100, 2)
    serie_limpia = serie.dropna()

    if es_numerica:
        media = round(float(serie_limpia.mean()), 4)
        mediana = round(float(serie_limpia.median()), 4)
        desv_std = round(float(serie_limpia.std()), 4)
        asimetria = round(float(serie_limpia.skew()), 4)

        Q1 = float(serie_limpia.quantile(0.25))
        Q3 = float(serie_limpia.quantile(0.75))
        iqr = Q3 - Q1
        lower = Q1 - 1.5 * iqr
        upper = Q3 + 1.5 * iqr
        outliers = int(((serie_limpia < lower) | (serie_limpia > upper)).sum())
        opcion_3 = {
            "descripcion": "Rellenar los vacíos con la media de la columna",
            "valor_a_usar": media,
            "outliers_que_distorsionan_media": outliers,
            "riesgo_distorsion": "alto" if outliers > 0 or abs(asimetria) > 1 else "bajo",
        }
        opcion_4 = {
            "descripcion": "Rellenar los vacíos con la mediana de la columna",
            "valor_a_usar": mediana,
            "robusta_frente_a_outliers": True,
            "riesgo_distorsion": "bajo",
        }
    else:
        moda = serie_limpia.mode().iloc[0] if not serie_limpia.mode().empty else "No disponible"
        media = mediana = desv_std = "No aplica"
        asimetria = 0.0
        outliers = 0
        opcion_3 = {
            "descripcion": "Rellenar los vacíos con la categoría más frecuente",
            "valor_a_usar": str(moda),
            "outliers_que_distorsionan_media": 0,
            "riesgo_distorsion": "bajo",
        }
        opcion_4 = {
            "descripcion": "Rellenar los vacíos con la categoría 'Desconocido'",
            "valor_a_usar": "Desconocido",
            "robusta_frente_a_outliers": True,
            "riesgo_distorsion": "bajo",
        }

    return {
        "columna": columna,
        "tipo": "numerica" if es_numerica else "texto/categorica",
        "total_filas": total,
        "nulos": nulos,
        "porcentaje_nulos": pct_nulos,
        "estadisticas": {
            "media": media,
            "mediana": mediana,
            "desviacion_estandar": desv_std,
            "asimetria": asimetria,
            "distribucion_sesgada": es_numerica and abs(asimetria) > 1,
            "outliers_detectados": outliers,
        },
        "opciones": {
            "1_eliminar_filas": {
                "descripcion": f"Eliminar las {nulos} filas que tienen vacíos en '{columna}'",
                "filas_perdidas": nulos,
                "porcentaje_dataset_perdido": pct_nulos,
                "columnas_perdidas": 0,
            },
            "2_eliminar_columna": {
                "descripcion": f"Eliminar toda la columna '{columna}' del dataset",
                "filas_perdidas": 0,
                "columnas_perdidas": 1,
                "valores_disponibles_sacrificados": total - nulos,
            },
            "3_imputar_media": opcion_3,
            "4_imputar_mediana": opcion_4,
        },
    }


@app.route('/api/fase3/analizar-nulos-columna', methods=['GET'])
def analizar_nulos_columna_f3():
    """Devuelve el análisis mecánico (Pandas) de una columna con nulos.
    El LLM NO está involucrado aquí; solo se calculan estadísticas."""
    columna = request.args.get('columna', '').strip()
    if not columna:
        return jsonify({"error": "El parámetro 'columna' es obligatorio."}), 400
    try:
        return jsonify(_calcular_analisis_nulos(columna))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404

@app.route('/api/fase3/evaluar-tratamiento-nulos', methods=['POST', 'OPTIONS'])
def evaluar_tratamiento_nulos_fase3():
    """Recibe una columna, calcula sus metadatos y los envía al LLM 
    para evaluar las 4 opciones de limpieza de nulos."""
    if request.method == 'OPTIONS':
        return '', 204
        
    datos = request.get_json(silent=True) or {}
    columna = str(datos.get("columna", "")).strip()
    
    if not columna:
        return jsonify({"error": "El nombre de la columna es obligatorio."}), 400
        
    motor = MotorAnalisis()
    return ejecutar_llm(lambda: motor.analizar_nulos_columna_fase3(columna))
@app.route('/api/fase3/analizar-batch-nulos', methods=['POST', 'OPTIONS'])
def analizar_batch_nulos_fase3():
    """Endpoint que recibe un lote de columnas y devuelve las estadísticas reales para el LLM."""
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        datos = request.get_json(silent=True) or {}
        columnas = datos.get("columnas", [])
        
        resultado_batch = {}
        for col in columnas:
            try:
                stats = _calcular_analisis_nulos(col)
                resultado_batch[col] = {
                    "tipo": stats["tipo"],
                    "total_filas": stats["total_filas"],
                    "nulos": stats["nulos"],
                    "porcentaje_nulos": stats.get("porcentaje_nulos", 0),
                    "media": stats["estadisticas"]["media"] if stats["nulos"] else "N/A",
                    "mediana": stats["estadisticas"]["mediana"] if stats["nulos"] else "N/A",
                    "outliers": stats["estadisticas"]["outliers_detectados"] if stats["nulos"] else 0,
                }
            except ValueError:
                resultado_batch[col] = {"error": "Columna no encontrada en el dataset"}
                
        return jsonify(resultado_batch)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/fase3/analizar-batch-outliers', methods=['POST', 'OPTIONS'])
def analizar_batch_outliers_endpoint():
    """Fase 3 — Outliers: identifica valores atípicos por IQR y devuelve los
    valores y filas afectados.

    ``registros_outliers`` contiene todos los casos detectados de cada columna;
    no solo su cantidad. Así el consumidor puede revisar exactamente qué dato fue
    marcado antes de decidir si lo recorta, transforma o conserva.
    """
    if request.method == 'OPTIONS':
        return '', 204
    try:
        data = request.get_json(silent=True) or {}
        columnas = data.get('columnas', [])

        if columnas and not isinstance(columnas, list):
            return jsonify({"error": "'columnas' debe ser una lista."}), 400

        global df
        if not columnas:
            columnas = [
                col for col in df.select_dtypes(include=[np.number]).columns
                if col.lower() not in COLUMNAS_NO_ANALITICAS
            ]

        resumen_batch = {}
        total_filas = len(df)
        
        for col in columnas:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                serie = df[col].dropna()
                total_validos = int(serie.size)
                if total_validos == 0:
                    resumen_batch[col] = {
                        "tipo": "Numérica",
                        "total_filas": total_filas,
                        "valores_validos": 0,
                        "outliers_count": 0,
                        "outliers_porcentaje": 0.0,
                        "registros_outliers": [],
                        "mensaje": "La columna no tiene valores numéricos válidos para evaluar.",
                    }
                    continue
                
                # Cálculo exacto por IQR
                Q1 = serie.quantile(0.25)
                Q3 = serie.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                outliers_mask = (serie < lower_bound) | (serie > upper_bound)
                outliers_count = int(outliers_mask.sum())
                outliers_porc = round((outliers_count / total_validos) * 100, 2)

                # Se conserva el índice original del DataFrame para poder ubicar
                # el registro directamente en el dataset.
                registros_outliers = [
                    {
                        "indice_fila": int(indice) if isinstance(indice, (int, np.integer)) else str(indice),
                        "valor": float(valor),
                    }
                    for indice, valor in serie[outliers_mask].items()
                ]
                
                # Cálculo de sesgo (Skewness)
                skew_val = round(float(serie.skew()), 2)
                
                resumen_batch[col] = {
                    "tipo": "Numérica",
                    "total_filas": total_filas,
                    "valores_validos": total_validos,
                    "outliers_count": outliers_count,
                    "outliers_porcentaje": outliers_porc,
                    "sesgo": skew_val,
                    "limites_iqr": {
                        "inferior": round(float(lower_bound), 4),
                        "superior": round(float(upper_bound), 4),
                    },
                    "min_val": round(float(serie.min()), 2),
                    "max_val": round(float(serie.max()), 2),
                    "registros_outliers": registros_outliers,
                }

            elif col not in df.columns:
                resumen_batch[col] = {"error": "Columna no encontrada en el dataset"}
            else:
                resumen_batch[col] = {"error": "La columna no es numérica"}

        return jsonify(resumen_batch), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/fase3/analizar-batch-normalizacion', methods=['POST', 'OPTIONS'])
def analizar_batch_normalizacion_endpoint():
    """Fase 3 — Normalización: resume variables numéricas para decidir su escalado.
    No modifica el DataFrame ni normaliza datos todavía."""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json(silent=True) or {}
        columnas = data.get('columnas', [])
        global df 
        
        # SI NO HAY COLUMNAS, TOMA TODAS LAS NUMÉRICAS DEL DATASET SOLITO
        if not columnas:
            columnas = [
                col for col in df.select_dtypes(include=['number']).columns
                if col.lower() not in COLUMNAS_NO_ANALITICAS
            ]
            
        columnas = [
            col for col in columnas
            if col in df.columns
            and pd.api.types.is_numeric_dtype(df[col])
            and col.lower() not in COLUMNAS_NO_ANALITICAS
        ]
        resumen_batch = {}
        
        for col in columnas:
            serie = df[col].dropna()
            if not serie.empty:
                resumen_batch[col] = {
                    "tipo": "Numérica",
                    "min": round(float(serie.min()), 4),
                    "max": round(float(serie.max()), 4),
                    "rango": round(float(serie.max() - serie.min()), 4),
                    "media": round(float(serie.mean()), 4),
                    "std": round(float(serie.std()), 4),
                }
        return jsonify(resumen_batch), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/fase3/transformar-tiempo', methods=['POST', 'OPTIONS'])
def transformar_tiempo_fase3():
    """Crea la columna ``datetime`` desde year, month, day y hour.
    Conserva las columnas fuente para que la operación sea trazable."""
    if request.method == 'OPTIONS':
        return '', 204

    columnas_requeridas = {"year", "month", "day", "hour"}
    faltantes = sorted(columnas_requeridas - set(df.columns))
    if faltantes:
        return jsonify({
            "error": "No se puede construir datetime; faltan columnas temporales.",
            "columnas_faltantes": faltantes,
        }), 400

    fecha_hora = pd.to_datetime(
        df[["year", "month", "day", "hour"]], errors="coerce"
    )
    df["datetime"] = fecha_hora
    invalidos = int(fecha_hora.isna().sum())
    validos = int(fecha_hora.notna().sum())

    return jsonify({
        "columna_creada": "datetime",
        "columnas_origen": ["year", "month", "day", "hour"],
        "filas_validas": validos,
        "filas_invalidas": invalidos,
        "inicio": fecha_hora.min().isoformat() if validos else None,
        "fin": fecha_hora.max().isoformat() if validos else None,
        "mensaje": "La columna datetime fue creada; las columnas originales se conservaron.",
    }), 200

if __name__ == '__main__':
    app.run(port=5000)
