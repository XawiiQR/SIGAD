import copy
import unittest
from unittest.mock import Mock

import pandas as pd
from flask import Flask
from fase1 import registrar_fase1
from fase2 import registrar_fase2, diagnosticar, validar_evaluacion, validar_apoyo
from motor_fase2 import HABILIDADES, MotorFase2
from test_fase1 import dataset, rubrica as rubrica_f1


def plan(accion='Revisar faltantes de PM2.5 antes de decidir el tratamiento'):
    return {'pasos': [{'accion': accion, 'variables': ['PM2.5'],
                       'justificacion': 'Conservar la cobertura de la pregunta confirmada.'}]}


def rubrica(puntuacion=2):
    return {'criterios': {k: {'puntuacion': puntuacion, 'explicacion': 'Justificación evaluada.'}
                          for k in HABILIDADES},
            'variables_utilizadas': ['PM2.5'], 'feedback': 'Plan revisado.',
            'plan': plan() if puntuacion == 2 else None}


class TestContratoPlan(unittest.TestCase):
    def test_entrada_llm_elimina_esquemas_de_graficos_y_no_muta_original(self):
        from agente import MotorAnalisis
        entrada = {'contexto_verificable': {'variables': [
            {'columna': 'SO2', 'nombre': 'SO2', 'rol': 'medida', 'vistas': {'detalle': 'innecesario'}}]},
            'seleccion_usuario': {'variables': ['SO2']}, 'dominio': {'SO2': .5},
            'historial': []}
        compacta = MotorAnalisis._entrada_plan_compacta(entrada)
        self.assertNotIn('vistas', compacta['contexto_verificable']['variables'][0])
        self.assertNotIn('dominio', compacta)
        self.assertEqual(compacta['seleccion_usuario'], entrada['seleccion_usuario'])
        self.assertIn('vistas', entrada['contexto_verificable']['variables'][0])

    def test_rubrica_completa_y_columnas(self):
        self.assertTrue(validar_evaluacion(rubrica(), dataset().columns)['completa'])
        for mutation in ('puntuacion', 'variable', 'plan', 'criterios'):
            r = rubrica()
            if mutation == 'puntuacion': r['criterios']['calidad']['puntuacion'] = True
            elif mutation == 'variable': r['variables_utilizadas'] = ['inventada']
            elif mutation == 'plan': r['plan']['pasos'][0]['variables'] = ['inventada']
            else: del r['criterios']['estructura']
            with self.assertRaises(ValueError): validar_evaluacion(r, dataset().columns)

    def test_no_admite_plan_resuelto_en_orientar(self):
        with self.assertRaises(ValueError):
            validar_apoyo({'mensaje': 'Pista', 'plan': plan()}, 2, dataset().columns)

    def test_dirigir_requiere_tres_planes_distintos(self):
        with self.assertRaises(ValueError):
            validar_apoyo({'mensaje': 'Elige', 'opciones': [plan()]*3}, 3, dataset().columns)

    def test_motor_usa_habilidades_de_plan_y_no_de_problema(self):
        m = MotorFase2()
        self.assertEqual(set(m.habilidades), set(HABILIDADES))
        m.registrar('tarea', 'intento', dict.fromkeys(HABILIDADES, 2))
        self.assertGreater(m.habilidades['calidad'].probabilidad, .5)
        self.assertNotIn('proposito', m.habilidades)


class TestFase2API(unittest.TestCase):
    def setUp(self):
        self.df = dataset()
        self.app = Flask(__name__); self.app.testing = True
        registrar_fase1(self.app, self.df, Mock(return_value=rubrica_f1()))
        self.evaluador = Mock(return_value=rubrica())
        self.generador = Mock(return_value={'mensaje': 'Relaciona tu decisión con los faltantes observados.'})
        registrar_fase2(self.app, self.evaluador, self.generador)
        self.client = self.app.test_client()
        origen = self.client.post('/api/fase1/sesion', json={'variable':'PM2.5', 'vista':'evolucion'}).get_json()
        self.origen = origen['sesion']
        self.h1 = {'X-SiGAD-Session': self.origen}
        self.client.post('/api/fase1/evaluar', headers=self.h1,
            json={'pregunta':'¿Cómo cambia PM2.5 de enero a marzo de 2020?', 'intento':'f1', 'revision':0})
        self.estado = self.client.post('/api/fase2/sesion', headers=self.h1, json={}).get_json()
        self.headers = {'X-SiGAD-Phase2': self.estado['sesion']}

    def post(self, path, **datos):
        r = self.client.post('/api/fase2/' + path, headers=self.headers,
            json={'revision': self.estado['revision'], **datos})
        if r.status_code == 200: self.estado = r.get_json()
        return r

    def evaluar(self, intento='p1', propuesta='Revisaré los faltantes sin eliminar registros automáticamente.'):
        return self.post('evaluar', intento=intento, propuesta=propuesta)

    def subir(self, nivel):
        while self.estado['motor']['nivel'] < nivel:
            self.assertEqual(self.post('accion', accion='ayuda').status_code, 200)

    def test_requiere_objetivo_confirmado_en_servidor(self):
        self.assertEqual(self.client.post('/api/fase2/sesion', json={}).status_code, 404)
        pendiente = self.client.post('/api/fase1/sesion', json={'variable':'PM2.5','vista':'evolucion'}).get_json()
        self.assertEqual(self.client.post('/api/fase2/sesion', headers={'X-SiGAD-Session':pendiente['sesion']},
            json={'objetivo':'inventado'}).status_code, 409)

    def test_objetivo_heredado_diagnostico_y_datos_intactos(self):
        c = self.estado['contexto']
        self.assertIn('PM2.5', c['objetivo']['variables'])
        self.assertEqual(c['faltantes']['PM2.5'], 1)
        self.assertNotIn('year', c['escalas'])
        self.evaluar()
        pd.testing.assert_frame_equal(self.df, dataset())
        pd.testing.assert_frame_equal(self.app.extensions['fase1']['explorador'].df, dataset())
        self.assertFalse(self.estado['plan']['ejecutado'])

    def test_muestra_contiene_columnas_filas_y_ejemplos_sin_modificar_dominio(self):
        before = copy.deepcopy(self.estado)
        r = self.client.get('/api/fase2/muestra', headers=self.headers)
        self.assertEqual(r.status_code, 200)
        sample = r.get_json()
        self.assertEqual(sample['columnas'], list(self.df.columns))
        self.assertEqual(len(sample['filas']), 5)
        self.assertEqual(sample['total_filas'], 8)
        self.assertIsNone(sample['filas'][3][sample['columnas'].index('PM2.5')])
        self.assertEqual(sample['ejemplos']['TEMP'], [10, 11, 12])
        self.assertEqual(sample['ejemplos']['station'], ['X'])
        self.assertEqual(self.client.get('/api/fase2/estado', headers=self.headers).get_json(), before)
        self.evaluador.assert_not_called()
        self.generador.assert_not_called()

    def test_muestra_requiere_sesion(self):
        self.assertEqual(self.client.get('/api/fase2/muestra').status_code, 404)

    def test_exploracion_calidad_no_actualiza_conocimiento(self):
        before = copy.deepcopy(self.estado)
        self.assertEqual(self.client.get('/api/fase2/calidad?variable=PM2.5').status_code, 404)
        r = self.client.get('/api/fase2/calidad?variable=PM2.5', headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['faltantes'], 1)
        detalle = self.client.get('/api/fase2/calidad?variable=PM2.5&fila=3', headers=self.headers)
        self.assertEqual(detalle.status_code, 200)
        self.assertTrue(any(d['fila'] == 3 and d['valor'] is None for d in detalle.get_json()['registros']))
        self.assertEqual(self.client.get('/api/fase2/estado', headers=self.headers).get_json(), before)
        self.evaluador.assert_not_called()
        self.generador.assert_not_called()

    def test_seleccion_multiple_y_retiro_conservan_bkt(self):
        before = copy.deepcopy(self.estado['motor'])
        self.assertEqual(self.post('borrador', variables=['PM2.5','year','month'], tratamientos={}).status_code, 200)
        self.assertEqual(self.estado['borrador']['variables'], ['PM2.5','year','month'])
        self.assertEqual(self.estado['motor'], before)
        self.post('borrador', variables=['year','month'], tratamientos={})
        saved = self.client.post('/api/fase2/sesion', headers=self.h1, json={}).get_json()
        self.assertEqual(saved['borrador']['variables'], ['year','month'])
        self.assertEqual(saved['motor'], before)
        self.evaluador.assert_not_called()

    def test_tratamientos_deben_corresponder_a_seleccion_y_diagnostico(self):
        self.assertEqual(self.post('borrador', variables=['PM2.5'],
            tratamientos={'PM2.5':['imputar','conservar_unidades']}).status_code, 200)
        self.assertEqual(self.post('borrador', variables=['TEMP'],
            tratamientos={'TEMP':['imputar']}).status_code, 400)
        self.assertEqual(self.post('borrador', variables=['PM2.5'],
            tratamientos={'year':['construir_fecha']}).status_code, 400)
        self.assertEqual(self.post('borrador', variables=['inventada']).status_code, 400)
        self.assertEqual(self.post('borrador', variables=['PM2.5'],
            tratamientos={'PM2.5':['imputar','excluir_faltantes']}).status_code, 400)

    def test_evaluacion_recibe_seleccion_guardada(self):
        self.post('borrador', variables=['PM2.5','year'], tratamientos={'PM2.5':['imputar']})
        self.assertEqual(self.evaluar().status_code, 200)
        entrada = self.evaluador.call_args.args[1]
        self.assertEqual(entrada['seleccion_usuario']['variables'], ['PM2.5','year'])
        self.assertEqual(entrada['seleccion_usuario']['tratamientos']['PM2.5'], ['imputar'])

    def test_exito_actualiza_solo_habilidades_de_plan(self):
        before = self.client.get('/api/fase1/estado', headers=self.h1).get_json()['motor']
        self.assertEqual(self.evaluar().status_code, 200)
        self.assertTrue(self.estado['completada'])
        self.assertEqual(self.estado['plan']['origen'], 'usuario')
        self.assertGreater(self.estado['motor']['habilidades']['calidad']['probabilidad'], .5)
        self.assertEqual(self.client.get('/api/fase1/estado', headers=self.h1).get_json()['motor'], before)

    def test_entrada_contiene_rubrica_ayuda_y_contexto(self):
        self.subir(2)
        self.post('apoyo')
        self.evaluador.return_value = rubrica(1)
        self.evaluar()
        _, entrada = self.evaluador.call_args.args
        self.assertEqual(entrada['tarea']['fase'], 'Plan')
        self.assertEqual(set(entrada['rubrica']['criterios']), set(HABILIDADES))
        self.assertFalse(entrada['ayuda_recibida']['autonoma'])
        self.assertIn('mensaje', entrada['ayuda_recibida']['contenido'])
        self.assertIn('faltantes', entrada['contexto_verificable'])
        self.evaluar('p2')
        self.assertEqual(len(self.evaluador.call_args.args[1]['historial']), 1)

    def test_fallo_escala_un_grado_aunque_cliente_fuerce_otro(self):
        self.evaluador.return_value = rubrica(1)
        r = self.post('evaluar', propuesta='Plan parcial', intento='p1', nivel_forzado=4, intento_fallido=99)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.estado['motor']['nivel'], 2)
        self.assertEqual(self.estado['motor']['decision']['regla'], 'dificultad_en_rubrica')

    def test_ayuda_y_timeout_no_actualizan_bkt(self):
        before = copy.deepcopy(self.estado['motor']['habilidades'])
        for accion in ('ayuda', 'timeout'):
            self.post('accion', accion=accion)
            self.assertEqual(self.estado['motor']['habilidades'], before)
        self.evaluador.assert_not_called()

    def test_proveedor_y_json_invalidos_no_penalizan(self):
        before = copy.deepcopy(self.estado)
        self.evaluador.side_effect = RuntimeError('proveedor')
        self.assertEqual(self.evaluar().status_code, 502)
        self.evaluador.side_effect = None; self.evaluador.return_value = {'criterios': {}}
        self.assertEqual(self.evaluar().status_code, 502)
        self.assertEqual(self.client.get('/api/fase2/estado', headers=self.headers).get_json(), before)

    def test_rubrica_valida_no_depende_del_plan_redactado_por_llm(self):
        self.post('borrador', variables=['PM2.5','year'],
                  tratamientos={'PM2.5':['imputar'], 'year':['construir_fecha']})
        self.evaluador.return_value = {**rubrica(), 'plan': None}
        self.assertEqual(self.evaluar().status_code, 200)
        self.assertTrue(self.estado['completada'])
        pasos = self.estado['plan']['contenido']['pasos']
        self.assertTrue(any('Completar' in p['accion'] for p in pasos))
        self.assertTrue(all(set(p['variables']).issubset({'PM2.5','year'}) for p in pasos))

    def test_limite_proveedor_se_distingue_y_conserva_seleccion(self):
        class LimiteProveedor(Exception):
            status_code = 429
        self.post('borrador', variables=['PM2.5'], tratamientos={})
        before = copy.deepcopy(self.estado)
        self.evaluador.side_effect = LimiteProveedor('No mostrar detalles privados')
        response = self.evaluar()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()['codigo'], 'proveedor_limite')
        self.assertNotIn('privados', response.get_json()['error'])
        self.assertEqual(self.client.get('/api/fase2/estado',headers=self.headers).get_json(), before)

    def test_esquema_invalido_indica_causa(self):
        self.evaluador.return_value = {'criterios':{}}
        response = self.evaluar()
        self.assertEqual(response.get_json()['codigo'], 'evaluacion_formato')

    def test_idempotencia_y_colision_de_identificador(self):
        first = self.evaluar().get_json()
        self.assertEqual(self.evaluar().get_json(), first)
        self.assertEqual(self.evaluador.call_count, 1)
        self.assertEqual(self.evaluar(propuesta='Otra propuesta').status_code, 409)

    def test_revision_obsoleta_y_propuesta_vacia(self):
        self.assertEqual(self.post('evaluar', intento='p', propuesta=' ', revision=0).status_code, 400)
        self.assertEqual(self.post('evaluar', intento='p', propuesta='Plan', revision=99).status_code, 409)
        self.evaluador.assert_not_called()

    def test_restaurar_sesion_no_reinicia_dominio(self):
        self.subir(2)
        r = self.client.post('/api/fase2/sesion', headers=self.h1, json={}).get_json()
        self.assertEqual(r, self.estado)

    def test_pista_se_genera_una_vez_sin_actualizar_bkt(self):
        self.subir(2); before = copy.deepcopy(self.estado['motor'])
        self.assertEqual(self.post('apoyo').status_code, 200)
        self.assertEqual(self.estado['motor'], before)
        self.post('apoyo')
        self.assertEqual(self.generador.call_count, 1)
        self.assertEqual(self.generador.call_args.args[0]['grado_seleccionado'], 2)

    def test_apoyo_invalido_no_cambia_estado_y_se_puede_reintentar(self):
        self.subir(2); before = copy.deepcopy(self.estado)
        self.generador.return_value = {'mensaje':'Plan completo', 'plan':plan()}
        self.assertEqual(self.post('apoyo').status_code, 502)
        self.assertEqual(self.client.get('/api/fase2/estado',headers=self.headers).get_json(), before)
        self.generador.return_value = {'mensaje':'Observa los faltantes.'}
        self.assertEqual(self.post('apoyo').status_code, 200)

    def test_seleccion_asistida_no_acredita_dominio(self):
        self.subir(3); before = copy.deepcopy(self.estado['motor'])
        self.generador.return_value = {'mensaje':'Elige un plan.',
            'opciones':[plan(f'Revisar con criterio {i}') for i in range(3)]}
        self.assertEqual(self.post('apoyo').status_code, 200)
        self.assertEqual(self.post('seleccionar', indice=1).status_code, 200)
        self.assertTrue(self.estado['completada'])
        self.assertEqual(self.estado['plan']['origen'], 'sugerido')
        self.assertEqual(self.estado['motor'], before)

    def test_prescripcion_no_acredita_dominio(self):
        self.subir(4); before = copy.deepcopy(self.estado['motor'])
        self.generador.return_value = {'mensaje':'Este es el plan.', 'plan':plan()}
        self.assertEqual(self.post('apoyo').status_code, 200)
        self.assertTrue(self.estado['completada'])
        self.assertEqual(self.estado['plan']['origen'], 'prescrito')
        self.assertEqual(self.estado['motor'], before)
        self.assertFalse(self.estado['plan']['ejecutado'])

    def test_prescribir_resuelve_variables_sin_copiar_seleccion_incorrecta(self):
        self.post('borrador', variables=['TEMP'], tratamientos={})
        self.subir(4)
        self.assertEqual(self.post('apoyo').status_code, 200)
        columnas = self.estado['borrador']['variables']
        self.assertIn('PM2.5', columnas)
        self.assertNotIn('TEMP', columnas)
        self.assertTrue(self.estado['plan']['contenido']['pasos'])
        self.assertIn('conservar_unidades', self.estado['borrador']['tratamientos']['PM2.5'])
        self.generador.assert_not_called()

    def test_salto_directo_desde_autonomo_y_plan_prescrito(self):
        antes = copy.deepcopy(self.estado['motor']['habilidades'])
        self.assertEqual(self.post('accion',accion='prescribir').status_code,200)
        self.assertEqual(self.estado['motor']['nivel'],4)
        self.assertEqual(self.estado['motor']['habilidades'],antes)
        self.assertEqual(self.post('apoyo').status_code,200)
        self.assertTrue(self.estado['completada'])
        self.assertEqual(self.estado['plan']['origen'],'prescrito')

    def test_salto_fase1_desde_autonomo_sin_acreditar_acierto(self):
        origen = self.client.post('/api/fase1/sesion',json={'variable':'PM2.5','vista':'evolucion'}).json
        r = self.client.post('/api/fase1/accion',headers={'X-SiGAD-Session':origen['sesion']},
                             json={'revision':origen['revision'],'accion':'prescribir'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['motor']['nivel'],4)
        self.assertEqual(r.json['motor']['habilidades'],origen['motor']['habilidades'])
        self.assertFalse(r.json['completada'])

    def test_sesiones_aisladas(self):
        self.subir(2)
        self.assertEqual(self.client.get('/api/fase2/estado').status_code, 404)
        self.assertEqual(self.client.get('/api/fase2/estado',headers={'X-SiGAD-Phase2':'otro'}).status_code, 404)

    def test_diagnostico_categorico_espacial_y_sin_alertas(self):
        from fase1 import Explorador
        df = pd.DataFrame({'station':['A','B'], 'latitud':[-12,-13],
                           'longitud':[-77,-78], 'fecha':['2020-01-01','2020-02-01']})
        c = diagnosticar(Explorador(df), {'pregunta':'Comparar estaciones', 'variables':['station']})
        self.assertEqual(c['escalas'], {})
        self.assertEqual(c['faltantes'], {})
        self.assertTrue(c['espacial']['espaciotemporal'])


if __name__ == '__main__':
    unittest.main()
