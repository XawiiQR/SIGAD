import unittest
import pandas as pd
from flask import Flask
from fase3 import transformar, registrar_fase3, grafico_preparacion
import threading
from types import SimpleNamespace


class PreparacionTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({'SO2': [1., None, 3., 100.], 'station': ['A']*4})
        self.app = Flask(__name__)
        self.app.extensions['fase1'] = {'explorador': SimpleNamespace(df=self.df)}
        self.app.extensions['fase2'] = {'lock': threading.RLock(), 'sesiones': {'plan': {
            'token': 'plan', 'completada': True, 'plan': {'contenido': {'pasos': [
                {'accion': 'Preparar SO2', 'variables': ['SO2']}]}}}}}
        registrar_fase3(self.app)
        self.client = self.app.test_client()
        r = self.client.post('/api/fase3/sesion', headers={'X-SiGAD-Phase2': 'plan'})
        self.assertEqual(r.status_code, 200)
        self.headers = {'X-SiGAD-Phase3': r.json['sesion']}

    def operation(self, name, revision=0, **kwargs):
        return self.client.post('/api/fase3/operacion', headers=self.headers,
                                json=dict(operacion=name, revision=revision, **kwargs))

    def test_preview_apply_undo_preserves_original(self):
        r = self.operation('previsualizar', columna='SO2', accion='mediana')
        self.assertEqual(r.json['previa']['cambios'], 1)
        self.assertEqual(r.json['previa']['ejemplos'][0]['despues'], 3)
        self.assertEqual(r.json['estado']['datos']['nulos']['SO2'], 1)
        r = self.operation('aplicar')
        self.assertEqual(r.json['estado']['datos']['nulos']['SO2'], 0)
        self.assertTrue(pd.isna(self.df.at[1, 'SO2']))
        self.assertEqual(self.operation('aplicar').status_code, 409)
        r = self.operation('deshacer', revision=1)
        self.assertEqual(r.json['estado']['datos']['nulos']['SO2'], 1)

    def test_drop_and_download_context(self):
        self.operation('previsualizar', columna='SO2', accion='excluir_nulos')
        self.operation('aplicar')
        r = self.client.get('/api/fase3/descargar', headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertIn('station', r.data.decode('utf-8-sig'))
        self.assertEqual(len(r.data.decode('utf-8-sig').strip().splitlines()), 4)

    def test_reject_unselected_and_unconfirmed(self):
        self.assertEqual(self.operation('previsualizar', columna='station', accion='mediana').status_code, 400)
        self.assertEqual(self.operation('aplicar').status_code, 400)
        self.assertEqual(self.client.post('/api/fase3/sesion').status_code, 409)

    def test_scaling_and_clip(self):
        clean, changes = transformar(self.df, 'SO2', 'normalizar')
        self.assertEqual(clean.SO2.min(), 0)
        self.assertEqual(clean.SO2.max(), 1)
        self.assertTrue(pd.isna(clean.SO2.iloc[1]))
        constant = pd.DataFrame({'x': [5.,5.,None]})
        self.assertEqual(transformar(constant, 'x', 'normalizar')[0].x.dropna().tolist(), [0,0])
        extremes = pd.DataFrame({'x': [1.,2.,3.,4.,100.]})
        result, changes = transformar(extremes, 'x', 'limitar_iqr')
        self.assertEqual(changes, 1)
        self.assertEqual(result.x.iloc[-1], 7.)

    def test_media_y_exclusion_muestran_efectos_distintos(self):
        df = pd.DataFrame({'year': [2020]*4, 'month': [1,1,2,2],
                           'day': [1,2,1,2], 'SO2': [1., None, 9., 9.]})
        antes = grafico_preparacion(df, 'SO2')
        imputados, cambios = transformar(df, 'SO2', 'media')
        despues = grafico_preparacion(imputados, 'SO2')
        self.assertEqual(cambios, 1)
        self.assertAlmostEqual(imputados.SO2.iloc[1], 19/3)
        self.assertEqual(antes['puntos'][0]['valor'], 1.)
        self.assertAlmostEqual(despues['puntos'][0]['valor'], 11/3)
        excluidos, _ = transformar(df, 'SO2', 'excluir_nulos')
        sin_nulos = grafico_preparacion(excluidos, 'SO2')
        self.assertEqual([p['valor'] for p in antes['puntos']], [p['valor'] for p in sin_nulos['puntos']])
        self.assertEqual(sin_nulos['puntos'][0]['total'], 1)
        self.assertEqual(antes['puntos'][0]['total'], 2)

    def test_grafico_conserva_periodos_sin_datos(self):
        df = pd.DataFrame({'year':[2020,2020], 'month':[1,3], 'day':[1,1], 'x':[2.,8.]})
        g = grafico_preparacion(df, 'x')
        self.assertEqual(len(g['puntos']), 3)
        self.assertIsNone(g['puntos'][1]['valor'])
        self.assertEqual(g['puntos'][1]['total'], 0)

    def test_todas_las_alternativas_son_simulaciones_independientes(self):
        r = self.operation('comparar', columna='SO2')
        self.assertEqual(r.status_code, 200)
        escenarios = r.json['escenarios']
        self.assertEqual(set(escenarios), {'conservar','media','mediana','excluir_nulos','limitar_iqr','excluir_atipicos','normalizar'})
        self.assertEqual(escenarios['conservar']['datos']['nulos']['SO2'], 1)
        self.assertEqual(escenarios['media']['datos']['nulos']['SO2'], 0)
        self.assertEqual(escenarios['mediana']['datos']['nulos']['SO2'], 0)
        self.assertEqual(escenarios['excluir_nulos']['datos']['filas'], 3)
        self.assertEqual(r.json['estado']['revision'], 0)
        self.assertEqual(r.json['estado']['historial'], [])
        self.assertEqual(r.json['estado']['datos']['nulos']['SO2'], 1)
        self.assertEqual(self.operation('aplicar').status_code, 400)

    def test_excluir_atipicos_no_excluye_nulos(self):
        datos = pd.DataFrame({'x': [1.,2.,3.,4.,100.,None], 'contexto':list('abcdef')})
        copia, cambios = transformar(datos,'x','excluir_atipicos')
        self.assertEqual(cambios, 1)
        self.assertNotIn(4, copia.index)
        self.assertIn(5, copia.index)
        self.assertTrue(pd.isna(copia.at[5,'x']))
        self.assertEqual(len(datos), 6)

    def test_normalizacion_conjunta_conserva_fechas_y_se_deshace_en_un_paso(self):
        datos = pd.DataFrame({'SO2':[10.,20.,None,30.], 'PM10':[100.,300.,200.,None], 'year':[2020]*4})
        app = Flask('normalizacion')
        app.extensions['fase1'] = {'explorador':SimpleNamespace(df=datos)}
        app.extensions['fase2'] = {'lock':threading.RLock(),'sesiones':{'multi':{
            'token':'multi','completada':True,
            'contexto':{'variables':[{'columna':'SO2','rol':'medida'},{'columna':'PM10','rol':'medida'},{'columna':'year','rol':'tiempo'}]},
            'plan':{'contenido':{'pasos':[{'accion':'Comparar','variables':['SO2','PM10','year']}]}}}}}
        registrar_fase3(app)
        client = app.test_client()
        estado = client.post('/api/fase3/sesion',headers={'X-SiGAD-Phase2':'multi'}).json
        self.assertEqual(estado['medidas'], ['SO2','PM10'])
        headers = {'X-SiGAD-Phase3':estado['sesion']}
        payload = dict(operacion='escalas',revision=0,variables=['SO2','PM10'],accion='normalizar')
        r=client.post('/api/fase3/operacion',headers=headers,json=payload)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['previa']['datos']['muestra'][0]['SO2'],0.)
        self.assertEqual(r.json['previa']['datos']['muestra'][0]['PM10'],0.)
        self.assertEqual(r.json['previa']['datos']['muestra'][1]['SO2'],.5)
        self.assertEqual(r.json['previa']['datos']['muestra'][1]['PM10'],1.)
        self.assertEqual(r.json['previa']['datos']['muestra'][0]['year'],2020)
        self.assertEqual(r.json['previa']['datos']['nulos']['SO2'],1)
        self.assertEqual(r.json['estado']['datos']['muestra'][0]['SO2'],10.)
        client.post('/api/fase3/operacion',headers=headers,json=dict(operacion='aplicar',revision=0))
        r=client.post('/api/fase3/operacion',headers=headers,json=dict(operacion='deshacer',revision=1))
        self.assertEqual(r.json['estado']['datos']['muestra'][0]['SO2'],10.)
        self.assertEqual(r.json['estado']['datos']['muestra'][1]['PM10'],300.)
        payload['revision']=2
        payload['variables']=['year']
        self.assertEqual(client.post('/api/fase3/operacion',headers=headers,json=payload).status_code,400)

    def test_saltar_a_prescribir_registra_apoyo_sin_aplicar_datos(self):
        self.operation('previsualizar', columna='SO2', accion='media')
        r = self.operation('prescribir')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['estado']['nivel'],4)
        self.assertEqual(r.json['estado']['datos']['nulos']['SO2'],1)
        self.assertEqual(r.json['estado']['historial'],[])
        self.assertEqual(r.json['estado']['ayudas'][-1]['tipo'],'prescribir')
        r = self.operation('aplicar')
        self.assertEqual(r.json['estado']['historial'][-1]['apoyo'],4)
        self.assertEqual(r.json['estado']['datos']['nulos']['SO2'],0)

    def test_boxplot_estadisticas_completas_y_extremos(self):
        from fase3 import resumen
        datos = pd.DataFrame({'x':[1.,2.,3.,4.,100.,None]})
        antes = resumen(datos,['x'])['diagnostico']['x']
        self.assertEqual((antes['q1'],antes['mediana'],antes['q3']),(2.,3.,4.))
        self.assertEqual((antes['bigote_inferior'],antes['bigote_superior']),(1.,4.))
        self.assertEqual(antes['candidatos'],1)
        recortados,_=transformar(datos,'x','limitar_iqr')
        despues=resumen(recortados,['x'])['diagnostico']['x']
        self.assertEqual(despues['maximo'],7.)
        self.assertEqual(despues['candidatos'],0)

    def test_ventana_mantiene_posiciones_excluidas_y_estacion(self):
        from fase3 import ventana_nulos
        datos=pd.DataFrame({'x':[1.,None,100.,None,2.],'station':['A','A','B','B','A']})
        imputados,_=transformar(datos,'x','media')
        ventana=ventana_nulos(datos,'x',imputados)
        self.assertEqual([r['fila'] for r in ventana],[1,2,5])
        self.assertTrue(ventana[1]['imputado'])
        self.assertEqual(ventana[1]['despues'],103/3)
        excluidos,_=transformar(datos,'x','excluir_nulos')
        ventana=ventana_nulos(datos,'x',excluidos)
        self.assertEqual([r['fila'] for r in ventana],[1,2,5])
        self.assertTrue(ventana[1]['eliminado'])
        self.assertIsNone(ventana[1]['despues'])

    def test_ampliar_no_pierde_tratamiento_pendiente(self):
        self.operation('previsualizar',columna='SO2',accion='media')
        r=self.operation('ventana',columna='SO2',fila=2)
        self.assertEqual(r.status_code,200)
        self.assertTrue(any(p['imputado'] for p in r.json['ventana']))
        self.assertEqual(self.operation('aplicar').status_code,200)

    def test_kde_mismo_ancho_media_mediana_y_dispersion(self):
        from fase3 import comparar_kde
        import numpy as np
        serie=pd.Series([1.,2.,3.,4.,100.,None,None])
        original=serie.copy()
        k=comparar_kde(serie)
        self.assertEqual(k['centros'],{'media':22.,'mediana':3.})
        self.assertEqual(set(k['curvas']),{'original','media','mediana'})
        self.assertEqual(len(k['x']),256)
        self.assertTrue(all(len(c)==len(k['x']) for c in k['curvas'].values()))
        self.assertLess(k['estadisticas']['media']['desviacion'],k['estadisticas']['original']['desviacion'])
        for curve in k['curvas'].values():
            self.assertTrue(np.isfinite(curve).all())
            self.assertTrue((np.array(curve)>=0).all())
            area=np.trapezoid(curve,k['x']) if hasattr(np,'trapezoid') else np.trapz(curve,k['x'])
            self.assertAlmostEqual(area,1,places=2)
        pd.testing.assert_series_equal(serie,original)

    def test_kde_sin_nulos_y_casos_degenerados(self):
        from fase3 import comparar_kde
        k=comparar_kde(pd.Series([1.,2.,3.,10.]))
        self.assertEqual(k['curvas']['original'],k['curvas']['media'])
        self.assertEqual(k['curvas']['original'],k['curvas']['mediana'])
        for serie in (pd.Series([None,None],dtype=float),pd.Series([5.,5.,None]),pd.Series([1.,None])):
            k=comparar_kde(serie)
            self.assertEqual(k['x'],[])
            self.assertTrue(k['motivo'])
        self.assertIsNone(comparar_kde(pd.Series(['A',None,'B'])))

    def test_dispersion_no_equilibra_candidatos_y_habituales(self):
        from fase3 import resumen, dispersion_registros
        datos=pd.DataFrame({'x':[1.]*980+[100.]*20})
        d=resumen(datos,['x'])['diagnostico']['x']
        self.assertEqual(d['candidatos'],20)
        self.assertEqual(d['disponibles'],1000)
        self.assertEqual(len(d['dispersion']),800)
        self.assertLess(sum(p['atipico'] for p in d['dispersion']),25)
        despues,_=transformar(datos,'x','excluir_atipicos')
        puntos=dispersion_registros(datos,'x',despues)
        self.assertTrue(any(p['eliminado'] for p in puntos))
        self.assertEqual(puntos[-1]['fila'],1000)
        self.assertIsNone(puntos[-1]['despues'])
