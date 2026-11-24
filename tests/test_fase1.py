import copy
import json
import unittest
from unittest.mock import Mock

import pandas as pd
from flask import Flask
from fase1 import (Explorador, registrar_fase1, validar_evaluacion,
                   validar_prescripcion, validar_recomendaciones)
from motor_fase1 import HABILIDADES, MotorFase1
from lightva_fase1 import perfilar_datos, planificar


def rubrica(puntuacion=2):
    return {"es_viable": puntuacion == 2,
            "pregunta_formulada": "¿Cómo cambia PM2.5 entre enero y marzo de 2020?",
            "vista_sugerida": "evolucion",
            "criterios": {k: {"puntuacion": puntuacion, "explicacion": "Evaluación de prueba."}
                           for k in HABILIDADES},
            "variables_utilizadas": ["PM2.5"], "feedback": "Justificación revisada."}


def dataset():
    return pd.DataFrame({"year": [2020]*8, "month": [1,1,1,1,3,3,3,3],
                         "day": [1,1,2,2,1,1,2,2], "hour": [0,1,0,1,0,1,0,1],
                         "PM2.5": [1,2,3,None,7,8,9,10],
                         "TEMP": [10,11,12,13,14,15,16,17],
                         "constante": [5]*8, "station": ["X"]*8})


def recomendaciones():
    return {"opciones": [
        {"titulo": f"Alternativa {i + 1}",
         "pregunta": f"¿Cómo cambia PM2.5 en el periodo según la alternativa {i + 1}?",
         "motivo": "Puede responderse con la cobertura y la vista seleccionadas.",
         "variables": ["PM2.5"]}
        for i in range(4)
    ]}


class TestMotor(unittest.TestCase):
    def test_formula_correcta(self):
        m = MotorFase1()
        m.registrar('a', '1', dict.fromkeys(HABILIDADES, 2))
        posterior = .5*.85 / (.5*.85 + .5*.25)
        self.assertAlmostEqual(m.habilidades['variables'].probabilidad, posterior+(1-posterior)*.15)

    def test_error_escala_un_grado(self):
        m = MotorFase1()
        for i, expected in enumerate([2,3,4,4]):
            completada, _ = m.registrar('a', str(i), dict.fromkeys(HABILIDADES, 0))
            self.assertFalse(completada); self.assertEqual(m.nivel, expected)

    def test_ayuda_no_actualiza_bkt(self):
        m = MotorFase1(); p = m.resumen()['habilidades']
        m.ayuda(); self.assertEqual(m.resumen()['habilidades'], p)

    def test_timeout_no_es_evidencia_y_escala(self):
        m = MotorFase1(); inicial = m.p_sabe('proposito') if hasattr(m, 'p_sabe') else m.habilidades['proposito'].probabilidad
        self.assertTrue(m.registrar_timeout('a'))
        self.assertEqual(m.nivel, 2)
        self.assertEqual(m.habilidades['proposito'].probabilidad, inicial)
        self.assertTrue(m.registrar_timeout('a'))
        self.assertEqual(m.nivel, 3)

    def test_prescripcion_no_cuenta_como_acierto(self):
        m = MotorFase1(); m.nivel = 4
        p = m.resumen()['habilidades']
        m.registrar('a', '1', dict.fromkeys(HABILIDADES, 2))
        self.assertEqual(m.resumen()['habilidades'], p)
        self.assertEqual(m.siguiente_nivel, 4)

    def test_fading_solo_en_siguiente_tarea(self):
        m = MotorFase1(); m.nivel = 3
        m.registrar('a', '1', dict.fromkeys(HABILIDADES, 2))
        self.assertEqual(m.siguiente_nivel, 3)
        m.nueva_tarea(); m.registrar('b', '2', dict.fromkeys(HABILIDADES, 2))
        self.assertEqual(m.nivel, 3)
        self.assertEqual(m.siguiente_nivel, 2)
        m.nueva_tarea(); self.assertEqual(m.nivel, 2)

    def test_reintentos_no_son_tareas_distintas(self):
        m = MotorFase1(); m.nivel = 3
        for i in range(3): m.registrar('a', str(i), dict.fromkeys(HABILIDADES, 2))
        self.assertEqual(m.siguiente_nivel, 3)

    def test_intento_duplicado_no_actualiza(self):
        m = MotorFase1(); m.registrar('a', '1', dict.fromkeys(HABILIDADES, 0)); before = m.resumen()
        with self.assertRaises(ValueError): m.registrar('a', '1', dict.fromkeys(HABILIDADES, 0))
        self.assertEqual(m.resumen(), before)

    def test_verificacion_no_retira_apoyo_sin_evidencia(self):
        m = MotorFase1(); m.siguiente_nivel = 4
        m.nueva_tarea(verificacion=True)
        m.registrar('a','1',dict.fromkeys(HABILIDADES,2))
        self.assertEqual(m.siguiente_nivel,4)
        m.nueva_tarea(verificacion=True)
        m.registrar('b','2',dict.fromkeys(HABILIDADES,2))
        self.assertEqual(m.siguiente_nivel,3)


class TestPerfil(unittest.TestCase):
    def setUp(self): self.explorador = Explorador(dataset())

    def test_evolucion_tres_series_conserva_valores_y_huecos(self):
        ex = Explorador(dataset().assign(O3=[2,4,6,8,10,12,14,16]))
        r = ex.grafico('PM2.5','evolucion',variables=['PM2.5','TEMP','O3'])
        self.assertEqual([s['variable'] for s in r['series']], ['PM2.5','TEMP','O3'])
        self.assertEqual(r['series'][0]['puntos'][0]['valor'], 2)
        self.assertEqual(r['series'][1]['puntos'][0]['valor'], 11.5)
        self.assertTrue(all(s['puntos'][1]['valor'] is None for s in r['series']))
        self.assertEqual(len({tuple(p['fecha'] for p in s['puntos']) for s in r['series']}), 1)
        with self.assertRaises(ValueError): ex.grafico('PM2.5','evolucion',variables=['station'])
        self.assertEqual(ex.grafico('PM2.5','evolucion',variables=[])['series'], [])

    def test_paneles_numericos_conservan_cada_calculo(self):
        ex = Explorador(dataset().assign(O3=[2,4,6,8,10,12,14,16]))
        for vista in ('ciclicidad','distribucion','variabilidad'):
            r = ex.grafico('PM2.5',vista,variables=['PM2.5','TEMP','O3'])
            self.assertEqual(len(r['paneles']), 3)
            for p in r['paneles']:
                self.assertEqual(p['puntos'], ex.grafico(p['variable'],vista)['puntos'])

    def test_relaciones_multivariables_compara_cada_pareja_una_vez(self):
        ex = Explorador(dataset().assign(O3=[2,4,6,8,10,12,14,16]))
        r = ex.grafico('PM2.5','relaciones',variables=['PM2.5','TEMP','O3'])
        self.assertEqual([(p['variable'],p['secundaria']) for p in r['paneles']],
                         [('PM2.5','TEMP'),('PM2.5','O3'),('TEMP','O3')])
        self.assertEqual(ex.grafico('PM2.5','relaciones',variables=['PM2.5'])['paneles'], [])

    def test_frecuencias_y_varias_medidas_por_categoria(self):
        ex = Explorador(dataset().assign(wd=['N','S']*4))
        freq = ex.grafico('station','frecuencias',variables=['station','wd'])
        self.assertEqual(len(freq['paneles']), 2)
        r = ex.grafico('station','comparacion',variables=['PM2.5','TEMP'])
        self.assertEqual([p['secundaria'] for p in r['paneles']], ['PM2.5','TEMP'])
        with self.assertRaises(ValueError): ex.grafico('station','comparacion',variables=['wd'])
        with self.assertRaises(ValueError): ex.grafico('PM2.5','distribucion',variables=['station'])

    def test_roles_y_fechas_no_se_tratan_como_medidas(self):
        df = dataset().assign(No=range(8), wd=['N', 'S', None, 'N', 'N', 'S', 'N', 'S'])
        ex = Explorador(df)
        self.assertEqual(ex.roles['No'], 'identificador')
        self.assertEqual(ex.roles['year'], 'tiempo')
        self.assertEqual(ex.roles['wd'], 'categoria')
        self.assertFalse(any(o['disponible'] for o in ex.opciones('No').values()))
        with self.assertRaises(ValueError): ex.grafico('year', 'distribucion')
        puntos = ex.grafico('wd', 'frecuencias')['puntos']
        self.assertEqual({p['categoria']: p['n'] for p in puntos}, {'N': 4, 'S': 3})

    def test_comparacion_categoria_excluye_faltantes_y_admite_negativos(self):
        ex = Explorador(pd.DataFrame({'station': ['A', 'A', 'B', None], 'valor': [-2, 0, 4, 99]}))
        puntos = ex.grafico('station', 'comparacion', 'valor')['puntos']
        self.assertEqual({p['categoria']: p['valor'] for p in puntos}, {'A': -1, 'B': 4})
        with self.assertRaises(ValueError): ex.grafico('station', 'comparacion', 'inexistente')

    def test_una_estacion_muestra_conteo_y_aviso(self):
        self.assertEqual(self.explorador.grafico('station', 'frecuencias')['puntos'],
                         [{'categoria': 'X', 'n': 8}])
        self.assertIn('Solo hay una categoría', self.explorador.grafico('station', 'comparacion', 'PM2.5')['nota'])

    def test_categorias_sin_medidas_y_alta_cardinalidad(self):
        ex = Explorador(pd.DataFrame({'categoria': [f'c{i}' for i in range(30)]}))
        self.assertFalse(ex.opciones('categoria')['comparacion']['disponible'])
        puntos = ex.grafico('categoria', 'frecuencias')['puntos']
        self.assertEqual(len(puntos), 21)
        self.assertEqual(sum(p['n'] for p in puntos), 30)

    def test_detecta_coordenadas_validas_sin_inventar_ubicaciones(self):
        self.assertEqual(self.explorador.perfil['espacial']['registros_validos'], 0)
        df = dataset().assign(latitud=[-12]*8, longitud=[-77]*7+[200])
        ex = Explorador(df)
        self.assertEqual(ex.perfil['espacial']['registros_validos'], 7)
        self.assertTrue(ex.perfil['espacial']['espaciotemporal'])
        self.assertNotIn('latitud', ex.numericas)

    def test_hueco_temporal(self):
        a = self.explorador.grafico('PM2.5', 'evolucion')['puntos']
        self.assertEqual(len(a), 3); self.assertIsNone(a[1]['valor']); self.assertEqual(a[1]['n'], 0)

    def test_cinco_graficos(self):
        for view in ('evolucion','ciclicidad','distribucion','variabilidad','relaciones'):
            r = self.explorador.grafico('PM2.5', view, 'TEMP' if view == 'relaciones' else None)
            self.assertTrue(r['puntos'])

    def test_histograma_y_medias_excluyen_faltantes(self):
        hist = self.explorador.grafico('PM2.5','distribucion')['puntos']
        self.assertEqual(sum(d['n'] for d in hist), 7)
        line = self.explorador.grafico('PM2.5','evolucion')['puntos']
        self.assertEqual(line[0]['valor'], 2)

    def test_constante_y_variable_inexistente(self):
        self.assertFalse(self.explorador.opciones('constante')['distribucion']['disponible'])
        with self.assertRaises(ValueError): self.explorador.grafico('inventada','evolucion')

    def test_no_tiempo_no_vistas_temporales(self):
        ex = Explorador(pd.DataFrame({'a':[1,2,3],'b':[2,4,6]}))
        self.assertFalse(ex.opciones('a')['evolucion']['disponible'])
        self.assertTrue(ex.opciones('a')['distribucion']['disponible'])

    def test_json_esquema_y_columnas(self):
        with self.assertRaises(ValueError): validar_evaluacion('no json', ['PM2.5'])
        r = rubrica(); r['variables_utilizadas'] = ['inventada']
        with self.assertRaises(ValueError): validar_evaluacion(r, ['PM2.5'])

    def test_recomendaciones_exigen_cuatro_opciones_y_columnas_reales(self):
        self.assertEqual(len(validar_recomendaciones(recomendaciones(), dataset().columns)), 4)
        malas = recomendaciones(); malas['opciones'][0]['variables'] = ['inventada']
        with self.assertRaises(ValueError): validar_recomendaciones(malas, dataset().columns)
        with self.assertRaises(ValueError): validar_prescripcion({'indice': 4, 'explicacion': 'Fuera de rango'})


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.evaluador = Mock(return_value=rubrica())
        self.recomendador = Mock(return_value=recomendaciones())
        self.prescriptor = Mock(return_value={'indice': 1, 'explicacion': 'Es viable y aprovecha la vista seleccionada.'})
        self.generador = Mock(return_value={'mensaje': 'Delimita el periodo de tu pregunta.', 'ejemplo': None})
        self.app = Flask(__name__); self.app.testing = True
        registrar_fase1(self.app, dataset(), self.evaluador, self.recomendador, self.prescriptor,
                        generar_apoyo=self.generador)
        self.client = self.app.test_client()
        result = self.client.post('/api/fase1/sesion',json={'variable':'PM2.5','vista':'evolucion'}).get_json()
        self.token = result['sesion']; self.estado = result
        self.headers = {'X-SiGAD-Session': self.token}

    def evaluar(self, intento='1', **kwargs):
        body = {'pregunta':'¿Cómo cambia PM2.5 en la estación X entre enero y marzo de 2020?',
                'revision':self.estado['revision'], 'intento':intento, **kwargs}
        r = self.client.post('/api/fase1/evaluar',json=body,headers=self.headers)
        if r.status_code==200:self.estado=r.get_json()
        return r

    def test_perfil_serializable(self):
        self.assertEqual(self.client.get('/api/fase1/perfil').status_code,200)

    def test_seleccion_multiple_se_conserva_al_evaluar(self):
        before = copy.deepcopy(self.estado['motor'])
        self.estado = self.client.post('/api/fase1/accion',headers=self.headers,json={
            'accion':'contexto','revision':self.estado['revision'], 'variable':'PM2.5',
            'vista':'evolucion','variables':['PM2.5','TEMP']}).get_json()
        self.assertEqual(self.estado['motor'], before)
        r = self.client.get('/api/fase1/grafico?variable=PM2.5&vista=evolucion&variables=PM2.5&variables=TEMP').get_json()
        self.assertEqual(len(r['series']), 2)
        self.evaluar()
        self.assertEqual(self.estado['contexto']['variables'], ['PM2.5','TEMP'])
        self.assertEqual(self.evaluador.call_args.args[1]['grafico']['variables'], ['PM2.5','TEMP'])

    def test_quitar_ultima_serie_no_evalua_y_no_penaliza(self):
        before = copy.deepcopy(self.estado['motor'])
        self.estado = self.client.post('/api/fase1/accion',headers=self.headers,json={
            'accion':'contexto','revision':self.estado['revision'], 'variable':'PM2.5',
            'vista':'evolucion','variables':[]}).get_json()
        self.assertEqual(self.evaluar().status_code, 400)
        self.assertEqual(self.estado['motor'], before)
        self.evaluador.assert_not_called()

    def test_contexto_y_evaluacion_conservan_paneles_multiples(self):
        self.estado = self.client.post('/api/fase1/accion',headers=self.headers,json={
            'accion':'contexto','revision':self.estado['revision'],'variable':'PM2.5',
            'vista':'distribucion','variables':['PM2.5','TEMP']}).get_json()
        respuesta = rubrica(); respuesta['vista_sugerida'] = 'distribucion'
        self.evaluador.return_value = respuesta
        self.assertEqual(self.evaluar().status_code, 200)
        self.assertEqual(self.estado['contexto']['variables'], ['PM2.5','TEMP'])
        self.assertEqual(self.evaluador.call_args.args[1]['grafico']['cantidad_paneles'], 2)

    def test_contexto_comparacion_varias_medidas(self):
        r = self.client.post('/api/fase1/accion',headers=self.headers,json={
            'accion':'contexto','revision':self.estado['revision'],'variable':'station',
            'vista':'comparacion','variables':['PM2.5','TEMP']})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.get_json()['contexto']['variable'],'station')
        grafico = self.client.get('/api/fase1/grafico?variable=station&vista=comparacion&variables=PM2.5&variables=TEMP').get_json()
        self.assertEqual(len(grafico['paneles']),2)

    def test_sesion_categoria_evaluacion_y_apoyo(self):
        self.estado = self.client.post('/api/fase1/sesion', json={
            'variable': 'station', 'vista': 'comparacion', 'secundaria': 'PM2.5'}).get_json()
        self.token = self.estado['sesion']; self.headers = {'X-SiGAD-Session': self.token}
        respuesta = rubrica()
        respuesta['vista_sugerida'] = 'comparacion'
        respuesta['variables_utilizadas'] = ['station', 'PM2.5']
        self.evaluador.return_value = respuesta
        r = self.evaluar().get_json()
        self.assertTrue(r['completada'])
        self.assertEqual(r['contexto']['secundaria'], 'PM2.5')
        self.assertEqual(r['contexto']['vista'], 'comparacion')

    def test_completa_y_conserva_objetivo(self):
        r=self.evaluar().get_json()
        self.assertTrue(r['completada']); self.assertEqual(r['objetivo']['variables'],['PM2.5'])
        self.assertIn('pregunta',r['objetivo'])

    def test_intencion_breve_incompleta_no_se_acepta(self):
        respuesta=rubrica(1)
        respuesta['criterios']['variables']['puntuacion']=2
        respuesta['criterios']['viabilidad']['puntuacion']=2
        respuesta['pregunta_formulada']='¿Cómo evoluciona PM2.5 entre enero y marzo de 2020?'
        respuesta['feedback']='Indica el periodo que deseas analizar.'
        self.evaluador.return_value=respuesta
        r=self.evaluar(pregunta='evolución temporal de PM2.5').get_json()
        self.assertFalse(r['completada'])
        self.assertIsNone(r['objetivo'])

    def test_intencion_ciclica_tiene_prioridad_sobre_vista_activa(self):
        respuesta=rubrica(2)
        respuesta['vista_sugerida']='ciclicidad'
        respuesta['pregunta_formulada']='¿Qué patrones cíclicos presenta PM2.5 según el mes y la hora entre enero y marzo de 2020?'
        respuesta['feedback']='¡Genial! Entonces analizaremos los patrones cíclicos de PM2.5.'
        self.evaluador.return_value=respuesta
        r=self.evaluar(pregunta='¿Qué patrones cíclicos presenta PM2.5 según el mes y la hora entre enero y marzo de 2020?').get_json()
        self.assertTrue(r['completada'])
        self.assertEqual(r['contexto']['vista'],'ciclicidad')
        self.assertIn('patrones cíclicos',r['objetivo']['pregunta'])

    def test_incorrecta_y_aislamiento(self):
        self.evaluador.return_value=rubrica(0)
        self.assertEqual(self.evaluar().get_json()['motor']['nivel'],2)
        other=self.client.post('/api/fase1/sesion',json={'variable':'PM2.5','vista':'evolucion'}).get_json()
        self.assertEqual(other['motor']['nivel'],1)

    def test_proveedor_y_json_invalido_no_penalizan(self):
        before=copy.deepcopy(self.estado['motor'])
        for response in [RuntimeError('fallo proveedor'), {'criterios':{}}]:
            if isinstance(response,Exception): self.evaluador.side_effect=response
            else:self.evaluador.side_effect=None;self.evaluador.return_value=response
            self.assertEqual(self.evaluar().status_code,502)
            estado=self.client.get('/api/fase1/estado',headers=self.headers).get_json()
            self.assertEqual(estado['motor'],before);self.assertEqual(estado['revision'],0)

    def test_repeticion_idempotente(self):
        first=self.evaluar().get_json(); second=self.evaluar().get_json()
        self.assertEqual(first,second);self.assertEqual(self.evaluador.call_count,1)

    def test_limite_del_proveedor_permite_reintentar_sin_penalizar(self):
        fallo = RuntimeError("detalle interno del proveedor")
        fallo.status_code = 429
        self.evaluador.side_effect = [fallo, rubrica()]
        anterior = copy.deepcopy(self.estado["motor"])
        respuesta = self.evaluar()
        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(respuesta.get_json()["codigo"], "proveedor_limite")
        estado = self.client.get("/api/fase1/estado", headers=self.headers).get_json()
        self.assertEqual(estado["motor"], anterior)
        self.assertEqual(estado["revision"], self.estado["revision"])
        self.assertEqual(self.evaluar().status_code, 200)

    def test_campo_vacio_no_evalua(self):
        self.assertEqual(self.evaluar(pregunta='').status_code,400)
        self.evaluador.assert_not_called()

    def test_ayuda_y_contexto_preservan_probabilidad(self):
        before=self.estado['motor']['habilidades']
        for accion in ['ayuda','contexto']:
            r=self.client.post('/api/fase1/accion',headers=self.headers,json={'accion':accion,'revision':self.estado['revision'],'variable':'TEMP','vista':'distribucion'})
            self.estado=r.get_json();self.assertEqual(r.status_code,200)
            self.assertEqual(self.estado['motor']['habilidades'],before)
        self.assertEqual(self.estado['motor']['nivel'],2)

    def test_timeout_conserva_bkt_y_escala(self):
        before=self.estado['motor']['habilidades']['proposito']['probabilidad']
        r=self.client.post('/api/fase1/accion',headers=self.headers,json={'accion':'timeout','revision':self.estado['revision']})
        self.estado=r.get_json()
        self.assertEqual(r.status_code,200);self.assertEqual(self.estado['motor']['nivel'],2)
        self.assertEqual(self.estado['motor']['habilidades']['proposito']['probabilidad'],before)

    def test_evaluador_recibe_entrada_completa_y_ayuda_previa(self):
        self.subir_nivel(2)
        self.evaluador.return_value = rubrica(1)
        self.evaluar()
        respuesta, contexto = self.evaluador.call_args.args
        self.assertIn('pregunta', respuesta)
        self.assertEqual(contexto['tarea']['fase'], 'Problema')
        self.assertEqual(set(contexto['rubrica']['criterios']), set(HABILIDADES))
        self.assertEqual(contexto['ayuda_recibida']['grado'], 2)
        self.assertFalse(contexto['ayuda_recibida']['autonoma'])
        self.assertIn('operaciones_disponibles', contexto)
        self.assertIn('faltantes', contexto['perfil']['variables'][0])
        self.evaluar('2')
        self.assertEqual(len(self.evaluador.call_args.args[1]['historial']), 1)

    def test_pista_llm_usa_decision_y_no_actualiza_bkt(self):
        self.subir_nivel(2)
        before = copy.deepcopy(self.estado['motor'])
        r = self.client.post('/api/fase1/apoyo', headers=self.headers,
            json={'revision': self.estado['revision']})
        self.estado = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.estado['guidance']['mensaje'], self.generador.return_value['mensaje'])
        self.assertEqual(self.estado['motor'], before)
        self.assertEqual(self.generador.call_args.args[0]['grado_seleccionado'], 2)
        self.client.post('/api/fase1/apoyo', headers=self.headers,
            json={'revision': self.estado['revision']})
        self.assertEqual(self.generador.call_count, 1)

    def test_pista_invalida_no_modifica_estado(self):
        self.subir_nivel(2)
        before = copy.deepcopy(self.estado)
        self.generador.return_value = {'mensaje': 'Respuesta completa', 'ejemplo': 'Pregunta resuelta'}
        r = self.client.post('/api/fase1/apoyo', headers=self.headers,
            json={'revision': self.estado['revision']})
        self.assertEqual(r.status_code, 502)
        after = self.client.get('/api/fase1/estado', headers=self.headers).get_json()
        self.assertEqual(after, before)

    def subir_nivel(self, nivel):
        while self.estado['motor']['nivel'] < nivel:
            self.estado=self.client.post('/api/fase1/accion',headers=self.headers,
                json={'accion':'ayuda','revision':self.estado['revision']}).get_json()

    def test_dirigir_ofrece_cuatro_y_seleccion_no_actualiza_bkt(self):
        self.subir_nivel(3); before=copy.deepcopy(self.estado['motor']['habilidades'])
        r=self.client.post('/api/fase1/apoyo-avanzado',headers=self.headers,
            json={'revision':self.estado['revision']})
        self.estado=r.get_json()
        self.assertEqual(r.status_code,200);self.assertEqual(len(self.estado['avanzado']['opciones']),4)
        self.assertFalse(self.estado['completada'])
        r=self.client.post('/api/fase1/seleccionar-opcion',headers=self.headers,
            json={'revision':self.estado['revision'],'indice':2})
        self.estado=r.get_json()
        self.assertTrue(self.estado['completada']);self.assertEqual(self.estado['objetivo']['origen'],'sugerida')
        self.assertEqual(self.estado['motor']['habilidades'],before)

    def test_prescribir_elige_y_completa_sin_actualizar_bkt(self):
        self.subir_nivel(4); before=copy.deepcopy(self.estado['motor']['habilidades'])
        r=self.client.post('/api/fase1/apoyo-avanzado',headers=self.headers,
            json={'revision':self.estado['revision']})
        self.estado=r.get_json()
        self.assertEqual(r.status_code,200);self.assertTrue(self.estado['completada'])
        self.assertEqual(self.estado['avanzado']['modo'],'prescribir')
        self.assertEqual(self.estado['objetivo']['origen'],'prescrita')
        self.assertEqual(self.estado['motor']['habilidades'],before)

    def test_recomendacion_invalida_no_cambia_bkt(self):
        self.subir_nivel(3); before=copy.deepcopy(self.estado['motor'])
        self.recomendador.return_value={'opciones':[]}
        r=self.client.post('/api/fase1/apoyo-avanzado',headers=self.headers,
            json={'revision':self.estado['revision']})
        self.assertEqual(r.status_code,502)
        after=self.client.get('/api/fase1/estado',headers=self.headers).get_json()
        self.assertEqual(after['motor'],before)

    def test_revision_obsoleta(self):
        self.assertEqual(self.evaluar(revision=500).status_code,409)
        self.evaluador.assert_not_called()

    def test_sesion_desconocida(self):
        self.assertEqual(self.client.get('/api/fase1/estado').status_code,404)


class TestLightVAAPI(unittest.TestCase):
    def test_evaluacion_guia_plan_y_avance_no_actualiza_bkt(self):
        datos = pd.concat([dataset(), dataset().assign(year=2021)], ignore_index=True)
        perfil = perfilar_datos(datos)
        inicial = rubrica()
        inicial["criterios"]["alcance"] = {"puntuacion": 1, "explicacion": "Falta delimitar el periodo."}
        evaluar = Mock(side_effect=[inicial, rubrica()])

        def generar(nivel, **entrada):
            def paso(clave, dependencias):
                return {"id": clave, "proposito": "Delimitar el periodo", "variables": ["PM2.5"],
                        "dependencias": dependencias, "evidencia": "Periodo justificado",
                        "criterios": ["alcance"], "intervencion": "Consulta el gráfico y justifica el periodo."}

            def opcion(ventana):
                return {"texto": "Analiza la evolución en el periodo indicado.",
                        "explicacion": "La ventana tiene observaciones.", "variables": ["PM2.5"],
                        "operacion": "resumen_temporal", "ventana": ventana}

            salida = {"nivel": nivel, "invalidaciones": {}, "aclaraciones": [],
                      "intervencion": "Revisa y justifica tu pregunta.",
                      "subtareas": [paso("elegir", ["revisar"])],
                      "alternativas": [opcion("2020"), opcion("2021")] if nivel == 3 else [],
                      "propuesta": opcion("2020") if nivel == 4 else None}
            if entrada["anterior"] is None:
                salida["subtareas"].insert(0, paso("revisar", []))
            return planificar(perfil, nivel, proveedor=lambda _: json.dumps(salida), **entrada)[0]

        planificador = Mock(side_effect=generar)
        app = Flask(__name__)
        registrar_fase1(app, datos, evaluar, planificador=planificador)
        client = app.test_client()
        estado = client.post("/api/fase1/sesion", json={"variable": "PM2.5", "vista": "evolucion"}).get_json()
        headers = {"X-SiGAD-Session": estado["sesion"]}

        def enviar(ruta, codigo=200, **cuerpo):
            nonlocal estado
            respuesta = client.post(f"/api/fase1/{ruta}", headers=headers,
                                    json={"revision": estado["revision"], **cuerpo})
            self.assertEqual(respuesta.status_code, codigo, respuesta.get_json())
            if codigo == 200:
                estado = respuesta.get_json()

        enviar("accion", accion="timeout")
        enviar("apoyo")
        self.assertEqual(estado["motor"]["nivel"], 1)
        planificador.assert_not_called()
        enviar("evaluar", intento="primero", pregunta="¿Cómo cambia PM2.5?")
        self.assertEqual(estado["motor"]["nivel"], 2)
        antes = copy.deepcopy(estado["motor"])
        enviar("apoyo")
        self.assertEqual(planificador.call_args.kwargs["dificultades"], ["alcance: Falta delimitar el periodo."])
        self.assertEqual(planificador.call_args.kwargs["respuesta"], "¿Cómo cambia PM2.5?")
        enviar("accion", 409, accion="completar_subtarea", subtarea="elegir", respuesta="Elegí una ventana.")
        enviar("accion", accion="completar_subtarea", subtarea="revisar", respuesta="Revisé el eje temporal.")
        self.assertEqual(estado["motor"], antes)
        enviar("accion", accion="ayuda")
        enviar("apoyo-avanzado")
        self.assertEqual(len(estado["plan_lightva"]["alternativas"]), 2)
        self.assertEqual(estado["plan_lightva"]["subtareas"][0]["respuesta"], "Revisé el eje temporal.")
        enviar("accion", accion="prescribir")
        enviar("apoyo")
        self.assertIsNotNone(estado["plan_lightva"]["propuesta"])
        self.assertFalse(estado["completada"])
        antes = copy.deepcopy(estado["motor"]["habilidades"])
        enviar("evaluar", intento="final", pregunta="¿Cómo varía PM2.5 en 2020?")
        self.assertTrue(estado["completada"])
        self.assertEqual(estado["motor"]["habilidades"], antes)
        self.assertEqual(evaluar.call_args.args[0], {"pregunta": "¿Cómo varía PM2.5 en 2020?"})
        self.assertEqual(evaluar.call_args.args[1]["ayuda_recibida"]["plan_lightva"]["nivel"], 4)
        enviar("accion", accion="nueva")
        self.assertIsNone(estado["plan_lightva"])


if __name__ == '__main__': unittest.main()
