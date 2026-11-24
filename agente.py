import requests
import json
import os
from openai import OpenAI
import prompts 
from dotenv import load_dotenv

# 1. Cargar configuración
load_dotenv()

class MotorAnalisis:
    def __init__(self):
        # La dirección base de tu servidor API
        self.base_url = "http://127.0.0.1:5000/api"
        self.client = OpenAI(base_url="https://api.groq.com/openai/v1")
        # Alternativa a GPT-OSS cuando ese modelo alcanza su cupo diario en Groq.
        self.modelo = "openai/gpt-oss-20b"

    def evaluar_problema_fase1(self, respuesta, contexto):
        """El LLM evalúa una rúbrica; el backend decide BKT y nivel de apoyo."""
        modelo = os.getenv("SIGAD_FASE1_MODEL") or self.modelo
        opciones = {"reasoning_effort": "low"} if modelo in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"} else {}
        resultado = self.client.with_options(max_retries=0).chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": prompts.PROMPT_RUBRICA_FASE1},
                {"role": "user", "content": prompts.obtener_prompt_rubrica_fase1(respuesta, contexto)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_completion_tokens=1200,
            timeout=20,
            **opciones,
        )
        return json.loads(resultado.choices[0].message.content)

    def generar_apoyo_problema_fase1(self, contexto):
        """Redacta una pista después de que la política selecciona Orientar."""
        resultado = self.client.chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": prompts.PROMPT_APOYO_FASE1},
                {"role": "user", "content": json.dumps({"contexto": contexto}, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"}, temperature=0.3, timeout=45,
        )
        return json.loads(resultado.choices[0].message.content)

    def generar_opciones_problema_fase1(self, contexto):
        """Genera las cuatro rutas del nivel Dirigir sin decidir el nivel."""
        resultado = self.client.chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": prompts.PROMPT_OPCIONES_FASE1},
                {"role": "user", "content": prompts.obtener_prompt_opciones_fase1(contexto)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            timeout=45,
        )
        return json.loads(resultado.choices[0].message.content)

    def prescribir_opcion_problema_fase1(self, opciones, contexto):
        """Selecciona una ruta cuando el motor ya activó Prescribir."""
        resultado = self.client.chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": prompts.PROMPT_PRESCRIPCION_FASE1},
                {"role": "user", "content": prompts.obtener_prompt_prescripcion_fase1(opciones, contexto)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            timeout=45,
        )
        return json.loads(resultado.choices[0].message.content)

    def evaluar_plan_fase2(self, propuesta, entrada):
        """Valora la rúbrica del Plan; no decide el grado de apoyo."""
        entrada = self._entrada_plan_compacta(entrada)
        resultado = self.client.with_options(max_retries=0).chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": prompts.PROMPT_RUBRICA_PLAN_FASE2},
                {"role": "user", "content": json.dumps({"propuesta": propuesta, "entrada": entrada}, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"}, temperature=0, timeout=45,
            max_completion_tokens=4096,
        )
        if resultado.choices[0].finish_reason == 'length':
            raise ValueError('La evaluación fue truncada antes de completarse.')
        return json.loads(resultado.choices[0].message.content)

    @staticmethod
    def _entrada_plan_compacta(entrada):
        """No repetir esquemas de gráficos ni todo el historial en cada llamada."""
        import copy
        salida = copy.deepcopy(entrada)
        c = salida.get('contexto_verificable', {})
        c['variables'] = [{k: v[k] for k in ('columna', 'nombre', 'rol', 'numerica') if k in v}
                          for v in c.get('variables', [])]
        historial = salida.get('historial', [])
        salida['historial'] = [{'respuesta': h.get('respuesta'), 'grado': h.get('grado'),
                               'criterios': h.get('evaluacion', {}).get('criterios')}
                              for h in historial[-2:]]
        salida.pop('dominio', None)  # El evaluador no decide probabilidades.
        return salida

    def generar_apoyo_plan_fase2(self, entrada):
        """Redacta el apoyo del grado elegido por la política del backend."""
        resultado = self.client.chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": prompts.PROMPT_APOYO_PLAN_FASE2},
                {"role": "user", "content": json.dumps(entrada, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"}, temperature=0.3, timeout=45,
        )
        return json.loads(resultado.choices[0].message.content)

    def obtener_taxonomia(self):
        """Obtiene todas las variables disponibles, agrupadas por tipo."""
        response = requests.get(
            f"{self.base_url}/taxonomia-variables", timeout=15
        )
        response.raise_for_status()
        return response.json()

    def obtener_diagnostico_calidad(self):
        """Obtiene el resumen de calidad calculado por Pandas en la API local."""
        response = requests.get(
            f"{self.base_url}/diagnostico-calidad", timeout=30
        )
        response.raise_for_status()
        return response.json()

    def obtener_analisis_escalado_transformacion(self, objetivo_fase1):
        """Obtiene el resumen de escalado calculado por Pandas para el objetivo."""
        response = requests.get(
            f"{self.base_url}/analisis-escalado-transformacion",
            params={"objetivo": objetivo_fase1},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def generar_diagnostico(self, endpoint_name):
        # 1. Construir la URL completa uniendo la base y el nombre
        url_completa = f"{self.base_url}/{endpoint_name}"
        
        # 2. Consultar a la API
        response = requests.get(url_completa)
        datos = response.json()
        
        # 3. Unir con el prompt
        mensaje = prompts.obtener_prompt_diagnostico(datos)
        # 4. Llamar al LLM
        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}]
        )
        return respuesta.choices[0].message.content
    def generar_diagnostico_calidad(self):
        # 1. Llamar al endpoint que acabamos de definir en app.py
        url_calidad = f"{self.base_url}/diagnostico-calidad"
        
        try:
            response = requests.get(url_calidad)
            datos_calidad = response.json()
            
            # 2. Generar el mensaje usando el prompt del "Consultor de Datos"
            mensaje = prompts.obtener_prompt_calidad(datos_calidad)
            
            # 3. Llamar al LLM para que analice y recomiende
            respuesta = self.client.chat.completions.create(
                model=self.modelo,
                messages=[{"role": "user", "content": mensaje}]
            )
            return respuesta.choices[0].message.content
            
        except Exception as e:
            return f"Error al realizar el diagnóstico de calidad: {str(e)}"
    
    def generar_mapa_variables(self):
        datos = self.obtener_taxonomia()
        
        mensaje = prompts.obtener_prompt_taxonomia(datos)
        
        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}]
        )
        return respuesta.choices[0].message.content

    def generar_descripcion_variables(self):
        """Describe de manera breve qué representa cada variable del dataset."""
        datos = self.obtener_taxonomia()
        mensaje = prompts.obtener_prompt_descripcion_variables(datos)

        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}]
        )
        return respuesta.choices[0].message.content

    def generar_preguntas_relaciones(self):
        """Identifica el tema del dataset y propone preguntas entre sus variables."""
        datos = self.obtener_taxonomia()

        mensaje = prompts.obtener_prompt_preguntas_relaciones(datos)

        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}]
        )
        return respuesta.choices[0].message.content

    def validar_pregunta_F1_1(self, pregunta):
        """Evalúa si una pregunta se puede responder con las variables del dataset."""
        if not pregunta.strip():
            return "⚠️ Escribe una pregunta para poder evaluarla."

        datos = self.obtener_taxonomia()
        mensaje = prompts.obtener_prompt_validacion_pregunta(pregunta, datos)

        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}]
        )
        return respuesta.choices[0].message.content

    def generar_tres_preguntas_sugeridas(self):
        """Genera tres preguntas viables para orientar al estudiante."""
        datos = self.obtener_taxonomia()
        mensaje = prompts.obtener_prompt_tres_preguntas_sugeridas(datos)

        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}]
        )
        return respuesta.choices[0].message.content

    def explicar_pregunta_elegida(self, pregunta):
        """Explica la utilidad de una pregunta seleccionada para el dataset."""
        datos = self.obtener_taxonomia()
        mensaje = prompts.obtener_prompt_explicacion_pregunta_elegida(pregunta, datos)

        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}]
        )
        return respuesta.choices[0].message.content

    def prescribir_pregunta(self, preguntas):
        """Elige la mejor pregunta sugerida cuando el estudiante no selecciona una."""
        datos = self.obtener_taxonomia()
        opciones = "\n".join(
            f"{indice}. {pregunta}" for indice, pregunta in enumerate(preguntas, 1)
        )
        mensaje = prompts.obtener_prompt_prescripcion_pregunta(opciones, datos)

        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}]
        )
        return respuesta.choices[0].message.content

    def evaluar_estrategia_fase2(
        self, propuesta_usuario, intento_fallido=0, objetivo_fase1="", nivel_forzado=None
    ):
        """Evalúa una estrategia sin recalcular el dataset en el LLM."""
        if not propuesta_usuario.strip():
            raise ValueError("La propuesta metodológica no puede estar vacía.")

        variables_contexto = self.obtener_taxonomia()
        diagnostico_calidad = self.obtener_diagnostico_calidad()
        analisis_escalado_transformacion = (
            self.obtener_analisis_escalado_transformacion(objetivo_fase1)
        )
        mensaje = prompts.obtener_prompt_evaluacion_fase2(
            variables_contexto,
            diagnostico_calidad,
            analisis_escalado_transformacion,
            int(intento_fallido),
            propuesta_usuario,
            nivel_forzado,
        )
        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}],
        )
        return respuesta.choices[0].message.content

    def explicar_alternativa_correcta_fase2(self, alternativa, objetivo_fase1=""):
        """Explica por qué una alternativa correcta prepara el dataset."""
        diagnostico_calidad = self.obtener_diagnostico_calidad()
        escalado = self.obtener_analisis_escalado_transformacion(objetivo_fase1)
        mensaje = prompts.obtener_prompt_explicacion_alternativa_correcta_fase2(
            alternativa, diagnostico_calidad, escalado
        )
        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}],
        )
        return respuesta.choices[0].message.content

    # ─────────────────────────────────────────────
    # FASE 3 — Limpieza de valores nulos (Evaluación LLM)
    # ─────────────────────────────────────────────

    def obtener_analisis_nulos_columna(self, columna: str) -> dict:
        """Llama al endpoint Flask que calcula las estadísticas Pandas de una columna."""
        response = requests.get(
            f"{self.base_url}/fase3/analizar-nulos-columna",
            params={"columna": columna},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def analizar_nulos_columna_fase3(self, columna: str) -> str:
        """Obtiene el análisis mecánico de Pandas y pide al LLM que clasifique
        las 4 opciones de tratamiento (BUENA / MEDIA / MALA) con justificación."""
        analisis = self.obtener_analisis_nulos_columna(columna)

        if analisis.get("nulos", 0) == 0:
            return f"La columna '{columna}' no tiene valores vacíos. No requiere tratamiento."

        # Construye el mensaje usando el prompt que ya tienes en prompts.py
        mensaje = prompts.obtener_prompt_analisis_nulos_fase3(analisis)
        
        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}],
        )
        return respuesta.choices[0].message.content
    def obtener_plan_maestro_nulos(self):
        """Obtiene el diagnóstico global de nulos de Flask y pide un plan maestro al LLM."""
        response = requests.get(
            f"{self.base_url}/diagnostico-calidad",
            timeout=30,
        )
        response.raise_for_status()
        datos = response.json()
        
        # Extraemos solo la sección de nulos y estadísticas relevantes
        nulos_info = datos.get("nulos", {})
        
        if not nulos_info:
            return "El dataset no tiene valores nulos. No se requiere plan de limpieza."

        mensaje = prompts.obtener_plan_maestro_nulos_fase3(nulos_info)
        
        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}],
        )
        return respuesta.choices[0].message.content

    def analizar_batch_nulos(self, lista_columnas: list) -> str:
        """Pide a Flask las estadísticas reales de un lote de columnas y consulta al LLM."""
        response = requests.post(
            f"{self.base_url}/fase3/analizar-batch-nulos",
            json={"columnas": lista_columnas},
            timeout=30,
        )
        response.raise_for_status()
        resumen_batch = response.json()
        
        # Genera el prompt con los metadatos reales obtenidos de Pandas
        mensaje = prompts.obtener_prompt_batch_nulos_fase3(resumen_batch)
        
        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}],
        )
        return respuesta.choices[0].message.content
    
    def obtener_analisis_outliers_batch_fase3(self, lista_columnas: list) -> dict:
        """Fase 3 — Outliers: calcula IQR, sesgo y registros atípicos."""
        response = requests.post(
            f"{self.base_url}/fase3/analizar-batch-outliers",
            json={"columnas": lista_columnas},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def analizar_batch_outliers_fase3(self, lista_columnas: list) -> str:
        """Fase 3 — solicita al LLM la recomendación para los outliers."""
        resumen_batch = self.obtener_analisis_outliers_batch_fase3(lista_columnas)

        # La API conserva todos los registros detectados para inspección. Al LLM
        # solo se le entrega una muestra para no exceder el límite de contexto en
        # columnas con muchos outliers.
        resumen_para_llm = {}
        for columna, datos in resumen_batch.items():
            if "registros_outliers" not in datos:
                resumen_para_llm[columna] = datos
                continue
            muestra = datos["registros_outliers"][:20]
            resumen_para_llm[columna] = {
                **datos,
                "registros_outliers": muestra,
                "registros_outliers_omitidos": max(
                    0, len(datos["registros_outliers"]) - len(muestra)
                ),
            }

        # Genera el prompt con los metadatos reales obtenidos de Pandas
        mensaje = prompts.obtener_prompt_batch_outliers(resumen_para_llm)
        
        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}],
        )
        return respuesta.choices[0].message.content
    def analizar_batch_normalizacion_fase3(self, lista_columnas: list = None) -> str:
        """Fase 3 — analiza el escalado de variables numéricas.
        No normaliza el DataFrame; solo genera la recomendación pedagógica."""
        payload = {"columnas": lista_columnas} if lista_columnas else {}
        
        response = requests.post(
            f"{self.base_url}/fase3/analizar-batch-normalizacion",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        resumen_batch = response.json()
        
        mensaje = prompts.obtener_prompt_batch_normalizacion(resumen_batch)
        
        respuesta = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "user", "content": mensaje}],
        )
        return respuesta.choices[0].message.content

    def transformar_tiempo_fase3(self) -> dict:
        """Construye ``datetime`` en el DataFrame activo sin eliminar sus fuentes."""
        response = requests.post(
            f"{self.base_url}/fase3/transformar-tiempo", timeout=30
        )
        response.raise_for_status()
        return response.json()
    
if __name__ == "__main__":
    # Prueba aislada del agente. Para el flujo completo usa: python3 main.py
    motor = MotorAnalisis()
    pregunta_usuario = input("\nEscribe una pregunta sobre el dataset: ")
    resultado_validacion = motor.validar_pregunta_F1_1(pregunta_usuario)
    print("\n--- Validación de la Pregunta ---\n")
    print(resultado_validacion)
