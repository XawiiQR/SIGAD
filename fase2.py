"""Fase Plan: evidencia evaluada, BKT, política y generación independientes."""
import copy
import hashlib
import json
import threading
import time
import uuid
from collections import OrderedDict

from flask import jsonify, request
from motor_fase2 import HABILIDADES, RUBRICA, MotorFase2
from calidad_fase2 import resumen_calidad, detalle_calidad

ACCIONES = {
    'revisar_faltantes': 'Revisar los datos faltantes antes de decidir',
    'imputar': 'Completar valores faltantes (imputación), eligiendo el método en la fase 3',
    'excluir_faltantes': 'Analizar solo registros completos, revisando la pérdida de cobertura',
    'revisar_atipicos': 'Revisar los valores atípicos antes de decidir si son errores',
    'conservar_atipicos': 'Conservar los valores atípicos como observaciones por verificar',
    'construir_fecha': 'Organizar las columnas temporales para construir la fecha',
    'conservar_unidades': 'Conservar las unidades originales',
    'evaluar_escalado': 'Evaluar el escalado según el análisis que se realizará',
    'revisar_categorias': 'Revisar las categorías y sus frecuencias',
    'excluir_identificador': 'Usar el identificador solo para localizar registros',
    'revisar_coordenadas': 'Comprobar las coordenadas y su sistema de referencia',
}


def acciones_disponibles(variable, contexto):
    col, rol = variable['columna'], variable['rol']
    acciones = []
    if contexto['faltantes'].get(col):
        acciones += ['revisar_faltantes', 'imputar', 'excluir_faltantes']
    if col in contexto['atipicos_iqr']:
        acciones += ['revisar_atipicos', 'conservar_atipicos']
    acciones += {'medida': ['conservar_unidades', 'evaluar_escalado'],
                 'tiempo': ['construir_fecha'], 'categoria': ['revisar_categorias'],
                 'identificador': ['excluir_identificador'],
                 'coordenada': ['revisar_coordenadas']}.get(rol, [])
    return acciones


def objeto(resultado):
    if isinstance(resultado, str):
        resultado = json.loads(resultado)
    if not isinstance(resultado, dict):
        raise ValueError("Se esperaba un objeto JSON.")
    return copy.deepcopy(resultado)


def texto(valor, limite=4000):
    if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= limite:
        raise ValueError("Texto ausente o demasiado largo.")
    return valor.strip()


def validar_plan(resultado, columnas):
    plan = objeto(resultado)
    pasos = plan.get('pasos')
    if not isinstance(pasos, list) or not 1 <= len(pasos) <= 15:
        raise ValueError("El plan debe contener entre uno y quince pasos.")
    limpios = []
    for paso in pasos:
        if not isinstance(paso, dict):
            raise ValueError("Paso inválido.")
        variables = paso.get('variables')
        if (not isinstance(variables, list) or not variables or
                any(not isinstance(v, str) or v not in columnas for v in variables)):
            raise ValueError("El plan debe referirse a columnas existentes.")
        limpios.append({'accion': texto(paso.get('accion'), 1500),
                        'variables': list(dict.fromkeys(variables)),
                        'justificacion': texto(paso.get('justificacion'), 1500)})
    return {'pasos': limpios}


def validar_evaluacion(resultado, columnas):
    r = objeto(resultado)
    criterios = r.get('criterios')
    if not isinstance(criterios, dict) or set(criterios) != set(HABILIDADES):
        raise ValueError("Rúbrica incompleta.")
    limpios = {}
    for habilidad, criterio in criterios.items():
        if (not isinstance(criterio, dict) or type(criterio.get('puntuacion')) is not int
                or criterio['puntuacion'] not in (0, 1, 2)):
            raise ValueError("Puntuación inválida.")
        limpios[habilidad] = {'puntuacion': criterio['puntuacion'],
                             'explicacion': texto(criterio.get('explicacion'), 1500)}
    variables = r.get('variables_utilizadas')
    if (not isinstance(variables, list) or not variables or
            any(not isinstance(v, str) or v not in columnas for v in variables)):
        raise ValueError("Variables de evaluación inválidas.")
    completa = all(c['puntuacion'] == 2 for c in limpios.values())
    # El evaluador no puede cerrar una tarea con una etiqueta de éxito incoherente.
    plan = validar_plan(r.get('plan'), columnas) if completa else None
    return {'criterios': limpios, 'variables_utilizadas': variables,
            'feedback': texto(r.get('feedback'), 2000), 'admisible': True,
            'completa': completa, 'plan': plan}


def validar_apoyo(resultado, nivel, columnas):
    r = objeto(resultado)
    mensaje = texto(r.get('mensaje'), 2000)
    if nivel == 2:
        if set(r) != {'mensaje'}:
            raise ValueError("Orientar solo admite una pista.")
        return {'grado': nivel, 'mensaje': mensaje}
    if nivel == 3:
        opciones = r.get('opciones')
        if not isinstance(opciones, list) or len(opciones) != 3:
            raise ValueError("Dirigir requiere tres planes alternativos.")
        planes = [validar_plan(p, columnas) for p in opciones]
        if len({json.dumps(p, sort_keys=True, ensure_ascii=False) for p in planes}) != 3:
            raise ValueError("Las alternativas deben ser diferentes.")
        return {'grado': nivel, 'mensaje': mensaje, 'opciones': planes}
    if nivel == 4:
        return {'grado': nivel, 'mensaje': mensaje, 'plan': validar_plan(r.get('plan'), columnas)}
    raise ValueError("No corresponde generar apoyo.")


def plan_desde_seleccion(seleccion):
    """Organiza decisiones ya guardadas; no añade tratamientos del modelo."""
    pasos = [{'accion': 'Utilizar las variables seleccionadas para la investigación',
              'variables': list(seleccion['variables']),
              'justificacion': 'Variables elegidas por el estudiante para responder su pregunta.'}]
    for accion, descripcion in ACCIONES.items():
        variables = [v for v in seleccion['variables']
                     if accion in seleccion.get('tratamientos', {}).get(v, [])]
        if variables:
            pasos.append({'accion': descripcion, 'variables': variables,
                          'justificacion': 'Decisión de preparación elegida en el formulario.'})
    return {'pasos': pasos}


def prescribir_plan(contexto):
    """Resuelve el plan desde el objetivo confirmado, no desde elecciones pendientes."""
    objetivo = contexto['objetivo']
    roles = {v['columna']: v['rol'] for v in contexto['variables']}
    columnas = [c for c in objetivo.get('variables', []) if c in roles]
    vista = objetivo.get('contexto', {}).get('vista', '')
    if vista in ('evolucion', 'ciclicidad', 'variabilidad'):
        temporales = [c for c in roles if roles[c] == 'tiempo']
        componentes = [c for c in ('year', 'month', 'day', 'hour') if c in temporales]
        columnas += componentes or temporales[:1]
    columnas = list(dict.fromkeys(columnas))
    if not columnas:
        raise ValueError('El objetivo confirmado no identifica las variables necesarias.')
    tratamientos = {}
    medidas = [c for c in columnas if roles[c] == 'medida']
    for c in columnas:
        acciones = []
        if contexto['faltantes'].get(c):
            acciones.append('revisar_faltantes')
        if c in contexto['atipicos_iqr']:
            acciones.append('conservar_atipicos')
        if roles[c] == 'medida':
            acciones.append('conservar_unidades')
            if len(medidas) > 1:
                acciones.append('evaluar_escalado')
        elif roles[c] == 'tiempo':
            acciones.append('construir_fecha')
        elif roles[c] == 'categoria':
            acciones.append('revisar_categorias')
        elif roles[c] == 'coordenada':
            acciones.append('revisar_coordenadas')
        tratamientos[c] = acciones
    seleccion = {'variables': columnas, 'tratamientos': tratamientos}
    plan = plan_desde_seleccion(seleccion)
    for paso in plan['pasos']:
        paso['justificacion'] = 'Decisión del sistema para responder: ' + objetivo['pregunta']
    return seleccion, plan


def error_evaluacion(error):
    """Mensajes útiles sin mostrar credenciales ni respuestas crudas del proveedor."""
    status = getattr(error, 'status_code', None)
    nombre = type(error).__name__
    if status == 429:
        return 'proveedor_limite', 'El servicio de IA alcanzó su límite de uso. Tu selección está guardada; vuelve a intentarlo cuando se restablezca la cuota.'
    if status in (401, 403):
        return 'proveedor_acceso', 'El servicio de IA rechazó las credenciales o el acceso al modelo. Revisa la configuración del proveedor.'
    if nombre in ('APITimeoutError', 'TimeoutError'):
        return 'proveedor_tiempo', 'El servicio de IA tardó demasiado en responder. Tu selección está guardada; puedes reintentar.'
    if nombre in ('APIConnectionError', 'ConnectionError'):
        return 'proveedor_conexion', 'No se pudo conectar con el servicio de IA. Comprueba la conexión y reintenta.'
    if status in (400, 413, 422):
        return 'proveedor_solicitud', 'El servicio de IA rechazó la solicitud o su tamaño. Tu selección está guardada.'
    if isinstance(error, (ValueError, TypeError, KeyError)):
        return 'evaluacion_formato', 'La IA devolvió una evaluación incompleta o con formato incorrecto. Tu selección está guardada; vuelve a evaluar.'
    return 'proveedor_error', 'No se pudo completar la evaluación con el servicio de IA. Tu selección está guardada; puedes reintentar.'


def diagnosticar(explorador, objetivo):
    """Solo calcula resúmenes sobre la copia de datos de fase 1; no transforma."""
    df = explorador.df
    nulos = {str(c): int(n) for c, n in df.isna().sum().items() if n > 0}
    atipicos, escalas = {}, {}
    for col in explorador.numericas:
        s = explorador.numerica(col).dropna()
        if s.empty:
            continue
        q1, q3 = s.quantile([.25, .75])
        iqr = q3 - q1
        n = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
        if n:
            atipicos[col] = {'cantidad': n, 'limite_inferior': float(q1 - 1.5 * iqr),
                            'limite_superior': float(q3 + 1.5 * iqr)}
        escalas[col] = {'min': float(s.min()), 'max': float(s.max()),
                        'rango': float(s.max() - s.min())}
    return {'version_dataset': explorador.perfil['version'], 'filas': len(df),
            'objetivo': copy.deepcopy(objetivo),
            'variables': copy.deepcopy(explorador.perfil['variables']),
            'faltantes': nulos, 'atipicos_iqr': atipicos, 'escalas': escalas,
            'temporal': copy.deepcopy(explorador.perfil['temporal']),
            'espacial': copy.deepcopy(explorador.perfil['espacial']),
            'advertencias': ['Un valor atípico detectado no es necesariamente un error.',
                'Escalar depende del método y objetivo, no solo de los rangos.',
                'Las decisiones del plan no ejecutan cambios sobre los datos.']}


def registrar_fase2(app, evaluar, generar):
    sesiones, lock = OrderedDict(), threading.RLock()
    app.extensions['fase2'] = {'sesiones': sesiones, 'lock': lock}

    def recuperar():
        s = sesiones.get(request.headers.get('X-SiGAD-Phase2', ''))
        if s is None:
            raise KeyError('Sesión no encontrada.')
        s['ultima_actividad'] = time.monotonic()
        return s

    def estado(s):
        return copy.deepcopy({'sesion': s['token'], 'origen_fase1': s['origen'],
            'tarea': s['tarea'], 'revision': s['revision'], 'completada': s['completada'],
            'contexto': s['contexto'], 'motor': s['motor'].resumen(),
            'resultado': s.get('resultado'), 'apoyo': s.get('apoyo'), 'plan': s.get('plan'),
            'borrador': s.get('borrador', {'variables': [], 'tratamientos': {}})})

    def entrada(s):
        return copy.deepcopy({'tarea': {'id': s['tarea'], 'fase': 'Plan',
                'consigna': 'Propón y justifica un plan de preparación para responder la pregunta confirmada.'},
            'rubrica': {'version': 'fase2-v1', 'criterios': RUBRICA,
                       'escala': {'0': 'ausente o incorrecto', '1': 'parcial', '2': 'adecuado'}},
            'contexto_verificable': s['contexto'],
            'seleccion_usuario': s.get('borrador'),
            'grado_seleccionado': s['motor'].nivel,
            'dominio': s['motor'].resumen()['habilidades'],
            'ayuda_recibida': {'grado': s['motor'].nivel, 'autonoma': s['motor'].nivel == 1,
                              'contenido': s.get('apoyo'), 'historial': s['ayudas'][-5:]},
            'historial': s['evaluaciones'][-5:], 'respuesta_usuario': s.get('ultima_respuesta'),
            'evaluacion_actual': s.get('resultado'),
            'restricciones': ['No modificar datos, dominio ni grado de ayuda.',
                              'Respetar objetivo, cobertura y columnas verificadas.']})

    def comprobar_revision(s, datos):
        return s['ocupada'] or type(datos.get('revision')) is not int or datos['revision'] != s['revision']

    @app.post('/api/fase2/sesion')
    def sesion_f2():
        # El objetivo proviene del servidor; no se acepta un objetivo inventado por el cliente.
        fase1 = app.extensions.get('fase1')
        if not fase1:
            return jsonify(error='La fase 1 no está configurada.'), 503
        origen = request.headers.get('X-SiGAD-Session', '')
        with fase1['lock']:
            anterior = fase1['sesiones'].get(origen)
            if not anterior:
                return jsonify(error='Inicia o recupera tu sesión de fase 1.'), 404
            if not anterior['completada'] or not anterior.get('objetivo'):
                return jsonify(error='Primero confirma una pregunta en la fase 1.'), 409
            objetivo = copy.deepcopy(anterior['objetivo'])
            tarea_origen = anterior['tarea']
        with lock:
            ahora = time.monotonic()
            for token in list(sesiones):
                if ahora - sesiones[token]['ultima_actividad'] > 24 * 3600:
                    del sesiones[token]
            for s in sesiones.values():
                if s['origen'] == origen and s['tarea_origen'] == tarea_origen:
                    return jsonify(estado(s))
            token = str(uuid.uuid4())
            s = {'token': token, 'origen': origen, 'tarea_origen': tarea_origen,
                 'tarea': str(uuid.uuid4()), 'revision': 0, 'completada': False,
                 'contexto': diagnosticar(fase1['explorador'], objetivo),
                 'motor': MotorFase2(**app.config.get('FASE2_BKT', {})),
                 'ocupada': False, 'ultima_actividad': ahora, 'respuestas': {},
                 'eventos': [], 'evaluaciones': [], 'ayudas': [],
                 'borrador': {'variables': [], 'tratamientos': {}}}
            sesiones[token] = s
            if len(sesiones) > 500:
                sesiones.popitem(last=False)
            return jsonify(estado(s))

    @app.get('/api/fase2/estado')
    def estado_f2():
        with lock:
            try:
                return jsonify(estado(recuperar()))
            except KeyError:
                return jsonify(error='Sesión de fase 2 no encontrada.'), 404

    @app.get('/api/fase2/muestra')
    def muestra_f2():
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error='Sesión de fase 2 no encontrada.'), 404
        df = app.extensions['fase1']['explorador'].df
        # Esta muestra es solo para la interfaz; no se añade al contexto del LLM.
        muestra = json.loads(df.head(5).to_json(orient='split', date_format='iso'))
        ejemplos = {}
        for col in df.columns:
            valores = json.loads(df[col].dropna().head(30).to_json(orient='values', date_format='iso'))
            ejemplos[str(col)] = list(dict.fromkeys(v for v in valores if v is not None))[:3]
        return jsonify(columnas=[str(c) for c in df.columns], filas=muestra['data'],
                       ejemplos=ejemplos, total_filas=len(df), calidad_visual=True,
                       acciones={v['columna']: [{'id': a, 'texto': ACCIONES[a]}
                                 for a in acciones_disponibles(v, s['contexto'])]
                                 for v in s['contexto']['variables']})

    @app.get('/api/fase2/calidad')
    def calidad_f2():
        with lock:
            try:
                recuperar()
            except KeyError:
                return jsonify(error='Sesión de fase 2 no encontrada.'), 404
        try:
            explorador = app.extensions['fase1']['explorador']
            variable = request.args.get('variable', '')
            if request.args.get('fila') is not None:
                return jsonify(detalle_calidad(explorador, variable, int(request.args['fila'])))
            return jsonify(resumen_calidad(explorador, variable))
        except (ValueError, TypeError):
            return jsonify(error='Selecciona una variable y una observación válidas.'), 400

    @app.post('/api/fase2/borrador')
    def borrador_f2():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error='Solicitud inválida.'), 400
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error='Sesión de fase 2 no encontrada.'), 404
            if comprobar_revision(s, datos) or s['completada']:
                return jsonify(error='La sesión cambió o el plan ya fue confirmado.'), 409
            variables, tratamientos = datos.get('variables'), datos.get('tratamientos', {})
            disponibles = {v['columna']: acciones_disponibles(v, s['contexto'])
                           for v in s['contexto']['variables']}
            if (not isinstance(variables, list) or
                    any(not isinstance(v, str) or v not in disponibles for v in variables)
                    or not isinstance(tratamientos, dict)):
                return jsonify(error='Selecciona columnas existentes.'), 400
            if any(v not in variables or not isinstance(acciones, list) or
                   any(not isinstance(a, str) or a not in disponibles[v] for a in acciones)
                   for v, acciones in tratamientos.items()):
                return jsonify(error='La preparación no corresponde a las variables seleccionadas.'), 400
            # No aceptar tratamientos mutuamente excluyentes como una decisión final.
            if any({'imputar', 'excluir_faltantes'}.issubset(a) or
                   {'conservar_unidades', 'evaluar_escalado'}.issubset(a)
                   for a in tratamientos.values()):
                return jsonify(error='Elige una alternativa de tratamiento por decisión.'), 400
            s['borrador'] = {'variables': list(dict.fromkeys(variables)),
                'tratamientos': {v: list(dict.fromkeys(a)) for v, a in tratamientos.items()}}
            s.pop('resultado', None)
            s['eventos'].append({'tipo': 'seleccion_variables', 'grado': s['motor'].nivel,
                                 'borrador': copy.deepcopy(s['borrador'])})
            s['revision'] += 1
            return jsonify(estado(s))

    @app.post('/api/fase2/evaluar')
    def evaluar_f2():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error='Solicitud inválida.'), 400
        try:
            propuesta = texto(datos.get('propuesta'))
            intento = texto(datos.get('intento'), 100)
        except ValueError:
            return jsonify(error='Escribe tu plan (máximo 4000 caracteres) e identifica el intento.'), 400
        huella = hashlib.sha256(propuesta.encode()).hexdigest()
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error='Sesión de fase 2 no encontrada.'), 404
            anterior = s['respuestas'].get(intento)
            if anterior:
                if anterior['huella'] != huella:
                    return jsonify(error='Ese intento corresponde a otra respuesta.'), 409
                return jsonify(anterior['estado'])
            if comprobar_revision(s, datos) or s['completada']:
                return jsonify(error='La sesión cambió o el plan ya fue confirmado.'), 409
            contexto = entrada(s)
            contexto['respuesta_usuario'] = propuesta
            s['ocupada'] = True
        try:
            respuesta_modelo = objeto(evaluar(propuesta, contexto))
            elegidas = contexto.get('seleccion_usuario', {}).get('variables', [])
            if elegidas:
                # La rúbrica y el plan son responsabilidades distintas: un plan
                # mal redactado por el LLM no invalida sus criterios de evaluación.
                respuesta_modelo['plan'] = plan_desde_seleccion(contexto['seleccion_usuario'])
            resultado = validar_evaluacion(respuesta_modelo,
                [v['columna'] for v in s['contexto']['variables']])
            if resultado['completa'] and elegidas:
                for paso in resultado['plan']['pasos']:
                    if not set(paso['variables']).issubset(elegidas):
                        raise ValueError('El plan añade columnas no elegidas por el estudiante.')
        except Exception as error:
            codigo, mensaje = error_evaluacion(error)
            app.logger.warning('Evaluación fase 2: codigo=%s tipo=%s status=%s',
                               codigo, type(error).__name__, getattr(error, 'status_code', None))
            with lock:
                s['ocupada'] = False
            return jsonify(error=mensaje, codigo=codigo, reintentable=True), 502
        with lock:
            antes = s['motor'].resumen()
            completada, grado = s['motor'].registrar(s['tarea'], intento,
                {k: v['puntuacion'] for k, v in resultado['criterios'].items()})
            s['ocupada'] = False
            s['completada'], s['resultado'] = completada, resultado
            s['ultima_respuesta'] = propuesta
            s.pop('apoyo', None)
            observacion = {'respuesta': propuesta, 'evaluacion': resultado, 'grado': grado}
            s['evaluaciones'].append(copy.deepcopy(observacion))
            s['eventos'].append({'tipo': 'evaluacion', 'intento': intento, 'entrada': contexto,
                                'antes': antes, 'despues': s['motor'].resumen(), **observacion})
            if completada:
                s['plan'] = {'origen': 'usuario', 'contenido': resultado['plan'],
                             'propuesta_original': propuesta, 'objetivo': s['contexto']['objetivo'],
                             'version_dataset': s['contexto']['version_dataset'], 'ejecutado': False}
            s['revision'] += 1
            respuesta = estado(s)
            s['respuestas'][intento] = {'huella': huella, 'estado': respuesta}
            return jsonify(respuesta)

    @app.post('/api/fase2/accion')
    def accion_f2():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error='Solicitud inválida.'), 400
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error='Sesión de fase 2 no encontrada.'), 404
            if comprobar_revision(s, datos) or s['completada']:
                return jsonify(error='La sesión cambió o el plan ya fue confirmado.'), 409
            accion = datos.get('accion')
            if accion == 'ayuda':
                s['motor'].ayuda()
            elif accion == 'prescribir':
                s['motor'].prescribir()
            elif accion == 'timeout':
                if not s['motor'].registrar_timeout(s['tarea']):
                    return jsonify(estado(s))
            else:
                return jsonify(error='Acción no disponible.'), 400
            evento = {'tipo': accion, 'grado': s['motor'].nivel}
            s['ayudas'].append(evento)
            s['eventos'].append(evento)
            s.pop('apoyo', None)
            s['revision'] += 1
            return jsonify(estado(s))

    @app.post('/api/fase2/apoyo')
    def apoyo_f2():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error='Solicitud inválida.'), 400
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error='Sesión de fase 2 no encontrada.'), 404
            if comprobar_revision(s, datos):
                return jsonify(error='La sesión cambió. Actualiza y reintenta.'), 409
            if s['completada'] or s['motor'].nivel == 1 or s.get('apoyo'):
                return jsonify(estado(s))
            contexto = entrada(s)
            grado = s['motor'].nivel
            s['ocupada'] = True
        try:
            if grado == 4:
                seleccion_prescrita, plan_prescrito = prescribir_plan(s['contexto'])
                apoyo = {'grado': 4, 'mensaje': 'El sistema seleccionó las variables del objetivo y estructuró su preparación. El plan pasa a la fase Datos; todavía no se ejecutaron tratamientos.', 'plan': plan_prescrito}
            else:
                apoyo = validar_apoyo(generar(contexto), grado,
                                      [v['columna'] for v in s['contexto']['variables']])
        except Exception:
            with lock:
                s['ocupada'] = False
            return jsonify(error='No se obtuvo un apoyo válido. Reintenta; BKT no cambió.'), 502
        with lock:
            s['ocupada'] = False
            s['apoyo'] = apoyo
            s['ayudas'].append(copy.deepcopy(apoyo))
            s['eventos'].append({'tipo': 'apoyo', 'contenido': copy.deepcopy(apoyo)})
            if grado == 4:
                s['borrador'] = seleccion_prescrita
                s['completada'] = True
                s['plan'] = {'origen': 'prescrito', 'contenido': apoyo['plan'],
                             'objetivo': s['contexto']['objetivo'],
                             'version_dataset': s['contexto']['version_dataset'], 'ejecutado': False}
            s['revision'] += 1
            return jsonify(estado(s))

    @app.post('/api/fase2/seleccionar')
    def seleccionar_f2():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error='Solicitud inválida.'), 400
        with lock:
            try:
                s = recuperar()
            except KeyError:
                return jsonify(error='Sesión de fase 2 no encontrada.'), 404
            if comprobar_revision(s, datos) or s['completada'] or s['motor'].nivel != 3:
                return jsonify(error='La selección ya no está disponible.'), 409
            apoyo, indice = s.get('apoyo'), datos.get('indice')
            if not apoyo or type(indice) is not int or indice not in range(3):
                return jsonify(error='Selecciona uno de los tres planes.'), 400
            s['plan'] = {'origen': 'sugerido', 'contenido': copy.deepcopy(apoyo['opciones'][indice]),
                         'objetivo': s['contexto']['objetivo'],
                         'version_dataset': s['contexto']['version_dataset'], 'ejecutado': False}
            s['completada'] = True
            s['eventos'].append({'tipo': 'seleccion_asistida', 'indice': indice})
            s['revision'] += 1
            return jsonify(estado(s))
