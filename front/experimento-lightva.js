const api = '/api/experimento-lightva';
const el = id => document.getElementById(id);
const value = id => el(id).value;
const labels = {conservar: 'Conservar nulos', excluir_nulos: 'Excluir filas',
  media: 'Imputar con la media', mediana: 'Imputar con la mediana'};
let sesion, estado, diagnostico, previa;
let ocupado = false;

function nodo(tag, texto) {
  const element = document.createElement(tag);
  if (texto !== undefined) element.textContent = texto;
  return element;
}

function tabla(destino, titulos, filas) {
  const table = nodo('table');
  const head = table.createTHead().insertRow();
  titulos.forEach(titulo => head.append(nodo('th', titulo)));
  const body = table.createTBody();
  filas.forEach(fila => {
    const row = body.insertRow();
    fila.forEach(celda => row.append(nodo('td', celda ?? '—')));
  });
  destino.replaceChildren(table);
}

async function peticion(datos) {
  const response = await fetch(api, datos ? {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({sesion, ...datos})
  } : undefined);
  const salida = await response.json();
  if (!response.ok) throw new Error(salida.error);
  return salida;
}

async function ejecutar(tarea, espera = 'Cargando…') {
  if (ocupado) return;
  ocupado = true;
  const controles = [...document.querySelectorAll('button, input, textarea, select')]
    .filter(control => !control.disabled);
  controles.forEach(control => { control.disabled = true; });
  el('estado').textContent = espera;
  try {
    await tarea();
    el('estado').textContent = '';
  } catch (error) {
    el('estado').textContent = error.message || 'No se pudo completar la solicitud.';
  } finally {
    controles.forEach(control => { control.disabled = false; });
    ocupado = false;
  }
}

function perfil(perfilActual) {
  diagnostico = perfilActual;
  const {filas, filas_con_nulos, periodo, columnas} = diagnostico;
  const cobertura = periodo.inicio ? `${periodo.inicio} a ${periodo.fin}` : 'Sin cobertura temporal';
  el('cobertura').textContent =
    `${filas} filas, ${filas_con_nulos} con nulos, ${periodo.filas_sin_fecha} sin fecha. ${cobertura}.`;
  tabla(el('perfil'), ['Variable', 'Tipo', 'Nulos', '%'],
    columnas.map(c => [c.nombre, c.tipo, c.nulos, c.porcentaje]));
  if (!el('columna').options.length) {
    columnas.forEach(c => el('columna').add(new Option(c.nombre, c.nombre)));
    if (columnas.some(c => c.nombre === 'PM2.5')) el('columna').value = 'PM2.5';
  }
  el('diagnostico').hidden = false;
  distribucion();
}

function distribucion() {
  const columna = diagnostico.columnas.find(c => c.nombre === value('columna'));
  if (!columna) return;
  const filas = columna.distribucion.map(g => [g.grupo, g.filas, g.nulos]);
  if (columna.nulos_sin_fecha && diagnostico.periodo.inicio) {
    filas.push(['Sin fecha', diagnostico.periodo.filas_sin_fecha, columna.nulos_sin_fecha]);
  }
  if (filas.length) tabla(el('distribucion'), ['Periodo o bloque de filas', 'Filas', 'Nulos'], filas);
  else el('distribucion').textContent = 'Esta variable no contiene nulos.';
}

function limpiarPrevia() {
  previa = null;
  el('previa').replaceChildren();
  el('aplicar').hidden = true;
}

function ventana(destino, filas) {
  tabla(destino, ['Fila original', 'Fecha', 'Antes', 'Después'],
    filas.map(f => [f.fila, f.fecha, f.antes, f.eliminado ? 'Fila excluida' : f.despues]));
}

function describir(evento) {
  if (evento.tipo === 'ayuda') return `${evento.id} · ${evento.columna} · ${evento.criterio} → nivel ${evento.nivel}. ${evento.contenido.mensaje}`;
  if (evento.tipo === 'hallazgo') return `${evento.id} · ${evento.columna} · Nivel ${evento.nivel}. Hallazgo: ${evento.respuesta}`;
  const verbo = evento.tipo === 'deshacer' ? 'Deshecho' : 'Confirmado';
  return `${evento.id} · ${evento.columna} · ${verbo}: ${labels[evento.tratamiento]} (${evento.cambios} cambios). Nivel ${evento.nivel}. Justificación: ${evento.respuesta}`;
}

function mostrar(nuevo) {
  estado = nuevo;
  perfil(nuevo.perfil);
  el('plan-panel').hidden = false;
  el('observacion').hidden = false;
  el('inspeccionar').hidden = false;
  el('ajustes').textContent = nuevo.plan.ajustes;
  el('deshacer').hidden = !nuevo.puede_deshacer;
  const actividades = nuevo.plan.actividades;
  el('plan').replaceChildren(...actividades.map(a => {
    const article = nodo('article');
    const avance = nuevo.avance[a.id];
    article.append(nodo('h3', a.titulo), nodo('p', a.proposito),
      nodo('p', `Evidencia esperada: ${a.evidencia}`), nodo('p', a.variables.join(', ')));
    if (avance) article.append(nodo('p', `Completada · ${describir(avance)}`));
    else {
      const button = nodo('button', a.id === nuevo.seleccion ? 'Actividad seleccionada' : 'Seleccionar actividad');
      button.disabled = a.id === nuevo.seleccion;
      button.onclick = () => ejecutar(async () => {
        const salida = await peticion({accion: 'seleccionar', id: a.id});
        el('respuesta').value = '';
        el('columna').value = a.variables[0];
        limpiarPrevia();
        mostrar(salida);
        await inspeccionar();
      });
      article.append(button);
    }
    return article;
  }));
  const actual = actividades.find(a => a.id === nuevo.seleccion);
  el('trabajo').hidden = !actual;
  if (actual) {
    const completa = Boolean(nuevo.avance[actual.id]);
    const tratamiento = actual.id === 'F2T1S2';
    el('actividad').textContent = actual.titulo;
    el('nivel').textContent = `Nivel ${nuevo.nivel} · ${nuevo.nombre_nivel}`;
    el('ayuda').hidden = completa || nuevo.nivel === 4;
    el('respuesta-panel').hidden = completa;
    el('hallazgo').hidden = tratamiento;
    el('tratamientos').hidden = !tratamiento;
    el('etiqueta-respuesta').textContent = tratamiento ? 'Justifica el tratamiento elegido' : 'Describe tu hallazgo';
  }
  el('apoyos').replaceChildren(...nuevo.apoyos.map(evento => {
    const bloque = nodo('article');
    bloque.append(nodo('h3', `Ayuda de nivel ${evento.nivel} · ${evento.columna}`),
      nodo('p', evento.contenido.mensaje));
    evento.contenido.alternativas.forEach(a =>
      bloque.append(nodo('p', `${labels[a.accion]} — ${a.explicacion}`)));
    return bloque;
  }));
  el('eventos').replaceChildren(...nuevo.eventos.map(e => nodo('li', describir(e))));
  nuevo.trazas.slice(el('trazas').childElementCount).forEach(traza => {
    const detalle = nodo('details');
    detalle.append(nodo('summary', `Consulta ${el('trazas').childElementCount + 1} · ${traza.tipo}`),
      nodo('pre', JSON.stringify(traza, null, 2)));
    el('trazas').append(detalle);
  });
}

function campos(accion) {
  return {accion, columna: value('columna'), respuesta: value('respuesta'),
    tratamiento: value('tratamiento')};
}

async function inspeccionar() {
  const {comparacion, ventana: filas} = await peticion(campos('inspeccionar'));
  const valores = Object.entries(comparacion);
  const anterior = value('tratamiento');
  el('tratamiento').replaceChildren(...valores.map(([k, v]) => new Option(v.tratamiento, k)));
  if (comparacion[anterior]) el('tratamiento').value = anterior;
  const resumen = nodo('div');
  const muestra = nodo('div');
  tabla(resumen, ['Tratamiento', 'Filas resultantes', 'Nulos resultantes', 'Cambios'],
    valores.map(([, v]) => [v.tratamiento, v.filas, v.nulos, v.cambios]));
  ventana(muestra, filas);
  el('inspeccion').replaceChildren(resumen, muestra);
}

el('inicio').onsubmit = event => {
  event.preventDefault();
  ejecutar(async () => {
    const nuevo = await peticion({accion: 'iniciar', pregunta: value('pregunta')});
    sesion = nuevo.sesion;
    el('pregunta').value = nuevo.pregunta;
    el('pregunta').readOnly = true;
    el('iniciar').hidden = true;
    mostrar(nuevo);
  }, 'LightVA está generando el plan…');
};
el('columna').onchange = () => {
  limpiarPrevia();
  distribucion();
  el('inspeccion').replaceChildren();
  el('tratamiento').replaceChildren();
  if (sesion) ejecutar(inspeccionar);
};
el('tratamiento').onchange = limpiarPrevia;
el('inspeccionar').onclick = () => ejecutar(inspeccionar);
el('ayuda').onclick = () => ejecutar(async () => mostrar(await peticion(campos('ayuda'))),
  'LightVA está preparando la ayuda…');
el('hallazgo').onclick = () => ejecutar(async () => mostrar(await peticion(campos('hallazgo'))));
el('previsualizar').onclick = () => ejecutar(async () => {
  const {previsualizacion} = await peticion(campos('previsualizar'));
  previa = previsualizacion.token;
  const muestra = nodo('div');
  ventana(muestra, previsualizacion.ventana);
  el('previa').replaceChildren(nodo('p', `${previsualizacion.cambios} cambios previstos. ${previsualizacion.filas} filas y ${previsualizacion.nulos} nulos en la variable después del tratamiento.`), muestra);
  el('aplicar').hidden = false;
});
el('aplicar').onclick = () => ejecutar(async () => {
  mostrar(await peticion({...campos('aplicar'), previa}));
  limpiarPrevia();
  el('inspeccion').replaceChildren();
  await inspeccionar();
});
el('deshacer').onclick = () => ejecutar(async () => {
  mostrar(await peticion({accion: 'deshacer'}));
  limpiarPrevia();
  el('inspeccion').replaceChildren();
  await inspeccionar();
});
el('actualizar').onclick = () => ejecutar(async () =>
  mostrar(await peticion({accion: 'actualizar'})), 'LightVA está actualizando las recomendaciones…');

ejecutar(async () => {
  const entrada = await peticion();
  el('archivo').textContent = `CSV de la aplicación · ${entrada.archivo}`;
  el('pregunta').value = entrada.pregunta;
  perfil(entrada.perfil);
  el('iniciar').disabled = false;
});
