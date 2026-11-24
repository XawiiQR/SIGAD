const FASES_SEGUIMIENTO = ['Problema', 'Plan', 'Datos', 'Análisis', 'Conclusión'];
const NIVELES_SEGUIMIENTO = ['Autónomo', 'Orientar', 'Dirigir', 'Prescribir'];

window.SigadSeguimiento = class {
  constructor(enlace) {
    if (!window.BroadcastChannel) return;
    const guardado = sessionStorage.getItem('sigad_canal_seguimiento');
    const canal = guardado || Array.from(crypto.getRandomValues(new Uint32Array(4)), n => n.toString(16).padStart(8, '0')).join('');
    sessionStorage.setItem('sigad_canal_seguimiento', canal);
    const inicio = Number(sessionStorage.getItem('sigad_inicio_seguimiento')) || Date.now();
    sessionStorage.setItem('sigad_inicio_seguimiento', String(inicio));
    this.datos = { inicio, fase: null, desde: inicio, fases: {}, eventos: [] };
    this.canal = new BroadcastChannel(`sigad-seguimiento-${canal}`);
    this.canal.onmessage = ({ data }) => {
      if (data?.tipo === 'solicitar') this.publicar();
    };
    window.addEventListener('pagehide', () => this.canal.postMessage({ tipo: 'desconexion' }));
    window.addEventListener('pageshow', () => this.publicar());
    enlace.href = `/front/seguimiento.html?canal=${encodeURIComponent(canal)}`;
    enlace.hidden = false;
  }
  publicar() {
    this.canal?.postMessage({ tipo: 'estado', datos: this.datos });
  }
  entrar(fase) {
    if (!this.datos || fase === this.datos.fase) return;
    this.datos.fase = fase;
    this.datos.desde = Date.now();
    this.evento(`Fase activa: ${FASES_SEGUIMIENTO[fase - 1]}`);
  }
  evento(texto) {
    if (!this.datos) return;
    this.datos.eventos = [...this.datos.eventos.slice(-11), { texto, instante: Date.now() }];
    this.publicar();
  }
  observar(fase, sesion, perfil) {
    if (!this.datos || this.datos.fase !== fase) return;
    if (perfil) {
      this.datos.dataset = {
        filas: perfil.filas,
        temporal: perfil.temporal,
        variables: perfil.variables.map(({ columna, nombre, faltantes }) => ({ columna, nombre, faltantes })),
      };
    }
    const pasos = sesion.plan_lightva?.subtareas ??
      sesion.plan?.contenido?.pasos?.map((paso, i) => ({
        id: String(i), proposito: paso.accion, estado: 'confirmada', dependencias: [],
      })) ?? (fase === 3 ? sesion.historial?.map((paso, i) => ({
        id: String(i), proposito: `${paso.columna} · ${paso.accion}`, estado: 'aplicado', dependencias: [],
      })) : undefined) ?? [];
    this.datos.fases[fase] = {
      completada: Boolean(sesion.completada),
      motor: sesion.motor,
      nivel: sesion.motor?.nivel ?? sesion.nivel,
      resultado: sesion.resultado,
      seleccion: sesion.contexto,
      variables: sesion.variables,
      tratamientos: sesion.historial?.length,
      subtareas: pasos.map(({ id, proposito, estado, dependencias, motivo_invalidacion }) =>
        ({ id, proposito, estado, dependencias, motivo_invalidacion })),
    };
    this.publicar();
  }
};

function iniciarVistaSeguimiento(vista) {
  const buscar = selector => vista.querySelector(selector);
  const mensaje = buscar('[data-conexion]');
  const id = new URLSearchParams(location.search).get('canal');
  if (!window.BroadcastChannel || !/^[0-9a-f]{32}$/.test(id || '')) {
    mensaje.textContent = 'Abre Seguimiento desde la pestaña donde estás usando SiGAD.';
    return;
  }
  const canal = new BroadcastChannel(`sigad-seguimiento-${id}`);
  const crear = (tag, texto) => {
    const nodo = document.createElement(tag);
    if (texto !== undefined) nodo.textContent = texto;
    return nodo;
  };
  const duracion = (inicio, hasta) => {
    const segundos = Math.max(0, Math.floor(((hasta ?? Date.now()) - inicio) / 1000));
    return [Math.floor(segundos / 3600), Math.floor(segundos / 60) % 60, segundos % 60]
      .map(n => String(n).padStart(2, '0')).join(':');
  };
  const porcentaje = new Intl.NumberFormat('es', { style: 'percent', maximumFractionDigits: 1 });
  const hora = new Intl.DateTimeFormat('es-CO', { timeStyle: 'medium', timeZone: 'America/Bogota' });
  const etiqueta = texto => texto.replaceAll('_', ' ').replace(/^./, letra => letra.toUpperCase());
  let datos, faseAnterior, desconectadoEn;
  function fila(lista, nombre, valor) {
    lista.append(crear('dt', nombre), crear('dd', valor));
  }
  function actualizarTiempo() {
    if (!datos) return;
    buscar('[data-tiempo-total]').textContent = duracion(datos.inicio, desconectadoEn);
    buscar('[data-tiempo-fase]').textContent = duracion(datos.desde, desconectadoEn);
  }
  function render() {
    const fase = datos.fase;
    const actual = datos.fases[fase] || {};
    const motor = actual.motor;
    const arbol = buscar('[data-ruta]');
    const anteriores = new Map(Array.from(arbol.querySelectorAll('details'), detalle => [detalle.dataset.fase, detalle.open]));
    arbol.replaceChildren();
    FASES_SEGUIMIENTO.forEach((nombre, indice) => {
      const numero = indice + 1, estado = datos.fases[numero];
      const detalle = crear('details');
      detalle.dataset.fase = String(numero);
      detalle.open = (numero === fase && fase !== faseAnterior) || (anteriores.get(String(numero)) ?? (numero === fase));
      const estadoTexto = numero === fase ? (estado?.completada ? 'Activa · completada' : 'Activa') :
        estado?.completada ? 'Completada' : estado ? 'Visitada' : 'Pendiente';
      const encabezado = crear('summary', nombre);
      encabezado.append(crear('small', estadoTexto));
      if (numero === fase) encabezado.setAttribute('aria-current', 'step');
      detalle.append(encabezado);
      if (estado?.subtareas.length) {
        const pasos = crear('ol');
        const nombres = new Map(estado.subtareas.map(p => [p.id, p.proposito]));
        estado.subtareas.forEach(paso => {
          const item = crear('li');
          const avance = paso.motivo_invalidacion ? 'Invalidada' : etiqueta(paso.estado);
          item.append(crear('strong', paso.proposito), crear('small', avance));
          if (paso.dependencias.length) item.append(crear('p', `Depende de: ${paso.dependencias.map(id => nombres.get(id) || id).join(', ')}`));
          pasos.append(item);
        });
        detalle.append(pasos);
      } else {
        detalle.append(crear('p', estado?.tratamientos != null ? `${estado.tratamientos} tratamientos registrados.` :
          estado ? 'Todavía no hay un plan de subtareas en esta fase.' : 'Todavía no se ha registrado actividad.'));
      }
      const nodo = crear('li');
      nodo.append(detalle);
      arbol.append(nodo);
    });
    faseAnterior = fase;

    const sesion = buscar('[data-sesion]');
    sesion.replaceChildren();
    fila(sesion, 'Fase', FASES_SEGUIMIENTO[fase - 1] || 'Preparando sesión');
    fila(sesion, 'Nivel de ayuda', NIVELES_SEGUIMIENTO[actual.nivel - 1] || 'Por definir');
    if (actual.completada) {
      const siguiente = NIVELES_SEGUIMIENTO[(motor?.siguiente_nivel ?? 0) - 1];
      if (siguiente) fila(sesion, 'Apoyo en la próxima tarea', siguiente);
    }
    fila(sesion, 'Tiempo transcurrido', '');
    sesion.lastElementChild.dataset.tiempoTotal = '';
    fila(sesion, 'Tiempo en esta fase', '');
    sesion.lastElementChild.dataset.tiempoFase = '';
    actualizarTiempo();
    if (actual.seleccion?.vista) fila(sesion, 'Vista', etiqueta(actual.seleccion.vista));
    const variables = actual.seleccion?.variables ?? actual.variables ?? [actual.seleccion?.variable, actual.seleccion?.secundaria].filter(Boolean);
    if (Array.isArray(variables) && variables.length) fila(sesion, 'Variables', variables.join(', '));

    const dominio = buscar('[data-dominio]');
    dominio.replaceChildren();
    if (motor?.habilidades) {
      Object.entries(motor.habilidades).forEach(([habilidad, dato]) => {
        const fila = crear('div');
        const barra = crear('progress');
        barra.max = 1;
        barra.value = dato.probabilidad;
        barra.setAttribute('aria-label', etiqueta(habilidad));
        fila.append(crear('span', etiqueta(habilidad)), barra,
          crear('strong', porcentaje.format(dato.probabilidad)),
          crear('small', `${dato.tareas_correctas} tareas correctas`));
        dominio.append(fila);
      });
      dominio.append(crear('p', `Umbral del motor: ${porcentaje.format(motor.umbral)} · mínimo ${motor.evidencia_minima} tareas distintas.`));
    } else {
      dominio.append(crear('p', 'Esta fase todavía no reporta estimaciones BKT.'));
    }
    const evaluacion = buscar('[data-evaluacion]');
    evaluacion.replaceChildren();
    const resultado = actual.resultado;
    if (resultado?.feedback) evaluacion.append(crear('p', resultado.feedback));
    if (resultado?.criterios) {
      const criterios = crear('dl');
      Object.entries(resultado.criterios).forEach(([nombre, criterio]) =>
        fila(criterios, etiqueta(nombre), `${criterio.puntuacion}/2 · ${criterio.explicacion}`));
      evaluacion.append(criterios);
    } else if (!resultado?.feedback) {
      evaluacion.append(crear('p', 'Aún no hay una evaluación registrada en esta fase.'));
    }

    const dataset = buscar('[data-dataset]');
    const abierto = dataset.querySelector('details')?.open || false;
    dataset.replaceChildren();
    if (datos.dataset) {
      const p = datos.dataset;
      const resumen = crear('dl');
      fila(resumen, 'Filas', p.filas.toLocaleString('es-CO'));
      if (p.temporal?.inicio && p.temporal?.fin) fila(resumen, 'Cobertura', `${p.temporal.inicio.slice(0, 10)} a ${p.temporal.fin.slice(0, 10)}`);
      const columnas = crear('details');
      columnas.open = abierto;
      columnas.append(crear('summary', `Ver ${p.variables.length} columnas y sus faltantes`));
      const lista = crear('dl');
      p.variables.forEach(v => fila(lista, v.columna, `${v.nombre} · ${v.faltantes} faltantes`));
      columnas.append(lista);
      dataset.append(resumen, columnas);
    } else dataset.append(crear('p', 'Los metadatos estarán disponibles al cargar el dataset.'));
    const actividad = buscar('[data-actividad]');
    actividad.replaceChildren(...[...datos.eventos].reverse().map(({ texto, instante }) =>
      crear('li', `${hora.format(instante)} · ${texto}`)));
  }
  canal.onmessage = ({ data }) => {
    if (data?.tipo === 'estado') {
      datos = data.datos;
      desconectadoEn = undefined;
      mensaje.textContent = 'Conectado a la actividad de SiGAD';
      render();
    } else if (data?.tipo === 'desconexion') {
      desconectadoEn = Date.now();
      mensaje.textContent = 'Actividad desconectada. Se muestra el último estado recibido.';
    }
  };
  canal.postMessage({ tipo: 'solicitar' });
  setInterval(actualizarTiempo, 1000);
}

const vistaSeguimiento = document.querySelector('[data-seguimiento]');
if (vistaSeguimiento) iniciarVistaSeguimiento(vistaSeguimiento);
