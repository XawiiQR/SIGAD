"""Preparación reversible, calculada localmente sobre una copia del archivo."""
import io
import threading
import uuid
from collections import OrderedDict
import pandas as pd
import numpy as np
from flask import request, jsonify, send_file


def transformar(datos, columna, accion):
    if columna not in datos:
        raise ValueError('Selecciona una columna existente.')
    copia = datos.copy(deep=True)
    serie = copia[columna]
    if accion == 'conservar':
        return copia, 0
    if accion == 'excluir_nulos':
        return copia.loc[serie.notna()].copy(), int(serie.isna().sum())
    if not pd.api.types.is_numeric_dtype(serie):
        raise ValueError('Este tratamiento requiere una variable numérica.')
    validos = serie.dropna()
    if validos.empty:
        raise ValueError('No hay valores válidos para calcular este tratamiento.')
    if accion in ('media', 'mediana'):
        copia[columna] = serie.fillna(validos.mean() if accion == 'media' else validos.median())
    elif accion == 'normalizar':
        amplitud = validos.max() - validos.min()
        copia[columna] = (serie - validos.min()) / amplitud if amplitud else serie.where(serie.isna(), 0)
    elif accion in ('limitar_iqr', 'excluir_atipicos'):
        q1, q3 = validos.quantile([.25, .75])
        inferior, superior = q1 - 1.5*(q3-q1), q3 + 1.5*(q3-q1)
        if accion == 'excluir_atipicos':
            mascara = serie.notna() & ((serie < inferior) | (serie > superior))
            return copia.loc[~mascara].copy(), int(mascara.sum())
        copia[columna] = serie.clip(inferior, superior)
    else:
        raise ValueError('Tratamiento no reconocido.')
    cambios = ~(serie.eq(copia[columna]) | (serie.isna() & copia[columna].isna()))
    return copia, int(cambios.sum())


def grafico_preparacion(datos, columna):
    """Agrega todos los registros; conserva huecos y posiciones al excluir filas."""
    from fase1 import fechas_del_dataset
    serie = datos[columna]
    if not pd.api.types.is_numeric_dtype(serie):
        return None
    fechas = fechas_del_dataset(datos)
    temporal = fechas.notna().any()
    if temporal:
        grupos = fechas.dt.to_period('M')
        calendario = pd.period_range(grupos.min(), grupos.max(), freq='M')
        if len(calendario) > 2400:
            grupos = fechas.dt.to_period('Y')
            calendario = pd.period_range(grupos.min(), grupos.max(), freq='Y')
        agregado = pd.DataFrame({'grupo': grupos, 'valor': serie}).groupby('grupo')['valor'].agg(['mean','count','size']).reindex(calendario)
        puntos = [dict(x=str(i), valor=None if pd.isna(r['mean']) else float(r['mean']),
                       disponibles=int(r['count']) if pd.notna(r['count']) else 0,
                       total=int(r['size']) if pd.notna(r['size']) else 0) for i,r in agregado.iterrows()]
    else:
        # Los índices originales no se renumeran al excluir registros.
        grupos = pd.Series(datos.index // max(1, int((datos.index.max()+1)/120)) if len(datos) else [], index=datos.index, dtype='int64')
        agregado = pd.DataFrame({'grupo': grupos, 'valor': serie}).groupby('grupo')['valor'].agg(['mean','count','size'])
        puntos = [dict(x='Bloque '+str(int(i)+1), valor=None if pd.isna(r['mean']) else float(r['mean']),
                       disponibles=int(r['count']), total=int(r['size'])) for i,r in agregado.iterrows()]
    for punto in puntos:
        if temporal:
            mascara = grupos.astype(str).eq(punto['x'])
        else:
            mascara = grupos.eq(int(punto['x'].replace('Bloque ',''))-1)
        indices = datos.index[mascara & serie.isna()]
        if not len(indices):
            indices = datos.index[mascara]
        punto['fila'] = int(indices[0])+1 if len(indices) else None
    return dict(temporal=bool(temporal), puntos=puntos,
                media=None if serie.dropna().empty else float(serie.mean()),
                disponibles=int(serie.notna().sum()), nulos=int(serie.isna().sum()),
                sin_fecha=int(fechas.isna().sum()) if temporal else 0)


def ventana_nulos(antes, columna, despues=None, fila=None):
    """Mismas posiciones antes/después, dentro de una estación si existe."""
    from fase1 import fechas_del_dataset
    if antes.empty:
        return []
    faltantes = antes.index[antes[columna].isna()]
    centro = fila if fila in antes.index else faltantes[0] if len(faltantes) else antes.index[0]
    grupo = antes
    if 'station' in antes and pd.notna(antes.at[centro,'station']):
        grupo = antes.loc[antes['station'].eq(antes.at[centro,'station'])]
    fechas = fechas_del_dataset(grupo)
    orden = fechas.sort_values(kind='stable',na_position='last').index if fechas.notna().any() else grupo.index
    posicion = orden.get_loc(centro)
    indices = orden[max(0,posicion-10):posicion+21]
    salida = []
    for idx in indices:
        original = antes.at[idx,columna]
        eliminado = despues is not None and idx not in despues.index
        nuevo = despues.at[idx,columna] if despues is not None and not eliminado else original
        def limpio(v):
            return None if pd.isna(v) else v.item() if isinstance(v,np.generic) else v
        salida.append(dict(fila=int(idx)+1, fecha=None if pd.isna(fechas.at[idx]) else fechas.at[idx].isoformat(),
                           estacion=limpio(antes.at[idx,'station']) if 'station' in antes else None,
                           antes=limpio(original), despues=None if eliminado else limpio(nuevo),
                           eliminado=eliminado, imputado=bool(pd.isna(original) and not eliminado and pd.notna(nuevo))))
    return salida


def comparar_kde(serie):
    """KDE gaussiana exacta con rejilla y ancho comunes para las tres curvas."""
    if not pd.api.types.is_numeric_dtype(serie):
        return None
    observados = serie.dropna().to_numpy(dtype=float)
    observados = observados[np.isfinite(observados)]
    n, faltantes = len(observados), int(serie.isna().sum())
    def estadisticas(valores):
        return dict(n=len(valores), media=float(np.mean(valores)) if len(valores) else None,
                    desviacion=float(np.std(valores,ddof=1)) if len(valores)>1 else None,
                    varianza=float(np.var(valores,ddof=1)) if len(valores)>1 else None)
    base = dict(observados=n, faltantes=faltantes, estadisticas={'original':estadisticas(observados)})
    if n < 2 or np.ptp(observados) == 0:
        base.update(x=[], curvas={}, motivo='La KDE requiere al menos dos valores distintos. No se inventa una curva para datos constantes o insuficientes.')
        return base
    media, mediana = float(np.mean(observados)), float(np.median(observados))
    q1,q3 = np.quantile(observados,[.25,.75])
    sigma = float(np.std(observados,ddof=1))
    escala = min(sigma,float((q3-q1)/1.34)) if q3>q1 else sigma
    h = 1.06 * escala * n**(-.2)
    if not np.isfinite(h) or h <= 0:
        base.update(x=[],curvas={},motivo='No se pudo calcular un ancho de banda válido.')
        return base
    x = np.linspace(observados.min()-3*h,observados.max()+3*h,256)
    valores,pesos = np.unique(observados,return_counts=True)
    densidad = np.zeros(len(x))
    for inicio in range(0,len(valores),1024):
        z=(x[:,None]-valores[None,inicio:inicio+1024])/h
        densidad += np.exp(-.5*z*z) @ pesos[inicio:inicio+1024]
    densidad /= n*h*np.sqrt(2*np.pi)
    total=n+faltantes
    curvas={'original':densidad.tolist()}
    for nombre,centro in (('media',media),('mediana',mediana)):
        pico=np.exp(-.5*((x-centro)/h)**2)/(h*np.sqrt(2*np.pi))
        curvas[nombre]=(densidad*n/total+pico*faltantes/total).tolist()
        completos=np.concatenate([observados,np.full(faltantes,centro)])
        base['estadisticas'][nombre]=estadisticas(completos)
    base.update(x=x.tolist(),curvas=curvas,ancho_banda=float(h),
                centros={'media':media,'mediana':mediana}, motivo=None)
    return base


def dispersion_registros(antes, columna, despues=None):
    validos = antes[columna].dropna()
    if validos.empty:
        return []
    q1,q3=validos.quantile([.25,.75])
    inferior,superior=q1-1.5*(q3-q1),q3+1.5*(q3-q1)
    posiciones=np.linspace(0,len(validos)-1,min(800,len(validos)),dtype=int)
    puntos=[]
    for idx,v in validos.iloc[posiciones].items():
        eliminado=despues is not None and idx not in despues.index
        nuevo=despues.at[idx,columna] if despues is not None and not eliminado else v
        puntos.append(dict(fila=int(idx)+1, valor=float(v), atipico=bool(v<inferior or v>superior),
                           despues=None if eliminado or pd.isna(nuevo) else float(nuevo), eliminado=eliminado))
    return puntos


def resumen(datos, columnas):
    muestra = datos[columnas].head(8).astype(object).where(datos[columnas].head(8).notna(), None)
    diagnostico = {}
    for c in columnas:
        if not pd.api.types.is_numeric_dtype(datos[c]):
            continue
        validos = datos[c].dropna()
        if validos.empty:
            continue
        q1, q3 = validos.quantile([.25, .75])
        inferior, superior = q1 - 1.5*(q3-q1), q3 + 1.5*(q3-q1)
        candidatos = validos[(validos < inferior) | (validos > superior)]
        diagnostico[c] = dict(minimo=float(validos.min()), maximo=float(validos.max()),
                             candidatos=len(candidatos), disponibles=len(validos), media=float(validos.mean()), dispersion=dispersion_registros(datos,c), inferior=float(inferior), superior=float(superior),
                             q1=float(q1), mediana=float(validos.median()), q3=float(q3),
                             bigote_inferior=float(validos[validos>=inferior].min()),
                             bigote_superior=float(validos[validos<=superior].max()),
                             puntos=[dict(fila=int(idx)+1, valor=float(v), atipico=bool(v<inferior or v>superior))
                                     for idx,v in pd.concat([validos.loc[~validos.index.isin(candidatos.index)].iloc[::max(1,len(validos)//80)].head(80),
                                                            candidatos.iloc[::max(1,len(candidatos)//80)].head(80)]).items()],
                             ejemplos=[dict(fila=int(i)+1, valor=float(v)) for i,v in candidatos.head(8).items()])
    return {'kde': {c: comparar_kde(datos[c]) for c in columnas if pd.api.types.is_numeric_dtype(datos[c])}, 'ventanas': {c: ventana_nulos(datos,c) for c in columnas}, 'graficos': {c: grafico_preparacion(datos,c) for c in columnas if pd.api.types.is_numeric_dtype(datos[c])}, 'diagnostico': diagnostico, 'filas': len(datos), 'columnas': columnas,
            'nulos': {c: int(datos[c].isna().sum()) for c in columnas},
            'muestra': muestra.to_dict(orient='records'),
            'numericas': [c for c in columnas if pd.api.types.is_numeric_dtype(datos[c])]}


def registrar_fase3(app):
    sesiones, lock = OrderedDict(), threading.RLock()

    def recuperar():
        s = sesiones.get(request.headers.get('X-SiGAD-Phase3'))
        if s is None:
            raise ValueError('Vuelve a abrir la fase 3 desde tu plan confirmado.')
        return s

    def estado(s):
        return dict(sesion=s['token'], revision=s['revision'], nivel=s['nivel'],
                    plan=s['plan'], variables=s['variables'], medidas=s['medidas'], historial=s['historial'],
                    ayudas=s.get('ayudas', []), datos=resumen(s['datos'], s['variables']))

    @app.post('/api/fase3/sesion')
    def iniciar_datos():
        f2 = app.extensions['fase2']
        with f2['lock'], lock:
            anterior = f2['sesiones'].get(request.headers.get('X-SiGAD-Phase2'))
            if not anterior or not anterior.get('completada') or not anterior.get('plan'):
                return jsonify(error='Confirma primero el plan de la fase 2.'), 409
            for s in sesiones.values():
                if s['origen'] == anterior['token']:
                    return jsonify(estado(s))
            plan = anterior['plan']['contenido']
            columnas = list(dict.fromkeys(c for paso in plan['pasos'] for c in paso['variables']))
            original = app.extensions['fase1']['explorador'].df
            if not columnas or any(c not in original for c in columnas):
                return jsonify(error='El plan no contiene variables válidas.'), 400
            roles = {v['columna']: v.get('rol') for v in anterior.get('contexto', {}).get('variables', [])}
            medidas = [c for c in columnas if roles.get(c) == 'medida' or (
                c not in roles and pd.api.types.is_numeric_dtype(original[c])
                and c.lower() not in ('year','month','day','hour','no','id','latitude','longitude','latitud','longitud'))]
            token = str(uuid.uuid4())
            s = dict(token=token, origen=anterior['token'], plan=plan, variables=columnas, medidas=medidas,
                     datos=original.copy(deep=True), revision=0, nivel=1, historial=[], anteriores=[], previa=None, ayudas=[])
            sesiones[token] = s
            if len(sesiones) > 40:
                sesiones.popitem(last=False)
            return jsonify(estado(s))

    @app.post('/api/fase3/operacion')
    def operar_datos():
        with lock:
            try:
                s = recuperar()
                d = request.get_json(silent=True) or {}
                if d.get('revision') != s['revision']:
                    return jsonify(error='La vista cambió. Vuelve a abrir la fase 3.'), 409
                operacion = d.get('operacion')
                if operacion in ('ayuda','prescribir'):
                    anterior = s['nivel']
                    s['nivel'] = 4 if operacion == 'prescribir' else min(4, s['nivel']+1)
                    s['ayudas'].append(dict(tipo=operacion, anterior=anterior, nivel=s['nivel'], revision=s['revision']))
                elif operacion == 'ventana':
                    c, fila = d.get('columna'), d.get('fila')
                    if c not in s['variables'] or type(fila) is not int or fila-1 not in s['datos'].index:
                        raise ValueError('Selecciona un registro existente.')
                    previa = s['previa']
                    despues = previa['datos'] if previa and previa['columna'] == c else None
                    return jsonify(estado=estado(s), ventana=ventana_nulos(s['datos'],c,despues,fila-1))
                elif operacion == 'comparar':
                    c = d.get('columna')
                    if c not in s['variables']:
                        raise ValueError('Selecciona una variable de tu plan.')
                    alternativas = {}
                    for accion in ('conservar','media','mediana','excluir_nulos','limitar_iqr','excluir_atipicos','normalizar'):
                        try:
                            copia, cambios = transformar(s['datos'], c, accion)
                            alternativas[accion] = dict(cambios=cambios, datos=resumen(copia,[c]),
                                                       grafico=grafico_preparacion(copia,c))
                        except ValueError as e:
                            alternativas[accion] = dict(error=str(e))
                    return jsonify(estado=estado(s), escenarios=alternativas)
                elif operacion == 'escalas':
                    columnas = d.get('variables')
                    accion = d.get('accion')
                    if (not isinstance(columnas, list) or not columnas or
                            any(not isinstance(c,str) or c not in s['medidas'] for c in columnas)
                            or accion not in ('normalizar','conservar')):
                        raise ValueError('Selecciona medidas de tu plan para comparar sus escalas.')
                    columnas = list(dict.fromkeys(columnas))
                    nuevo = s['datos'].copy(deep=True)
                    ejemplos, parametros = [], {}
                    afectadas = pd.Series(False,index=nuevo.index)
                    for c in columnas:
                        serie = s['datos'][c]
                        validos = serie.dropna()
                        if validos.empty:
                            raise ValueError('La variable '+c+' no tiene valores válidos para normalizar.')
                        parametros[c] = dict(minimo=float(validos.min()), maximo=float(validos.max()))
                        nuevo, _ = transformar(nuevo,c,accion)
                        mascara = ~(serie.eq(nuevo[c]) | (serie.isna() & nuevo[c].isna()))
                        afectadas |= mascara
                        for idx in serie.index[mascara][:3]:
                            ejemplos.append(dict(fila=int(idx)+1, columna=c, antes=float(serie.at[idx]), despues=float(nuevo.at[idx,c])))
                    cambios = int(afectadas.sum())
                    s['previa'] = dict(datos=nuevo, columna=', '.join(columnas), accion=accion,
                                       cambios=cambios, variables=columnas, parametros=parametros)
                    return jsonify(estado=estado(s), previa=dict(cambios=cambios, ejemplos=ejemplos,
                                   variables=columnas, parametros=parametros, datos=resumen(nuevo,s['variables'])))
                elif operacion == 'previsualizar':
                    c, accion = d.get('columna'), d.get('accion')
                    if c not in s['variables']:
                        raise ValueError('Selecciona una variable de tu plan.')
                    nuevo, cambios = transformar(s['datos'], c, accion)
                    antes = s['datos']
                    indices = antes.index.difference(nuevo.index) if accion in ('excluir_nulos','excluir_atipicos') else antes.index[~(antes[c].eq(nuevo[c]) | (antes[c].isna() & nuevo[c].isna()))]
                    ejemplos = [{'fila': int(i)+1, 'antes': None if pd.isna(antes.at[i,c]) else antes.at[i,c].item() if isinstance(antes.at[i,c], np.generic) else antes.at[i,c],
                                 'despues': None if i not in nuevo.index or pd.isna(nuevo.at[i,c]) else float(nuevo.at[i,c])} for i in indices[:8]]
                    s['previa'] = dict(datos=nuevo, columna=c, accion=accion, cambios=cambios)
                    preparada=resumen(nuevo,s['variables'])
                    return jsonify(estado=estado(s), previa=dict(cambios=cambios, ejemplos=ejemplos,
                                   datos=preparada, dispersion=dispersion_registros(antes,c,nuevo),
                                   ventana=ventana_nulos(antes,c,nuevo)))
                elif operacion == 'aplicar':
                    p = s['previa']
                    if not p:
                        raise ValueError('Revisa primero una vista previa.')
                    s['anteriores'].append(s['datos'])
                    if len(s['anteriores']) > 10:
                        s['anteriores'].pop(0)
                    s['datos'] = p['datos']
                    s['historial'].append(dict(columna=p['columna'], accion=p['accion'], cambios=p['cambios'], apoyo=s['nivel'], variables=p.get('variables',[p['columna']]), parametros=p.get('parametros',{})))
                    s['previa'] = None
                    s['revision'] += 1
                elif operacion == 'deshacer':
                    if not s['anteriores']:
                        raise ValueError('No hay cambios para deshacer.')
                    s['datos'] = s['anteriores'].pop()
                    s['historial'].pop()
                    s['previa'] = None
                    s['revision'] += 1
                else:
                    raise ValueError('Operación no reconocida.')
                return jsonify(estado=estado(s))
            except (ValueError, TypeError) as e:
                return jsonify(error=str(e)), 400

    @app.get('/api/fase3/descargar')
    def descargar_datos():
        with lock:
            try:
                s = recuperar()
                archivo = io.BytesIO(s['datos'].to_csv(index=False).encode('utf-8-sig'))
                return send_file(archivo, mimetype='text/csv', as_attachment=True, download_name='datos_preparados.csv')
            except ValueError as e:
                return jsonify(error=str(e)), 400
