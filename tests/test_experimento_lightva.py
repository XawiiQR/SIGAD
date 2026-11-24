import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from flask import Flask

from experimento_lightva import perfil_para_modelo, registrar_experimento
from lightVA import LightVA


class TestExperimentoLightVA(unittest.TestCase):
    def test_recorrido_con_csv_real_y_proveedor_simulado(self):
        app = Flask(__name__)
        app.testing = True
        csv = Path(__file__).resolve().parents[1] / "Data" / "Data.csv"
        datos = pd.read_csv(csv)
        registrar_experimento(app, datos, csv.name)
        cliente = app.test_client()
        endpoint = "/api/experimento-lightva"
        entradas = []

        def proveedor(**opciones):
            entrada = json.loads(opciones["messages"][1]["content"])
            entradas.append(entrada)
            if "nivel" in entrada:
                tratamientos = {2: [], 3: ["conservar", "mediana"], 4: ["mediana"]}
                salida = {"mensaje": "Revisa los huecos mensuales de PM2.5.",
                          "alternativas": [{"accion": a, "explicacion": "Compara la cobertura mensual."}
                                           for a in tratamientos[entrada["nivel"]]]}
            else:
                salida = {"ajustes": "Revisa la cobertura vigente.",
                          "actividades": [
                              dict(id=k, titulo=v, proposito="Revisar la cobertura de PM2.5",
                                   evidencia="Conteo mensual y justificación", variables=["PM2.5"])
                              for k, v in entrada["actividades_pendientes"].items()]}
            return SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop", message=SimpleNamespace(content=json.dumps(salida)))])

        modelo = LightVA.__new__(LightVA)
        modelo.modelo = "openai/gpt-oss-20b"
        modelo._consultar = proveedor
        meta = cliente.get(endpoint).get_json()
        self.assertIn("PM2.5", meta["pregunta"])
        self.assertIsNotNone(meta["perfil"]["periodo"]["inicio"])
        with patch("experimento_lightva.LightVA", return_value=modelo):
            inicio = cliente.post(endpoint, json={"accion": "iniciar", "pregunta": meta["pregunta"]})
            self.assertEqual(inicio.status_code, 200, inicio.get_json())
            sesion = inicio.get_json()["sesion"]

            def accion(nombre, status=200, **campos):
                resultado = cliente.post(endpoint, json=dict(
                    campos, accion=nombre, sesion=sesion, columna="PM2.5"))
                self.assertEqual(resultado.status_code, status, resultado.get_json())
                return resultado.get_json()

            self.assertEqual(accion("seleccionar", id="F2T1S1")["nivel"], 1)
            for nivel in (2, 3, 4):
                recibido = accion("ayuda")
                self.assertEqual(recibido["nivel"], nivel)
                self.assertEqual(recibido["eventos"][-1]["criterio"], "Solicitud del estudiante")
            accion("hallazgo", respuesta="Hay meses con datos faltantes de PM2.5.")
            self.assertEqual(accion("seleccionar", id="F2T1S2")["nivel"], 1)
            inspeccion = accion("inspeccionar")
            self.assertGreater(inspeccion["comparacion"]["mediana"]["cambios"], 0)
            original = inspeccion["perfil"]
            previa = accion("previsualizar", tratamiento="mediana")
            self.assertEqual(previa["perfil"], original)
            self.assertEqual(previa["previsualizacion"]["nulos"], 0)
            token = previa["previsualizacion"]["token"]
            accion("aplicar", status=400, tratamiento="media", previa=token, respuesta="Justificación.")
            aplicada = accion("aplicar", tratamiento="mediana", previa=token,
                              respuesta="Previsualicé la mediana para conservar filas.")
            self.assertEqual(aplicada["perfil"]["filas"], len(datos))
            self.assertEqual(next(c["nulos"] for c in aplicada["perfil"]["columnas"]
                                  if c["nombre"] == "PM2.5"), 0)
            self.assertGreater(datos["PM2.5"].isna().sum(), 0)
            revision = accion("actualizar")
            self.assertEqual(set(revision["avance"]), {"F2T1S1", "F2T1S2"})
            self.assertEqual(set(a["id"] for a in revision["plan"]["actividades"]), set(revision["avance"]))
            self.assertEqual(entradas[-1]["perfil"], perfil_para_modelo(aplicada["perfil"]))
            self.assertEqual(entradas[-1]["actividades_pendientes"], {})
            self.assertEqual(revision["trazas"][0]["entrada"]["avance"], {})
            deshecha = accion("deshacer")
            self.assertEqual(deshecha["perfil"], original)
            self.assertEqual(set(deshecha["avance"]), {"F2T1S1"})
            self.assertEqual(deshecha["eventos"][-1]["tipo"], "deshacer")
            accion("actualizar")
            self.assertEqual(set(entradas[-1]["actividades_pendientes"]), {"F2T1S2"})
