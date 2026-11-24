import sys
import json
import types
import unittest
from unittest.mock import Mock, patch

from lightVA import FASES, LightVA, decodificar_json, esquema_salida, agrupar_actividades, CAMPOS_PEDAGOGICOS, mostrar


def interpretacion():
    return dict(objetivo='Variación anual de PM2.5', intencion='tendencia',
                variables=['PM2.5'], explicito=[], inferido=[], pendiente=[],
                limitaciones=[], viable=True)


def pedagogia():
    return dict(proposito_aprendizaje='Justificar una estrategia coherente',
                evidencia_evaluable='Propuesta propia justificada',
                criterios_evaluacion=['Identifica variables pertinentes', 'Justifica su decisión'],
                autonomo='Propón una estrategia y justifícala.',
                orientar='Piensa qué necesitas decidir antes de ejecutar.',
                dirigir='Compara alternativas y justifica una elección.',
                prescribir='Se propone una estrategia explicada, sin acreditar dominio propio.')


def fase(numero):
    sub = dict(descripcion='Revisar datos', variables=['PM2.5'], metodo='Diagnóstico',
               resultado_esperado='Resumen', criterio_verificacion='Contrastar cobertura',
               condicion='Cuando existan registros', **pedagogia())
    return dict(numero=numero, nombre=FASES[numero], tareas=[dict(
        descripcion='Actividad pertinente', tipo='diagnostico', variables=['PM2.5'],
        subtareas=[sub])])


class TestLightVA(unittest.TestCase):
    def motor(self, modo='rapido'):
        m = LightVA.__new__(LightVA)
        m.perfil = {'columnas': [{'nombre': 'PM2.5'}]}
        m.modo, m.modelo, m.mediciones = modo, 'openai/gpt-oss-20b', []
        return m

    def preparar(self, m, fallo=None):
        def pedir(instrucciones, entrada, validar, **opciones):
            if 'No generes tareas' in instrucciones:
                return validar(interpretacion())
            if m.modo == 'rapido':
                salida = {'fases': [fase(n) for n in FASES]}
                if fallo:
                    fallo(salida)
                return validar(salida)
            return validar(fase(entrada['fase_actual']['numero']))
        m._pedir_json = Mock(side_effect=pedir)

    def test_rapido_dos_llamadas_y_dependencias_asignadas_por_python(self):
        m = self.motor()
        self.preparar(m)
        anterior = {'conservar': True}
        resultado = m.planificar('Pregunta', anterior, 'Revisar cobertura')
        self.assertEqual(m._pedir_json.call_count, 2)
        self.assertEqual([f['numero'] for f in resultado['fases']], [2, 3, 4, 5])
        for i, f in enumerate(resultado['fases']):
            t = f['tareas'][0]
            self.assertEqual(t['id'], f"F{f['numero']}T1")
            self.assertEqual(t['depende_de'], [] if i == 0 else [f"F{f['numero']-1}T1"])
        self.assertEqual(anterior, {'conservar': True})
        contexto = m._pedir_json.call_args.args[1]
        self.assertEqual(contexto['solicitud_revision'], 'Revisar cobertura')

    def test_secuencial_conserva_cinco_llamadas_y_contexto_anterior(self):
        m = self.motor('secuencial')
        self.preparar(m)
        m.planificar('Pregunta')
        self.assertEqual(m._pedir_json.call_count, 5)
        self.assertEqual(len(m._pedir_json.call_args.args[1]['fases_previas']), 3)

    def test_no_acepta_fase_omitida_ni_columna_inventada(self):
        for fallo in (lambda x: x['fases'].pop(),
                      lambda x: x['fases'][0]['tareas'][0].update(variables=['inventada'])):
            with self.subTest(fallo=fallo):
                m = self.motor()
                self.preparar(m, fallo)
                with self.assertRaises(ValueError):
                    m.planificar('Pregunta')

    def test_interpretacion_texto_aislado_se_conserva_como_lista(self):
        m = self.motor()
        original = interpretacion()
        original['inferido'] = 'Comparar concentraciones por dirección del viento'
        def pedir(instrucciones, entrada, validar, **opciones):
            if 'No generes tareas' in instrucciones:
                return validar(dict(original))
            return validar({'fases': [fase(n) for n in FASES]})
        m._pedir_json = Mock(side_effect=pedir)
        plan = m.planificar('¿Cómo varían conjuntamente PM2.5 y PM10 según wd?')
        self.assertEqual(plan['interpretacion']['inferido'], [original['inferido']])
        self.assertIsInstance(original['inferido'], str)
        self.assertEqual(m._pedir_json.call_count, 2)

    def test_interpretacion_rechaza_ausencia_null_objetos_y_listas_invalidas(self):
        for valor in (None, {}, ['válido', 7], [''], ''):
            with self.subTest(valor=valor):
                m = self.motor()
                obj = interpretacion()
                obj['inferido'] = valor
                m._pedir_json = Mock(side_effect=lambda ins, ent, validar, **opciones: validar(obj))
                with self.assertRaisesRegex(ValueError, 'interpretacion.inferido'):
                    m.planificar('Pregunta')
        m = self.motor()
        obj = interpretacion()
        del obj['inferido']
        m._pedir_json = Mock(side_effect=lambda ins, ent, validar, **opciones: validar(obj))
        with self.assertRaisesRegex(ValueError, 'interpretacion.inferido'):
            m.planificar('Pregunta')

    def test_campo_omitido_se_repara_en_reintento_con_error_especifico(self):
        m = self.motor()
        incompleta = interpretacion()
        del incompleta['inferido']
        sdk = self.sdk(m, [self.respuesta(json.dumps(incompleta)),
                           self.respuesta(json.dumps(interpretacion())),
                           self.respuesta(json.dumps({'fases': [fase(n) for n in FASES]}))])
        with patch.dict(sys.modules, {'openai': sdk}):
            plan = m.planificar('Pregunta')
        self.assertEqual(plan['interpretacion']['inferido'], [])
        self.assertEqual(m.client.chat.completions.create.call_count, 3)
        mensajes = m.client.chat.completions.create.call_args_list[1].kwargs['messages']
        self.assertIn('interpretacion.inferido', mensajes[-1]['content'])
        self.assertIn('[]', mensajes[-1]['content'])

    def test_fases_por_nombre_python_asigna_orden_y_numeros(self):
        m = self.motor()
        bloques = {FASES[n]: {'tareas': fase(n)['tareas']} for n in reversed(FASES)}
        def pedir(ins, entrada, validar, **opciones):
            return validar(interpretacion() if 'No generes tareas' in ins else bloques)
        m._pedir_json = Mock(side_effect=pedir)
        plan = m.planificar('Pregunta')
        self.assertEqual([f['numero'] for f in plan['fases']], [2, 3, 4, 5])
        self.assertEqual([f['nombre'] for f in plan['fases']], list(FASES.values()))
        self.assertEqual(m._pedir_json.call_count, 2)

    def test_no_renumera_lista_que_contiene_problema(self):
        m = self.motor()
        def fallo(obj):
            obj['fases'][0].update(numero=1, nombre='Problema')
        self.preparar(m, fallo)
        with self.assertRaisesRegex(ValueError, 'No incluyas Problema'):
            m.planificar('Pregunta')

    def test_error_columna_indica_ubicacion_y_nombres_permitidos(self):
        m = self.motor()
        def fallo(obj):
            obj['fases'][2]['tareas'][0]['subtareas'][0]['variables'] = ['mes']
        self.preparar(m, fallo)
        with self.assertRaisesRegex(ValueError, r"F4T1S1.variables.*mes.*PM2.5"):
            m.planificar('Pregunta')

    def sdk(self, m, respuestas):
        m.client = types.SimpleNamespace(chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=Mock(side_effect=respuestas))))
        return types.SimpleNamespace(BadRequestError=type('BadRequestError', (Exception,), {}),
                                     RateLimitError=type('RateLimitError', (Exception,), {}))

    def respuesta(self, contenido='{}', motivo='stop'):
        return types.SimpleNamespace(choices=[types.SimpleNamespace(
            message=types.SimpleNamespace(content=contenido), finish_reason=motivo)])

    def test_cuota_tpm_espera_y_reintenta_sin_perder_la_consulta(self):
        m = self.motor()
        sdk = self.sdk(m, [])
        error = sdk.RateLimitError()
        error.body = {'error': {'message': 'tokens per minute (TPM): Limit 8000, Used 6518, Requested 2490. Please try again in 7.56s.'}}
        error.response = types.SimpleNamespace(headers={})
        m.client.chat.completions.create.side_effect = [error, self.respuesta()]
        with patch.dict(sys.modules, {'openai': sdk}), patch('lightVA.sleep') as pausa:
            self.assertEqual(m._pedir_json('Contrato', {}, lambda x: x), {})
        pausa.assert_called_once_with(7.81)
        llamadas = m.client.chat.completions.create.call_args_list
        self.assertEqual(llamadas[0], llamadas[1])
        self.assertEqual(len(m.mediciones), 2)

    def test_cuota_diaria_o_peticion_demasiado_grande_no_reintenta(self):
        for mensaje in ('tokens per day (TPD): Please try again in 7s.',
                        'tokens per minute (TPM): Limit 8000, Requested 9000. Please try again in 7s.',
                        'tokens per minute (TPM): Please try again in 90s.'):
            m = self.motor()
            sdk = self.sdk(m, [])
            error = sdk.RateLimitError()
            error.body = {'error': {'message': mensaje}}
            m.client.chat.completions.create.side_effect = [error]
            with patch.dict(sys.modules, {'openai': sdk}), patch('lightVA.sleep') as pausa:
                with self.assertRaises(sdk.RateLimitError):
                    m._pedir_json('Contrato', {}, lambda x: x)
            pausa.assert_not_called()
            self.assertEqual(m.client.chat.completions.create.call_count, 1)

    def test_respeta_retry_after_y_acota_dos_reintentos(self):
        m = self.motor()
        sdk = self.sdk(m, [])
        error = sdk.RateLimitError()
        error.body = {'error': {'message': 'tokens per minute (TPM)'}}
        error.response = types.SimpleNamespace(headers={'retry-after': '2'})
        m.client.chat.completions.create.side_effect = [error, error, error]
        with patch.dict(sys.modules, {'openai': sdk}), patch('lightVA.sleep') as pausa:
            with self.assertRaises(sdk.RateLimitError):
                m._pedir_json('Contrato', {}, lambda x: x)
        self.assertEqual(pausa.call_args_list, [unittest.mock.call(2.25), unittest.mock.call(2.25)])
        self.assertEqual(m.client.chat.completions.create.call_count, 3)

    def test_limita_salida_razonamiento_y_registra_tiempo(self):
        m = self.motor()
        sdk = self.sdk(m, [self.respuesta()])
        with patch.dict(sys.modules, {'openai': sdk}):
            self.assertEqual(m._pedir_json('Contrato', {}, lambda x: x), {})
        kwargs = m.client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs['reasoning_effort'], 'low')
        self.assertEqual(kwargs['max_completion_tokens'], 6000)
        self.assertEqual(len(m.mediciones), 1)

    def test_respuesta_truncada_no_se_acepta_como_plan(self):
        m = self.motor()
        sdk = self.sdk(m, [self.respuesta(motivo='length')])
        with patch.dict(sys.modules, {'openai': sdk}), self.assertRaisesRegex(ValueError, 'truncada'):
            m._pedir_json('Contrato', {}, lambda x: x)
        self.assertEqual(m.client.chat.completions.create.call_count, 1)

    def test_reparacion_no_reenvia_la_respuesta_fallida_completa(self):
        m = self.motor()
        fallida = 'respuesta inválida extensa ' * 200
        sdk = self.sdk(m, [self.respuesta(fallida), self.respuesta('{}')])
        with patch.dict(sys.modules, {'openai': sdk}):
            self.assertEqual(m._pedir_json('Contrato', {'pregunta': 'Original'}, lambda x: x), {})
        mensajes = m.client.chat.completions.create.call_args_list[1].kwargs['messages']
        self.assertEqual(len(mensajes), 3)
        self.assertFalse(any(x['role'] == 'assistant' for x in mensajes))
        self.assertIn('Original', mensajes[1]['content'])
        self.assertNotIn(fallida, str(mensajes))

    def test_planificar_envia_esquema_en_ambas_llamadas(self):
        m = self.motor()
        self.preparar(m)
        m.planificar('¿Qué condiciones caracterizan episodios de PM2.5 elevado?')
        llamadas = m._pedir_json.call_args_list
        esquema_i = llamadas[0].kwargs['esquema']
        self.assertEqual(esquema_i['properties']['variables']['items']['enum'], ['PM2.5'])
        esquema_p = llamadas[1].kwargs['esquema']
        self.assertEqual(set(esquema_p['properties']), {'actividades'})
        actividad = esquema_p['properties']['actividades']['items']
        self.assertEqual(actividad['properties']['variables']['items']['enum'], ['PM2.5'])
        self.assertEqual(llamadas[1].kwargs['max_tokens'], 4800)

    def test_fallo_rapido_no_dispara_cascada_costosa_de_llamadas(self):
        m = self.motor()
        sdk = self.sdk(m, [])
        error = sdk.BadRequestError()
        error.body = {'error': {'code': 'json_validate_failed', 'message': 'Generation failed'}}
        def pedir(ins, entrada, validar, **opciones):
            if 'No generes tareas' in ins:
                return validar(interpretacion())
            raise error
        m._pedir_json = Mock(side_effect=pedir)
        with patch.dict(sys.modules, {'openai': sdk}), self.assertRaises(sdk.BadRequestError):
            m.planificar('Pregunta')
        self.assertEqual(m._pedir_json.call_count, 2)

    def test_esquema_invalido_preserva_diagnostico_y_no_inicia_fases(self):
        m = self.motor()
        sdk = self.sdk(m, [])
        error = sdk.BadRequestError()
        error.body = {'error': {'code': 'json_schema_invalid', 'message': 'Invalid schema'}}
        def pedir(ins, entrada, validar, **opciones):
            if 'No generes tareas' in ins:
                return validar(interpretacion())
            raise error
        m._pedir_json = Mock(side_effect=pedir)
        with patch.dict(sys.modules, {'openai': sdk}), self.assertRaises(sdk.BadRequestError) as salida:
            m.planificar('Pregunta')
        self.assertIs(salida.exception, error)
        self.assertEqual(m._pedir_json.call_count, 2)

    def test_sdk_recibe_json_schema_strict(self):
        m = self.motor()
        sdk = self.sdk(m, [self.respuesta('{}')])
        contrato = esquema_salida(['PM2.5'], 'plan')
        with patch.dict(sys.modules, {'openai': sdk}):
            m._pedir_json('Contrato', {}, lambda x: x, esquema=contrato)
        formato = m.client.chat.completions.create.call_args.kwargs['response_format']
        self.assertEqual(formato['type'], 'json_schema')
        self.assertIs(formato['json_schema']['strict'], True)
        self.assertEqual(formato['json_schema']['schema'], contrato)

    def test_rechazo_de_esquema_no_degrada_a_texto_libre(self):
        m = self.motor()
        sdk = self.sdk(m, [])
        error = sdk.BadRequestError()
        error.body = {'error': {'code': 'json_validate_failed', 'message': 'response_format invalid'}}
        m.client.chat.completions.create.side_effect = [error]
        with patch.dict(sys.modules, {'openai': sdk}), self.assertRaises(sdk.BadRequestError):
            m._pedir_json('Contrato', {}, lambda x: x, esquema=esquema_salida(['PM2.5'], 'plan'))
        self.assertEqual(m.client.chat.completions.create.call_count, 1)

    def test_todos_los_objetos_del_esquema_son_cerrados_y_obligatorios(self):
        def revisar(nodo):
            if isinstance(nodo, dict):
                if nodo.get('type') == 'object':
                    self.assertIs(nodo['additionalProperties'], False)
                    self.assertEqual(set(nodo['required']), set(nodo['properties']))
                for v in nodo.values():
                    revisar(v)
            elif isinstance(nodo, list):
                for v in nodo:
                    revisar(v)
        for tipo in ('interpretacion', 'plan', 'fase'):
            revisar(esquema_salida(['TEMP', 'O3', 'month'], tipo))

    def test_cache_de_respuestas_validas_no_repite_red_y_aisla_mutaciones(self):
        m = self.motor()
        sdk = self.sdk(m, [self.respuesta('{"dato":[1]}')])
        with patch.dict(sys.modules, {'openai': sdk}):
            primero = m._pedir_json('Contrato', {'pregunta': 'A'}, lambda x: x)
            primero['dato'].append(9)
            segundo = m._pedir_json('Contrato', {'pregunta': 'A'}, lambda x: x)
        self.assertEqual(segundo, {'dato': [1]})
        self.assertEqual(m.client.chat.completions.create.call_count, 1)

    def test_repetir_pregunta_reanuda_fase_pendiente_tras_cuota(self):
        m = self.motor('secuencial')
        sdk = self.sdk(m, [])
        error = sdk.RateLimitError()
        error.body = {'error': {'message': 'tokens per minute (TPM). Please try again in 90s.'}}
        m.client.chat.completions.create.side_effect = [
            self.respuesta(json.dumps(interpretacion())),
            self.respuesta(json.dumps(fase(2))),
            self.respuesta(json.dumps(fase(3))),
            self.respuesta(json.dumps(fase(4))), error,
            self.respuesta(json.dumps(fase(5))),
        ]
        with patch.dict(sys.modules, {'openai': sdk}):
            with self.assertRaises(sdk.RateLimitError):
                m.planificar('Pregunta')
            llamadas_antes = m.client.chat.completions.create.call_count
            plan = m.planificar('Pregunta')
        self.assertEqual(m.client.chat.completions.create.call_count - llamadas_antes, 1)
        self.assertEqual([f['numero'] for f in plan['fases']], [2, 3, 4, 5])

    def test_cache_no_reutiliza_contextos_distintos(self):
        m = self.motor()
        sdk = self.sdk(m, [self.respuesta('{}'), self.respuesta('{}')])
        with patch.dict(sys.modules, {'openai': sdk}):
            m._pedir_json('Contrato', {'pregunta': 'A'}, lambda x: x)
            m._pedir_json('Contrato', {'pregunta': 'B'}, lambda x: x)
        self.assertEqual(m.client.chat.completions.create.call_count, 2)

    def test_cuota_de_treinta_segundos_se_puede_recuperar(self):
        m = self.motor()
        sdk = self.sdk(m, [])
        error = sdk.RateLimitError()
        error.body = {'error': {'message': 'tokens per minute (TPM). Please try again in 30.465s.'}}
        m.client.chat.completions.create.side_effect = [error, self.respuesta()]
        with patch.dict(sys.modules, {'openai': sdk}), patch('lightVA.sleep') as pausa:
            m._pedir_json('Contrato', {}, lambda x: x)
        pausa.assert_called_once_with(30.715)

    def test_prescribir_duplicado_identico_no_regenera(self):
        m = self.motor()
        sdk = self.sdk(m, [self.respuesta('{"prescribir":"Propuesta","prescribir":"Propuesta"}')])
        with patch.dict(sys.modules, {'openai': sdk}):
            resultado = m._pedir_json('Contrato', {}, lambda x: x)
        self.assertEqual(resultado, {'prescribir': 'Propuesta'})
        self.assertEqual(m.client.chat.completions.create.call_count, 1)

    def test_prescribir_distinto_se_repara_solo_el_campo(self):
        m = self.motor()
        sdk = self.sdk(m, [self.respuesta('{"descripcion":"Planificar criterio","prescribir":"Opción A","prescribir":"Opción B"}'),
                           self.respuesta('{"textos":[{"id":"0","texto":"Propuesta conciliada"}]}')])
        with patch.dict(sys.modules, {'openai': sdk}):
            resultado = m._pedir_json('Contrato', {'perfil': 'CONTEXTO_COMPLETO'}, lambda x: x)
        self.assertEqual(resultado['prescribir'], 'Propuesta conciliada')
        self.assertEqual(resultado['descripcion'], 'Planificar criterio')
        llamadas = m.client.chat.completions.create.call_args_list
        self.assertEqual(len(llamadas), 2)
        reparacion = llamadas[1].kwargs
        self.assertNotIn('CONTEXTO_COMPLETO', str(reparacion['messages']))
        self.assertIn('Opción A', reparacion['messages'][1]['content'])
        self.assertIn('Opción B', reparacion['messages'][1]['content'])
        self.assertEqual(reparacion['max_completion_tokens'], 450)

    def test_cuota_durante_correccion_conserva_plan_sin_regenerarlo(self):
        m = self.motor()
        sdk = self.sdk(m, [])
        error = sdk.RateLimitError()
        error.body = {'error': {'message': 'tokens per minute (TPM). Please try again in 90s.'}}
        m.client.chat.completions.create.side_effect = [
            self.respuesta('{"prescribir":"Opción A","prescribir":"Opción B"}'), error,
            self.respuesta('{"textos":[{"id":"0","texto":"Propuesta conciliada"}]}'),
        ]
        with patch.dict(sys.modules, {'openai': sdk}):
            with self.assertRaises(sdk.RateLimitError):
                m._pedir_json('Contrato', {}, lambda x: x)
            antes = m.client.chat.completions.create.call_count
            resultado = m._pedir_json('Contrato', {}, lambda x: x)
        self.assertEqual(m.client.chat.completions.create.call_count - antes, 1)
        self.assertEqual(resultado['prescribir'], 'Propuesta conciliada')

    def test_dos_429_cortos_se_recuperan_sin_reprocesar(self):
        m = self.motor()
        sdk = self.sdk(m, [])
        def cuota(segundos):
            error = sdk.RateLimitError()
            error.body = {'error': {'message': f'tokens per minute (TPM). Please try again in {segundos}s.'}}
            return error
        m.client.chat.completions.create.side_effect = [cuota(12), cuota(14.64), self.respuesta('{}')]
        with patch.dict(sys.modules, {'openai': sdk}), patch('lightVA.sleep') as pausa:
            resultado = m._pedir_json('Contrato', {}, lambda x: x)
        self.assertEqual(resultado, {})
        self.assertEqual(m.client.chat.completions.create.call_count, 3)
        self.assertEqual(pausa.call_args_list, [unittest.mock.call(12.25), unittest.mock.call(14.89)])

    def test_espera_total_no_supera_45_segundos(self):
        m = self.motor()
        sdk = self.sdk(m, [])
        error = sdk.RateLimitError()
        error.body = {'error': {'message': 'tokens per minute (TPM). Please try again in 30s.'}}
        m.client.chat.completions.create.side_effect = [error, error]
        with patch.dict(sys.modules, {'openai': sdk}), patch('lightVA.sleep') as pausa:
            with self.assertRaises(sdk.RateLimitError):
                m._pedir_json('Contrato', {}, lambda x: x)
        pausa.assert_called_once_with(30.25)
        self.assertEqual(m.client.chat.completions.create.call_count, 2)

    def test_json_invalido_solo_reintenta_una_vez(self):
        m = self.motor()
        sdk = self.sdk(m, [self.respuesta('no JSON'), self.respuesta('no JSON')])
        with patch.dict(sys.modules, {'openai': sdk}), self.assertRaises(ValueError):
            m._pedir_json('Contrato', {}, lambda x: x)
        self.assertEqual(m.client.chat.completions.create.call_count, 2)


class TestActividades(unittest.TestCase):
    def actividades(self):
        return {'actividades': [dict(fase=n, tarea=f'Tarea {n}', tipo='analisis',
            **fase(n)['tareas'][0]['subtareas'][0]) for n in FASES]}

    def test_agrupar_no_pierde_metodos_verificaciones_ni_columnas(self):
        obj = self.actividades()
        sub = dict(obj['actividades'][0], descripcion='Segunda subtarea', variables=['TEMP'])
        obj['actividades'].append(sub)
        bloques = agrupar_actividades(obj)
        tarea = bloques['Plan']['tareas'][0]
        self.assertEqual(tarea['variables'], ['PM2.5', 'TEMP'])
        self.assertEqual(len(tarea['subtareas']), 2)
        self.assertEqual(tarea['subtareas'][1]['criterio_verificacion'], sub['criterio_verificacion'])
        self.assertNotIn('id', obj['actividades'][0])

    def test_no_pierde_el_andamiaje_al_reconstruir_el_plan(self):
        obj = self.actividades()
        bloques = agrupar_actividades(obj)
        sub = bloques['Plan']['tareas'][0]['subtareas'][0]
        for campo in CAMPOS_PEDAGOGICOS:
            self.assertEqual(sub[campo], obj['actividades'][0][campo])
        sub['criterios_evaluacion'].append('Otro')
        self.assertNotIn('Otro', obj['actividades'][0]['criterios_evaluacion'])

    def test_rechaza_tarea_sin_evidencia_o_sin_andamiaje(self):
        for campo in CAMPOS_PEDAGOGICOS:
            obj = self.actividades()
            del obj['actividades'][0][campo]
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                agrupar_actividades(obj)

    def test_esquemas_exigen_pedagogia_y_no_asignan_un_grado(self):
        for tipo in ('actividades', 'fase'):
            esquema = esquema_salida(['PM2.5'], tipo)
            sub = (esquema['properties']['actividades']['items'] if tipo == 'actividades'
                   else esquema['$defs']['Subtarea'])
            self.assertTrue(set(CAMPOS_PEDAGOGICOS).issubset(sub['required']))
            self.assertNotIn('grado_seleccionado', sub['properties'])
            self.assertNotIn('dominio', sub['properties'])

    def test_rechaza_fase_omitida_y_numero_fuera_de_rango(self):
        for modificar in (lambda x: x['actividades'].pop(),
                           lambda x: x['actividades'][0].update(fase=1)):
            obj = self.actividades()
            modificar(obj)
            with self.assertRaises(ValueError):
                agrupar_actividades(obj)


class TestDecodificarJSON(unittest.TestCase):
    def test_unico_objeto_se_conserva(self):
        self.assertEqual(decodificar_json('{"tareas": []}'), {'tareas': []})

    def test_fases_separadas_se_unen_sin_perder_contenido(self):
        bloques = {nombre: {'tareas': [nombre]} for nombre in FASES.values()}
        texto = '\n'.join(json.dumps({k: v}) for k, v in bloques.items())
        self.assertEqual(decodificar_json(texto), bloques)

    def test_rechaza_texto_extra_fases_incompletas_y_duplicados(self):
        for texto in ('{"Plan":{}} explicación', '{"Plan":{}} {"Datos":{}}',
                      '{"Plan":{}} {"Plan":{}}', '{"objetivo":"a"} {"objetivo":"b"}',
                      '{"Plan":{},"Plan":{}}'):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                decodificar_json(texto)


if __name__ == '__main__':
    unittest.main()
