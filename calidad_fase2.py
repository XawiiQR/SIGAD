"""Resúmenes visuales de calidad calculados localmente, sin modificar datos."""
import numpy as np
import pandas as pd


def referencias(serie):
    validos = pd.Series(serie, dtype='float64').dropna()
    if validos.empty:
        return None
    q1, q3 = validos.quantile([.25, .75])
    return {'media': float(validos.mean()), 'q1': float(q1), 'q3': float(q3),
            'inferior': float(q1 - 1.5 * (q3 - q1)),
            'superior': float(q3 + 1.5 * (q3 - q1)), 'n': len(validos)}


def resumen_calidad(explorador, variable):
    if variable not in explorador.df.columns:
        raise ValueError('Variable inexistente.')
    df = explorador.df
    numerica = variable in explorador.numericas
    valores = explorador.numerica(variable) if numerica else df[variable]
    faltantes = valores.isna()
    limites = None
    atipicos = pd.Series(False, index=df.index)
    if numerica and valores.notna().any():
        q1, q3 = valores.dropna().quantile([.25, .75])
        limites = {'inferior': float(q1 - 1.5 * (q3 - q1)), 'superior': float(q3 + 1.5 * (q3 - q1))}
        atipicos = valores.lt(limites['inferior']) | valores.gt(limites['superior'])
    fechas = explorador.fechas
    datos = pd.DataFrame({'fecha': fechas.to_numpy(), 'falta': faltantes.to_numpy(),
                          'valor': valores.to_numpy() if numerica else np.full(len(df), np.nan)})
    bandas = []
    temporal = fechas.notna().any()
    sin_fecha = int(fechas.isna().sum()) if temporal else 0
    if temporal:
        fechas_validas = datos.dropna(subset=['fecha']).set_index('fecha')
        span = (fechas_validas.index.max().year - fechas_validas.index.min().year) * 12 + 1
        frecuencia = 'MS' if span <= 60 else 'YS'
        for inicio, g in fechas_validas.resample(frecuencia):
            bandas.append({'etiqueta': inicio.strftime('%Y-%m' if frecuencia == 'MS' else '%Y'),
                          'total': len(g), 'faltantes': int(g.falta.sum()),
                          'media': float(g.valor.mean()) if g.valor.notna().any() else None})
    elif len(df):
        for indices in np.array_split(np.arange(len(df)), min(40, len(df))):
            if not len(indices):
                continue
            g = datos.iloc[indices]
            bandas.append({'etiqueta': f'Registros {indices[0]+1}–{indices[-1]+1}', 'total': len(g),
                          'faltantes': int(g.falta.sum()),
                          'media': float(g.valor.mean()) if g.valor.notna().any() else None})
    puntos = []
    if numerica:
        for mascara in (atipicos, valores.notna() & ~atipicos):
            indices = np.flatnonzero(mascara.to_numpy())
            indices = indices[np.linspace(0, len(indices)-1, min(60, len(indices)), dtype=int)] if len(indices) else []
            for i in indices:
                puntos.append({'fila': int(i), 'valor': float(valores.iloc[i]),
                               'atipico': bool(atipicos.iloc[i]),
                               'fecha': fechas.iloc[i].isoformat() if pd.notna(fechas.iloc[i]) else None})
    ref_periodos = referencias([b['media'] for b in bandas]) if numerica else None
    for banda in bandas:
        banda['atipico_media'] = bool(ref_periodos and banda['media'] is not None and
                                     (banda['media'] < ref_periodos['inferior'] or
                                      banda['media'] > ref_periodos['superior']))
    return {'variable': variable, 'numerica': numerica, 'total': len(df),
            'faltantes': int(faltantes.sum()), 'disponibles': int((~faltantes).sum()),
            'atipicos': int(atipicos.sum()), 'limites': limites, 'bandas': bandas,
            'temporal': bool(temporal), 'sin_fecha': sin_fecha, 'puntos': puntos,
            'referencias_registros': referencias(valores) if numerica else None,
            'referencias_periodos': ref_periodos,
            'periodos_atipicos': sum(b['atipico_media'] for b in bandas),
            'nota': 'La línea representa medias por periodo del archivo; no es una interpolación. Los periodos sin registros se distinguen de las celdas vacías.',
            'nota_puntos': 'Hasta 60 candidatos y 60 valores habituales, espaciados por filas. El criterio IQR identifica candidatos, no demuestra errores.'}


def detalle_calidad(explorador, variable, fila):
    if variable not in explorador.numericas or not 0 <= fila < len(explorador.df):
        raise ValueError('Observación no válida.')
    df = explorador.df
    indices = np.arange(len(df))
    if 'station' in df.columns and pd.notna(df['station'].iloc[fila]):
        indices = indices[df['station'].eq(df['station'].iloc[fila]).to_numpy()]
    posicion = int(np.flatnonzero(indices == fila)[0])
    vecinos = indices[max(0, posicion-2):posicion+3]
    valores = explorador.numerica(variable)
    return {'fila': fila, 'variable': variable, 'nota': 'Registros vecinos en el orden del archivo; se conserva la misma estación cuando existe.',
            'registros': [{'fila': int(i), 'valor': float(valores.iloc[i]) if pd.notna(valores.iloc[i]) else None,
                           'fecha': explorador.fechas.iloc[i].isoformat() if pd.notna(explorador.fechas.iloc[i]) else None,
                           'estacion': str(df['station'].iloc[i]) if 'station' in df.columns else None}
                          for i in vecinos]}
