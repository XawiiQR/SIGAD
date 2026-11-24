import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lightva_fase1 import ErrorPlan, consultar_proveedor, perfilar_csv, planificar


def actividad(clave="revisar", dependencias=()):
    return {"id": clave, "proposito": "Delimitar el alcance", "variables": ["PM2.5"],
            "dependencias": list(dependencias), "evidencia": "Justificación del periodo",
            "criterios": ["alcance"], "intervencion": "Consulta la cobertura disponible."}


def propuesta(ventana):
    return {"texto": "Resume la evolución en la ventana indicada.", "explicacion": "Hay mediciones.",
            "variables": ["PM2.5"], "ventana": ventana, "operacion": "resumen_temporal"}


class PlanFase1Test(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(dir=Path(__file__).parent, suffix=".csv", delete=False) as archivo:
            self.csv = Path(archivo.name)
        self.addCleanup(self.csv.unlink, missing_ok=True)
        self.csv.write_text(
            "fecha,PM2.5,otra\n2020-02-01,4,1\n2020-02-02,5,\n"
            "2021-01-01,6,2\n2021-01-02,7,3\nfecha inválida,,4\n", encoding="utf-8")
        self.perfil = perfilar_csv(self.csv)

    def generar(self, nivel=2, cambios=None, **entradas):
        salida = {"nivel": nivel, "subtareas": [actividad()], "invalidaciones": {},
                  "intervencion": "Revisa la cobertura y justifica tu elección.",
                  "alternativas": [], "propuesta": None, "aclaraciones": []}
        salida.update(cambios or {})
        return planificar(self.perfil, nivel, dificultades=["Falta el periodo"],
                          proveedor=lambda _: json.dumps(salida), **entradas)[0]

    def test_perfil_y_autonomo(self):
        self.assertEqual(self.perfil["columnas"]["PM2.5"]["faltantes"], 1)
        self.assertEqual(self.perfil["tiempo"]["sin_fecha_valida"], 1)
        self.assertEqual(self.perfil["tiempo"]["ventanas"]["2020"]["disponibles"]["PM2.5"], 2)
        plan, _ = planificar(self.perfil, 1, proveedor=lambda _: self.fail("Consulta inesperada"))
        self.assertEqual(plan["subtareas"], [])
        self.assertTrue(plan["evidencia"])

    def test_csv_invalido(self):
        for contenido in ("a,a\n1,2\n", "x,y\n1\n", "x,y\n"):
            with self.subTest(contenido=contenido):
                self.csv.write_text(contenido, encoding="utf-8")
                with self.assertRaisesRegex(ErrorPlan, "CSV inválido"):
                    perfilar_csv(self.csv)

    def test_cobertura_exige_observaciones_en_instantes_distintos(self):
        self.csv.write_text("year,month,day,PM2.5\n2020,1,1,4\n2020,1,1,5\n2020,,1,6\n"
                            "2021,1,1,7\n2021,1,2,8\n", encoding="utf-8")
        self.perfil = perfilar_csv(self.csv)
        self.assertEqual(self.perfil["tiempo"]["sin_fecha_valida"], 1)
        with self.assertRaisesRegex(ErrorPlan, "cobertura verificada"):
            self.generar(4, {"propuesta": propuesta("2020")})

    def test_dirigir_y_prescribir(self):
        plan = self.generar(3, {"alternativas": [propuesta("2020"), propuesta("2021")]})
        self.assertEqual(plan["alternativas"][0]["periodo"]["inicio"], "2020-02-01T00:00:00")
        self.assertEqual(self.generar(4, {"propuesta": propuesta("2021")})["propuesta"]["ventana"], "2021")
        with self.assertRaisesRegex(ErrorPlan, "dos o más"):
            self.generar(3)
        with self.assertRaisesRegex(ErrorPlan, "propuesta explicada"):
            self.generar(4)
        with self.assertRaisesRegex(ErrorPlan, "cobertura verificada"):
            self.generar(4, {"propuesta": propuesta("2019")})
        with self.assertRaisesRegex(ErrorPlan, "año completo"):
            self.generar(4, {"propuesta": dict(propuesta("2020"), texto="Analiza todo el año 2020.")})
        with self.assertRaisesRegex(ErrorPlan, "fecha ajena"):
            self.generar(4, {"propuesta": dict(propuesta("2020"), texto="Analiza 2021.")})
        plan = self.generar(4, {"propuesta": dict(propuesta("2020"), texto="Analiza 2020.")})
        self.assertEqual(plan["propuesta"]["texto"], "Analiza el periodo indicado.")
        with self.assertRaisesRegex(ErrorPlan, "alcances u operaciones distintos"):
            self.generar(3, {"alternativas": [propuesta("2021"), propuesta("2021")]})
        plan = self.generar(4, {"subtareas": [], "aclaraciones": ["¿Qué periodo interesa?"]})
        self.assertTrue(plan["aclaraciones"])
        with self.assertRaisesRegex(ErrorPlan, "propuesta explicada"):
            self.generar(4, {"aclaraciones": ["¿Qué periodo interesa?"]},
                         variables=["PM2.5"], respuesta="¿Cómo cambia PM2.5?")

    def test_rechaza_contratos_invalidos(self):
        casos = [
            ({"nivel": 3}, "nivel devuelto"),
            ({"subtareas": [actividad(), actividad()]}, "duplicados"),
            ({"subtareas": [actividad(dependencias=["otra"])]}, "inexistente"),
            ({"subtareas": [actividad("a", ["b"]), actividad("b", ["a"])]}, "ciclo"),
            ({"subtareas": [dict(actividad(), variables=["inventada"])]}, "ausentes"),
            ({"subtareas": [dict(actividad(), estado="completada")]}, "Campos inválidos"),
        ]
        for cambios, mensaje in casos:
            with self.subTest(cambios=cambios), self.assertRaisesRegex(ErrorPlan, mensaje):
                self.generar(cambios=cambios)
        for contenido in ("{", "{} {}", '{"nivel":2,"nivel":2}', '{"nivel":NaN}'):
            with self.subTest(contenido=contenido), self.assertRaisesRegex(ErrorPlan, "JSON válido"):
                planificar(self.perfil, 2, dificultades=["alcance"], proveedor=lambda _: contenido)
        with self.assertRaisesRegex(ErrorPlan, "Contexto insuficiente"):
            planificar(self.perfil, 2)

    def test_revision_conserva_estado_respuesta_y_dependencias(self):
        primero = self.generar()
        self.assertEqual(primero["subtareas"][0]["estado"], "pendiente")
        plan = self.generar(3, {"subtareas": [actividad("reformular", ["revisar"])],
                                "alternativas": [propuesta("2020"), propuesta("2021")]},
                            anterior=primero, avance={"revisar": {"completada": True, "respuesta": "2020"}})
        previa, nueva = plan["subtareas"]
        self.assertEqual((previa["id"], previa["estado"], previa["respuesta"]),
                         ("revisar", "completada", "2020"))
        self.assertEqual(nueva["estado"], "pendiente")
        self.assertIsNone(primero["subtareas"][0]["respuesta"])
        with self.assertRaisesRegex(ErrorPlan, "sobrescribir"):
            self.generar(anterior=plan)
        revisado = self.generar(cambios={"subtareas": [actividad("alternativa")],
                                        "invalidaciones": {"revisar": "Cambió el alcance requerido."}},
                                anterior=plan)
        self.assertEqual(revisado["subtareas"][0]["respuesta"], "2020")
        self.assertEqual(revisado["subtareas"][0]["estado"], "completada")
        self.assertTrue(revisado["subtareas"][0]["motivo_invalidacion"])
        self.assertTrue(revisado["subtareas"][1]["motivo_invalidacion"])

    def test_errores_del_proveedor_omiten_detalles_sensibles(self):
        with patch("dotenv.load_dotenv"), patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ErrorPlan, "Configuración ausente"):
                consultar_proveedor({"perfil": self.perfil})
        with patch.dict("os.environ", {"GROQ_API_KEY": "credencial-ficticia"}):
            with patch("lightva_fase1.LightVA", side_effect=RuntimeError("credencial-ficticia")):
                with self.assertRaisesRegex(ErrorPlan, r"^Fallo del proveedor\. RuntimeError$"):
                    consultar_proveedor({"perfil": self.perfil})

    def test_reintento_descarta_una_revision_invalida(self):
        anterior = self.generar()
        valido = {"nivel": 2, "subtareas": [actividad("reformular", ["revisar"])],
                  "invalidaciones": {}, "intervencion": "Reformula la pregunta.",
                  "alternativas": [], "propuesta": None, "aclaraciones": []}
        invalido = dict(valido, invalidaciones={"revisar": "Cambio de alcance."})
        with patch("lightva_fase1.consultar_proveedor",
                   side_effect=[json.dumps(invalido), json.dumps(valido)]) as consulta:
            plan, _ = planificar(self.perfil, 2, anterior=anterior, dificultades=["alcance"])
        self.assertEqual(consulta.call_count, 2)
        self.assertIn("invalidada", consulta.call_args.kwargs["correccion"])
        self.assertIsNone(plan["subtareas"][0]["motivo_invalidacion"])


if __name__ == "__main__":
    unittest.main()
