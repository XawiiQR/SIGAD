import unittest
import pandas as pd
from calidad_fase2 import resumen_calidad, detalle_calidad
from fase1 import Explorador
from test_fase1 import dataset


class TestCalidadVisual(unittest.TestCase):
    def test_referencias_distinguen_medias_de_periodo_de_registros(self):
        r = resumen_calidad(Explorador(dataset()), 'PM2.5')
        self.assertAlmostEqual(r['referencias_periodos']['media'], 5.25)
        self.assertAlmostEqual(r['referencias_registros']['media'], 40/7)
        self.assertAlmostEqual(r['referencias_periodos']['q1'], 3.625)
        self.assertAlmostEqual(r['referencias_periodos']['q3'], 6.875)
        self.assertEqual(r['referencias_periodos']['n'], 2)
        self.assertFalse(r['bandas'][1]['atipico_media'])

    def test_media_atipica_usa_limites_iqr_y_no_solo_cuartiles(self):
        df = pd.DataFrame({'fecha':pd.date_range('2020-01-01',periods=5,freq='MS'),
                           'valor':[1,1,1,1,100]})
        r = resumen_calidad(Explorador(df),'valor')
        self.assertEqual(r['periodos_atipicos'], 1)
        self.assertTrue(r['bandas'][-1]['atipico_media'])
        self.assertEqual(r['referencias_periodos']['superior'], 1)
        normal = pd.DataFrame({'fecha':pd.date_range('2020-01-01',periods=5,freq='MS'),
                               'valor':[1,2,3,4,5]})
        r = resumen_calidad(Explorador(normal),'valor')
        self.assertEqual(r['periodos_atipicos'],0)
        self.assertGreater(r['bandas'][-1]['media'],r['referencias_periodos']['q3'])

    def test_hueco_sin_registros_no_es_celda_vacia(self):
        r = resumen_calidad(Explorador(dataset()), 'PM2.5')
        self.assertEqual(r['faltantes'], 1)
        self.assertEqual(r['disponibles'], 7)
        enero, febrero, marzo = r['bandas']
        self.assertEqual(enero['faltantes'], 1)
        self.assertEqual(febrero['total'], 0)
        self.assertEqual(febrero['faltantes'], 0)
        self.assertIsNone(febrero['media'])
        self.assertEqual(marzo['faltantes'], 0)

    def test_extremo_es_candidato_y_no_desaparece_en_muestra(self):
        df = dataset(); df.loc[7, 'PM2.5'] = 120
        r = resumen_calidad(Explorador(df), 'PM2.5')
        self.assertEqual(r['atipicos'], 1)
        self.assertTrue(any(p['valor'] == 120 and p['atipico'] for p in r['puntos']))
        self.assertEqual(len(df), 8)
        self.assertEqual(df.loc[7, 'PM2.5'], 120)

    def test_vecinos_conservan_estacion(self):
        df = pd.DataFrame({'station':['A','B','A','B','A'], 'valor':[1,900,3,800,4]})
        r = detalle_calidad(Explorador(df), 'valor', 2)
        self.assertEqual([d['fila'] for d in r['registros']], [0,2,4])
        self.assertTrue(all(d['estacion'] == 'A' for d in r['registros']))
        with self.assertRaises(ValueError): detalle_calidad(Explorador(df), 'valor', -1)

    def test_categorias_sin_fechas_y_archivo_vacio(self):
        r = resumen_calidad(Explorador(pd.DataFrame({'grupo':['A',None,'B']})), 'grupo')
        self.assertFalse(r['numerica'])
        self.assertFalse(r['temporal'])
        self.assertEqual(r['faltantes'], 1)
        self.assertEqual(r['puntos'], [])
        vacio = resumen_calidad(Explorador(pd.DataFrame({'grupo':pd.Series(dtype='str')})), 'grupo')
        self.assertEqual(vacio['bandas'], [])

    def test_fechas_invalidas_declaradas_y_no_convertidas_en_periodos(self):
        ex = Explorador(pd.DataFrame({'fecha':['2020-01-01','no fecha'], 'valor':[1,2]}))
        r = resumen_calidad(ex, 'valor')
        self.assertEqual(r['sin_fecha'], 1)
        self.assertEqual(sum(b['total'] for b in r['bandas']), 1)


if __name__ == '__main__': unittest.main()
