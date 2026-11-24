/* Fase Problema: selección visual; el backend controla niveles, BKT y cierre. */
window.SigadPhase1 = class {
  constructor(host, api, callbacks) {
    this.host = host; this.api = api; this.callbacks = callbacks;
    this.variable = ''; this.vista = ''; this.secundaria = null;
    this.busy = false; this.chartRequest = 0; this.viewSelections = {}; this.chartPage = 0;
    this.seconds = 30; this.clock = null;
  }
  $(selector) { return this.host.querySelector(selector); }
  async request(path, body) {
    return this.api(`/api/fase1/${path}`, {
      ...(body ? { method: 'POST', body: JSON.stringify(body) } : {}),
      headers: { 'Content-Type': 'application/json', ...(this.token ? { 'X-SiGAD-Session': this.token } : {}) },
    });
  }
  async mount() {
    this.perfil = await this.request('perfil');
    if (!this.host.isConnected) return;
    const numericas = this.perfil.variables.filter(v => Object.values(v.vistas).some(x => x.disponible));
    if (!numericas.length) throw new Error('El dataset no tiene variables suficientes para las vistas de esta fase.');
    this.variable = numericas.find(v => v.columna === 'PM2.5')?.columna || numericas[0].columna;
    const variable = this.perfil.variables.find(v => v.columna === this.variable);
    this.vista = variable.vistas.evolucion?.disponible ? 'evolucion' : Object.keys(variable.vistas).find(k => variable.vistas[k].disponible);
    this.secundaria = variable.vistas[this.vista]?.pares?.[0] || null;
    this.token = sessionStorage.getItem('sigad_fase1_sesion');
    if (this.token) {
      try {
        this.session = await this.request('estado');
        this.variable = this.session.contexto.variable;
        this.vista = this.session.contexto.vista;
        this.secundaria = this.session.contexto.secundaria;
      } catch (error) {
        // Solo crear otra sesión si la anterior dejó de existir.
        if (error.status !== 404) throw error;
        this.token = null;
      }
    }
    if (!this.token) {
      const result = await this.request('sesion', this.context());
      this.token = result.sesion; this.session = result;
      sessionStorage.setItem('sigad_fase1_sesion', this.token);
    }
    this.host.classList.add('phase1-host');
    this.host.innerHTML = `
      <header class="f1-header">
        <h2>SiGAD</h2>
        <nav class="f1-phase-strip" aria-label="Fases del ciclo PPDAC">
          <span aria-current="step">Problema</span><span>Plan</span><span>Datos</span><span>Análisis</span><span>Conclusión</span>
        </nav>
      </header>
      <div class="f1-layout f1-problem-layout"><aside class="f1-panel f1-variables" aria-labelledby="f1-variables-title"><h3 id="f1-variables-title">Variables</h3>
        <p class="f1-note" data-dataset-summary></p>
        <section class="f1-context" aria-live="polite"><span>Qué mide</span><h4 data-name></h4><p data-description></p></section>
        <div data-vars></div>
        <details><summary>Disponibilidad y cobertura</summary><div data-quality></div></details></aside>
      <section class="f1-panel f1-exploration" aria-labelledby="f1-exploration-title">
        <h3 id="f1-exploration-title">Gráfico</h3>
        <div class="f1-views" data-views></div>
        <label class="f1-second" hidden>Segunda variable <select data-second></select></label>
        <h4 data-chart-title></h4><div class="f1-series-legend" data-series-legend></div><div class="f1-chart-wrap"><div class="f1-chart-panels" data-chart-panels hidden></div><svg data-chart role="img"></svg><div class="f1-tooltip" role="tooltip" hidden></div></div><p class="f1-note" data-chart-note></p>
      </section>
      <section class="f1-panel f1-question" aria-labelledby="f1-question-title">
        <h3 id="f1-question-title">Pregunta de investigación</h3>
        <form class="f1-form"><textarea name="pregunta" aria-labelledby="f1-question-title" aria-describedby="f1-question-hint" required maxlength="4000" placeholder="Escribe tu pregunta aquí"></textarea>
          <p id="f1-question-hint" class="f1-question-hint">Incluye qué quieres conocer, las variables y el periodo o grupo.</p>
          <div class="f1-actions"><button type="submit">Evaluar mi pregunta</button><button type="button" data-help-button>Necesito ayuda</button><button type="button" data-skip-button>Saltar a Prescribir</button></div>
        </form>
        <p data-error role="alert"></p>
        <div class="f1-question-results">
          <div data-feedback aria-live="polite"></div>
          <div class="f1-actions" data-complete hidden><button type="button" data-continue>Continuar a la fase 2</button><button type="button" data-new>Practicar otra pregunta</button><button type="button" data-verify>Comprobar comprensión sin ayuda</button></div>
          <section class="f1-help" hidden aria-live="polite"><h4 data-help-title></h4><p data-help></p><p data-example></p></section>
          <section class="f1-advanced" data-advanced hidden aria-live="polite"></section>
          <details class="f1-model"><summary>Seguimiento de aprendizaje · BKT</summary><p class="f1-note">Estimación del prototipo, con parámetros todavía no calibrados. La ayuda prescrita no aporta aciertos al modelo.</p><div data-model></div></details>
        </div>
      </section></div>`;
    this.renderVariables(); this.renderQuality(); this.renderSession();
    this.$('.f1-form').addEventListener('submit', e => { e.preventDefault(); this.evaluate(); });
    this.host.addEventListener('input', e => {
      if (this.session.lightva && e.target.matches('textarea') && !this.busy) this.startClock();
    });
    this.$('[data-help-button]').addEventListener('click', () => this.action('ayuda'));
    this.$('[data-skip-button]').addEventListener('click', () => this.action('prescribir'));
    this.$('[data-new]').addEventListener('click', async () => {
      if (await this.action('nueva')) { this.$('.f1-form').reset(); this.$('[data-feedback]').replaceChildren(); }
    });
    this.$('[data-verify]').addEventListener('click', async () => {
      if (await this.action('nueva', { verificacion: true })) {
        this.$('.f1-form').reset(); this.$('[data-feedback]').replaceChildren();
      }
    });
    this.$('[data-continue]').addEventListener('click', () => {
      if (this.session.completada) this.callbacks.onFinish(this.session.objetivo);
    });
    this.$('[data-second]').addEventListener('change', e => this.select(this.variable, this.vista, e.target.value));
    this.resize = new ResizeObserver(() => { if (this.chart) this.drawChart(); });
    this.resize.observe(this.$('[data-chart]'));
    await this.loadChart();
    this.startClock();
    if (!this.session.lightva || this.session.motor.nivel === 2) await this.ensureAdvanced();
  }
  stopClock() { clearInterval(this.clock); this.clock = null; }
  startClock() {
    this.stopClock();
    if (this.session.completada || this.session.motor.nivel >= 4) return;
    if (this.session.lightva && !this.session.resultado) return;
    this.seconds = 30;
    this.clock = setInterval(async () => {
      this.seconds -= 1;
      if (this.seconds <= 0) {
        this.stopClock();
        await this.action('timeout');
      }
    }, 1000);
  }
  selectedVariables() {
    const c = this.session?.contexto;
    if (c?.variables) return c.variables;
    if (this.vista === 'relaciones') return [this.variable,this.secundaria].filter(Boolean);
    if (this.vista === 'comparacion') return this.secundaria ? [this.secundaria] : [];
    return [this.variable];
  }
  temporalVariables() { return this.selectedVariables(); }
  context() { return { variable: this.variable, vista: this.vista, secundaria: this.secundaria }; }
  compatible(col, vista, categoria=this.variable) {
    const v=this.perfil.variables.find(v=>v.columna === col);
    if (!v) return false;
    if (vista === 'comparacion') return (this.perfil.variables.find(v=>v.columna === categoria)?.vistas.comparacion?.pares || []).includes(col);
    if (vista === 'relaciones') return v.numerica && v.vistas.relaciones?.disponible;
    return Boolean(v.vistas[vista]?.disponible);
  }
  async switchView(vista) {
    this.viewSelections[this.vista] = structuredClone(this.session.contexto);
    const stored=this.viewSelections[vista];
    const available=this.perfil.variables.filter(v=>v.vistas[vista]?.disponible);
    if (!available.length) return;
    let variable=stored?.variable || (available.some(v=>v.columna === this.variable) ? this.variable : available[0].columna);
    let columns=(stored?.variables || this.selectedVariables()).filter(c=>this.compatible(c,vista,variable));
    if (!columns.length && !stored) columns=vista === 'comparacion' ? [available.find(v=>v.columna === variable).vistas.comparacion.pares[0]] : [variable];
    if (vista === 'relaciones' && columns.length === 1 && !stored) {
      const other=this.perfil.variables.find(v=>v.columna !== columns[0] && this.compatible(v.columna,vista));
      if(other) columns.push(other.columna);
    }
    await this.select(vista === 'comparacion' ? variable : columns[0] || variable,vista,null,columns);
  }
  async toggleVariable(col) {
    if (this.busy) return;
    const v=this.perfil.variables.find(v=>v.columna === col);
    if (this.vista === 'comparacion' && v.rol === 'categoria') {
      const columns=this.selectedVariables().filter(c=>this.compatible(c,'comparacion',col));
      await this.select(col,'comparacion',null,columns); this.describe(v); return;
    }
    if (!this.compatible(col,this.vista)) { this.describe(v); return; }
    const columns=[...this.selectedVariables()], i=columns.indexOf(col);
    if(i>=0) columns.splice(i,1); else columns.push(col);
    await this.select(this.vista === 'comparacion' ? this.variable : columns[0] || this.variable,this.vista,null,columns);
    this.describe(v);
  }
  textNode(tag, text, className) {
    const node = document.createElement(tag); node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  renderVariables() {
    const host = this.$('[data-vars]'); host.replaceChildren();
    const grupos = [...new Set(this.perfil.variables.map(v => v.grupo))];
    const descripciones = {
      Contaminación: 'Gases y partículas que afectan la calidad del aire.',
      Meteorología: 'Condiciones del tiempo, como la lluvia y el viento.'
    };
    const tiempo = grupos.indexOf('Tiempo e identificadores');
    if (tiempo !== -1) grupos.push(grupos.splice(tiempo, 1)[0]);
    grupos.forEach(grupo => {
      const section = document.createElement('section'); section.className = 'f1-var-group';
      section.append(this.textNode('h4', grupo));
      if (Object.hasOwn(descripciones, grupo)) section.append(this.textNode('p', descripciones[grupo], 'f1-note'));
      const wrap = document.createElement('div'); wrap.className = 'f1-var-list';
      this.perfil.variables.filter(v => v.grupo === grupo).forEach(v => {
        const b = this.textNode('button', v.columna); b.type = 'button'; b.dataset.variable = v.columna;
        b.setAttribute('aria-pressed', String(this.selectedVariables().includes(v.columna) || (this.vista === 'comparacion' && v.columna === this.variable)));
        b.title = `${v.nombre}. ${v.descripcion}`;
        b.addEventListener('focus', () => this.describe(v));
        b.addEventListener('click', () => {
          this.describe(v);
          if (!this.session.completada) this.toggleVariable(v.columna);
        }); wrap.append(b);
      }); section.append(wrap); host.append(section);
    });
    this.describe(this.perfil.variables.find(v => v.columna === this.variable));
  }
  describe(v) {
    this.$('[data-name]').textContent = `${v.columna} · ${v.nombre}`;
    this.$('[data-description]').textContent = v.descripcion;
  }
  renderQuality() {
    const p = this.perfil, host = this.$('[data-quality]'); host.replaceChildren();
    host.append(this.textNode('p', `${p.filas.toLocaleString('es-PE')} registros`));
    if (p.espacial) host.append(this.textNode('p', p.espacial.nota));
    const temporal = p.temporal;
    const inicio = temporal.inicio?.slice(0, 4), fin = temporal.fin?.slice(0, 4);
    const periodo = inicio && fin ? (inicio === fin ? inicio : `${inicio}–${fin}`) : '';
    const tipo = p.variables.some(v => v.grupo === 'Contaminación') ? 'Registros de calidad del aire' : 'Registros del dataset';
    this.$('[data-dataset-summary]').textContent = periodo ? `${tipo} · ${periodo}` : tipo;
    host.append(this.textNode('p', temporal.inicio ? `${temporal.inicio.slice(0, 10)} → ${temporal.fin.slice(0, 10)}` : 'Sin fechas válidas.'));
    host.append(this.textNode('p', `Fechas inválidas: ${temporal.fechas_invalidas}; fechas repetidas: ${temporal.fechas_duplicadas}.`));
    host.append(this.textNode('p', `Intervalo más frecuente: ${temporal.intervalo_segundos == null ? 'no disponible' : temporal.intervalo_segundos / 3600 + ' horas'}. Intervalos diferentes: ${temporal.intervalos_irregulares}.`));
    p.variables.filter(v => v.numerica).forEach(v => {
      const row = document.createElement('div'); row.className = 'f1-missing';
      row.append(this.textNode('span', `${v.columna}: ${v.faltantes_porcentaje}% faltante`));
      const track = document.createElement('div'); track.className = 'f1-track';
      const fill = document.createElement('div'); fill.style.width = `${v.faltantes_porcentaje}%`;
      track.append(fill); row.append(track); host.append(row);
    });
  }
  renderSession() {
    if (!this.host.isConnected) return;
    const s = this.session, v = this.perfil.variables.find(v => v.columna === this.variable);
    const names = { evolucion: 'Evolución temporal', ciclicidad: 'Patrones cíclicos', distribucion: 'Distribución', variabilidad: 'Variabilidad', relaciones: 'Relaciones', frecuencias: 'Frecuencias', comparacion: 'Comparar categorías' };
    const views = this.$('[data-views]'); views.replaceChildren();
    Object.entries(names).forEach(([key, name]) => {
      const b = this.textNode('button', name); b.type = 'button'; b.dataset.view = key;
      b.disabled = !this.perfil.variables.some(col=>col.vistas[key]?.disponible) || s.completada;
      b.title = v.vistas[key]?.motivo || 'Selecciona una variable compatible.';
      b.setAttribute('aria-pressed', String(key === this.vista));
      b.addEventListener('click', () => this.switchView(key)); views.append(b);
    });
    this.$('.f1-second').hidden = true;
    const select = this.$('[data-second]'); select.replaceChildren();
    (v.vistas[this.vista]?.pares || []).forEach(c => { const o = this.textNode('option', c); o.value = c; select.append(o); });
    select.value = this.secundaria || '';
    this.host.querySelectorAll('[data-variable]').forEach(b => b.setAttribute('aria-pressed', String(this.selectedVariables().includes(b.dataset.variable) || (this.vista === 'comparacion' && b.dataset.variable === this.variable))));
    this.$('.f1-help').hidden = s.lightva || s.motor.nivel === 1 || s.motor.nivel >= 3 || s.completada;
    this.$('[data-help-title]').textContent = `Nivel ${s.motor.nivel} · ${s.motor.nombre_nivel}`;
    this.$('[data-help]').textContent = s.guidance.mensaje;
    this.$('[data-example]').textContent = s.guidance.ejemplo ? `Ejemplo: ${s.guidance.ejemplo}` : '';
    this.$('[data-skip-button]').hidden = s.completada || s.motor.nivel === 4 || (s.lightva && !s.resultado);
    this.$('[data-complete]').hidden = !s.completada;
    this.$('.f1-form button[type=submit]').disabled = s.completada || (!this.selectedVariables().length || (this.vista === 'relaciones' && this.selectedVariables().length < 2));
    this.$('.f1-form').hidden = s.completada || (!s.lightva && s.motor.nivel >= 3);
    const helpButton = this.$('[data-help-button]');
    helpButton.hidden = s.lightva && (!s.resultado || (s.motor.nivel > 1 && (!s.plan_lightva || s.motor.nivel >= 4)));
    helpButton.textContent = s.lightva && s.motor.nivel > 1 ? 'Más ayuda' : 'Necesito ayuda';
    this.$('[data-skip-button]').textContent = s.lightva ? 'Ver una pregunta de ejemplo' : 'Saltar a Prescribir';
    if (s.lightva) this.renderLightVA(); else this.renderAdvanced();
    this.$('[data-model]').replaceChildren();
    Object.entries(s.motor.habilidades).forEach(([k, e]) => {
      this.$('[data-model]').append(this.textNode('p', `${k}: P(dominio) ${e.probabilidad.toFixed(3)} · ${e.tareas_correctas} tareas correctas no prescritas`));
    });
    this.$('[data-model]').append(this.textNode('p', `Retiro de apoyo: umbral ${s.motor.umbral}; mínimo ${s.motor.evidencia_minima} tareas distintas. Próxima tarea: nivel ${s.motor.siguiente_nivel}.`));
    if (s.resultado) this.renderFeedback(s.resultado);
    this.callbacks.onState(s);
  }
  renderLightVA() {
    const host = this.$('[data-advanced]'), s = this.session;
    host.replaceChildren();
    host.hidden = s.motor.nivel < 2 || s.completada || !s.resultado;
    if (host.hidden) return;
    host.append(this.textNode('h4', 'Ayuda para formular tu pregunta'));
    const plan = s.plan_lightva;
    if (!plan) {
      const fallo = this.revisionAyudaFallida === s.revision;
      if (fallo) host.append(this.textNode('p', 'No se pudieron cargar más sugerencias. Puedes editar tu pregunta con la retroalimentación de arriba.'));
      const retry = this.textNode('button', fallo ? 'Reintentar ayuda' :
        s.motor.nivel === 2 ? 'Actualizar sugerencias' : 'Ver sugerencias');
      retry.type = 'button';
      retry.dataset.requestHelp = '';
      retry.addEventListener('click', () => this.ensureAdvanced());
      host.append(retry);
      return;
    }
    host.append(this.textNode('p', plan.intervencion));
    const steps = new Map(plan.subtareas.map(step => [step.id, step]));
    const list = document.createElement('ol');
    plan.subtareas.forEach(step => {
      const item = document.createElement('li');
      item.append(this.textNode('strong', step.proposito));
      if (step.motivo_invalidacion) {
        item.append(this.textNode('p', `Invalidada: ${step.motivo_invalidacion}`));
      } else if (step.estado === 'completada') {
        item.append(this.textNode('p', `Completada: ${step.respuesta}`));
      } else {
        item.append(this.textNode('p', step.intervencion), this.textNode('small', `Evidencia esperada: ${step.evidencia}`));
        const faltantes = step.dependencias.filter(id => steps.get(id)?.estado !== 'completada');
        if (faltantes.length) {
          item.append(this.textNode('p', `Primero completa: ${faltantes.map(id => steps.get(id)?.proposito).join(', ')}`));
        } else {
          const label = this.textNode('label', 'Tu respuesta a este paso');
          const input = document.createElement('textarea');
          input.maxLength = 4000;
          label.append(input);
          const save = this.textNode('button', 'Guardar avance');
          save.type = 'button';
          save.addEventListener('click', () => this.action('completar_subtarea', { subtarea: step.id, respuesta: input.value }));
          item.append(label, save);
        }
      }
      list.append(item);
    });
    if (list.childElementCount) host.append(list);
    const ayudas = plan.propuesta ? [plan.propuesta] : plan.alternativas;
    if (ayudas.length) host.append(this.textNode('h5', plan.propuesta ? 'Propuesta para revisar' : 'Alternativas para comparar'));
    for (const ayuda of ayudas) {
      const card = document.createElement('article');
      card.className = 'f1-option';
      card.append(this.textNode('p', ayuda.texto), this.textNode('p', ayuda.explicacion));
      if (ayuda.periodo) card.append(this.textNode('small', `${ayuda.periodo.inicio.slice(0, 10)} a ${ayuda.periodo.fin.slice(0, 10)}`));
      host.append(card);
    }
    plan.aclaraciones.forEach(texto => host.append(this.textNode('p', texto)));
  }
  renderAdvanced() {
    const host = this.$('[data-advanced]'), s = this.session;
    host.replaceChildren();
    host.hidden = s.motor.nivel < 3;
    if (host.hidden) return;
    const advanced = s.avanzado;
    if (!advanced) {
      host.append(this.textNode('h4', s.motor.nivel === 3 ? 'Preparando cuatro preguntas posibles…' : 'Eligiendo una pregunta viable…'));
      host.append(this.textNode('p', 'Las recomendaciones se basan en la variable, el gráfico y la cobertura disponible.'));
      return;
    }
    if (advanced.modo === 'prescribir') {
      host.append(this.textNode('span', 'Nivel 4 · Prescribir', 'f1-advanced-label'));
      host.append(this.textNode('h4', 'Analizaremos esta pregunta'));
      host.append(this.textNode('p', advanced.opcion.pregunta, 'f1-prescribed-question'));
      host.append(this.textNode('p', advanced.explicacion));
      host.append(this.textNode('small', `Variables: ${advanced.opcion.variables.join(', ')}`));
      return;
    }
    host.append(this.textNode('span', 'Nivel 3 · Dirigir', 'f1-advanced-label'));
    host.append(this.textNode('h4', advanced.seleccion == null ? 'Escoge una pregunta para continuar' : 'Pregunta seleccionada'));
    if (advanced.seleccion != null) {
      const selected = advanced.opciones[advanced.seleccion];
      host.append(this.textNode('p', selected.pregunta, 'f1-prescribed-question'));
      return;
    }
    const grid = document.createElement('div'); grid.className = 'f1-option-grid';
    advanced.opciones.forEach((option, index) => {
      const card = document.createElement('article'); card.className = 'f1-option';
      card.append(this.textNode('h5', option.titulo));
      card.append(this.textNode('p', option.pregunta));
      card.append(this.textNode('small', option.motivo));
      const button = this.textNode('button', 'Elegir esta pregunta'); button.type = 'button';
      button.addEventListener('click', () => this.selectOption(index));
      card.append(button); grid.append(card);
    });
    host.append(grid);
  }
  async ensureAdvanced() {
    if (this.busy || this.session.completada || this.session.motor.nivel < 2) return;
    if (this.session.lightva) {
      if (!this.session.resultado || this.session.plan_lightva) return;
      this.stopClock(); this.setBusy(true); this.$('[data-error]').textContent = '';
      const requestButton = this.$('[data-request-help]');
      if (requestButton) {
        const status = this.textNode('p', 'Preparando ayuda…');
        status.setAttribute('role', 'status');
        requestButton.replaceWith(status);
      }
      try {
        this.session = await this.request('apoyo', { revision: this.session.revision });
        this.revisionAyudaFallida = null;
        this.callbacks.onHistory(`Fase 1: plan de LightVA · ${this.session.motor.nombre_nivel}`);
      } catch (e) {
        if (e.status === 409) await this.handleError(e);
        else this.revisionAyudaFallida = this.session.revision;
      }
      finally {
        if (this.host.isConnected) { this.setBusy(false); this.renderSession(); this.startClock(); }
      }
      return;
    }
    if (this.session.motor.nivel === 2) {
      this.stopClock(); this.setBusy(true);
      try {
        this.session = await this.request('apoyo', { revision: this.session.revision });
      } catch (e) { await this.handleError(e); }
      finally {
        if (this.host.isConnected) { this.setBusy(false); this.renderSession(); }
        this.startClock();
      }
      return;
    }
    if (this.session.avanzado && (this.session.motor.nivel === 3 || this.session.avanzado.modo === 'prescribir')) return;
    this.stopClock(); this.setBusy(true); this.$('[data-error]').textContent = '';
    try {
      this.session = await this.request('apoyo-avanzado', { revision: this.session.revision });
      this.callbacks.onHistory(this.session.motor.nivel === 3 ? 'Fase 1: cuatro preguntas recomendadas' : 'Fase 1: pregunta prescrita');
    } catch (e) { await this.handleError(e); }
    finally {
      if (this.host.isConnected) { this.setBusy(false); this.renderSession(); }
      if (!this.session.completada && this.session.motor.nivel === 3) this.startClock();
    }
  }
  async selectOption(index) {
    if (this.busy) return;
    this.stopClock(); this.setBusy(true); this.$('[data-error]').textContent = '';
    try {
      this.session = await this.request('seleccionar-opcion', { indice: index, revision: this.session.revision });
      this.callbacks.onHistory('Fase 1: pregunta elegida con apoyo; BKT sin cambio');
    } catch (e) { await this.handleError(e); }
    finally { if (this.host.isConnected) { this.setBusy(false); this.renderSession(); } }
  }
  renderFeedback(result) {
    const host = this.$('[data-feedback]'); host.replaceChildren();
    host.append(this.textNode('h4', this.session.completada ? '¡Genial!' : 'Esta pregunta necesita otro enfoque'));
    if (this.session.completada) {
      host.append(this.textNode('p', `Entonces analizaremos: ${this.session.objetivo.pregunta}`, 'f1-prescribed-question'));
    } else {
      host.append(this.textNode('p', result.feedback));
      if (result.pregunta_sugerida) {
        host.append(this.textNode('p', result.pregunta_sugerida, 'f1-prescribed-question'));
        const useSuggestion = this.textNode('button', 'Usar y editar esta pregunta');
        useSuggestion.type = 'button';
        useSuggestion.addEventListener('click', () => {
          const input = this.$('.f1-form [name=pregunta]');
          input.value = result.pregunta_sugerida;
          input.focus();
          this.startClock();
        });
        host.append(useSuggestion);
      }
    }
  }
  setBusy(value) {
    this.busy = value;
    this.host.setAttribute('aria-busy', String(value));
    this.host.querySelectorAll('button, select').forEach(b => {
      if (value) { b.dataset.wasDisabled = String(b.disabled); b.disabled = true; }
      else { b.disabled = b.dataset.wasDisabled === 'true'; }
    });
  }
  async action(accion, extra = {}) {
    if (this.busy) return false;
    const nivelAnterior = this.session.motor.nivel;
    let success = false;
    this.setBusy(true); this.$('[data-error]').textContent = '';
    try {
      this.session = await this.request('accion', { accion, revision: this.session.revision, ...extra });
      this.callbacks.onHistory(`Fase 1: ${accion}; nivel ${this.session.motor.nombre_nivel}`);
      if (['ayuda', 'timeout', 'nueva', 'contexto'].includes(accion)) this.startClock();
      success = true;
    } catch (e) { await this.handleError(e); }
    finally { if (this.host.isConnected) { this.setBusy(false); this.renderSession(); } }
    const entraEnOrientar = this.session.motor.nivel === 2 && (nivelAnterior !== 2 || accion === 'nueva');
    if (success && (!this.session.lightva || entraEnOrientar || ['ayuda', 'prescribir'].includes(accion))) {
      await this.ensureAdvanced();
    }
    return success;
  }
  async select(variable, vista, secundaria, variables) {
    if (variables === undefined) variables = vista === 'comparacion' ? [secundaria].filter(Boolean) : vista === 'relaciones' ? [variable,secundaria].filter(Boolean) : [variable];
    if (await this.action('contexto', { variable, vista, secundaria, variables })) {
      this.variable = this.session.contexto.variable; this.vista = this.session.contexto.vista;
      this.secundaria = this.session.contexto.secundaria;
      this.describe(this.perfil.variables.find(v => v.columna === this.variable));
      this.renderSession(); await this.loadChart();
    }
  }
  async handleError(e) {
    if (e.status === 409) {
      try {
        this.session = await this.request('estado');
        this.variable = this.session.contexto.variable; this.vista = this.session.contexto.vista;
        this.secundaria = this.session.contexto.secundaria;
        await this.loadChart();
      } catch (_) { /* Conservar el mensaje y permitir reintentar. */ }
    }
    if (this.host.isConnected) this.$('[data-error]').textContent = e.message;
  }
  async evaluate() {
    if (this.busy) return;
    const nivelAnterior = this.session.motor.nivel;
    const form = this.$('.f1-form'), respuesta = Object.fromEntries(new FormData(form));
    // Reutilizar el id si se reintenta el mismo envío tras un error de red.
    const serialized = JSON.stringify(respuesta);
    if (this.pending?.serialized !== serialized || this.pending?.tarea !== this.session.tarea) {
      this.pending = { serialized, tarea: this.session.tarea, intento: crypto.randomUUID() };
    }
    this.setBusy(true); this.$('[data-error]').textContent = '';
    try {
      this.session = await this.request('evaluar', { ...respuesta, revision: this.session.revision, intento: this.pending.intento });
      const cambioContexto = this.variable !== this.session.contexto.variable ||
        this.vista !== this.session.contexto.vista || this.secundaria !== this.session.contexto.secundaria;
      this.variable = this.session.contexto.variable; this.vista = this.session.contexto.vista;
      this.secundaria = this.session.contexto.secundaria;
      this.pending = null;
      this.callbacks.onHistory(`Fase 1: ${this.session.completada ? 'pregunta justificada' : 'respuesta por mejorar'}; BKT actualizado por habilidad`);
      if (this.session.completada) this.stopClock(); else this.startClock();
      if (cambioContexto) await this.loadChart();
    } catch (e) { await this.handleError(e); }
    finally { if (this.host.isConnected) { this.setBusy(false); this.renderSession(); } }
    if (!this.session.lightva || (this.session.motor.nivel === 2 && nivelAnterior !== 2)) {
      await this.ensureAdvanced();
    }
  }
  async loadChart() {
    const id = ++this.chartRequest;
    try {
      const params = new URLSearchParams({ variable: this.variable, vista: this.vista });
      if (this.secundaria) params.set('secundaria', this.secundaria);
      {
        const variables = this.selectedVariables();
        if (!variables.length) params.append('variables','');
        else variables.forEach(col=>params.append('variables',col));
      }
      const chart = await this.request(`grafico?${params}`);
      if (id !== this.chartRequest || !this.host.isConnected) return;
      this.chartPage = 0; this.chart = chart; this.drawChart();
    } catch (e) { if (this.host.isConnected) this.$('[data-error]').textContent = e.message; }
  }
  drawPanels(chart) {
    const host=this.$('[data-chart-panels]'); host.replaceChildren();host.hidden=false;
    this.$('[data-chart]').setAttribute('hidden',''); this.$('[data-series-legend]').replaceChildren();
    const labels={ciclicidad:'Patrones cíclicos',distribucion:'Distribución',variabilidad:'Variabilidad',relaciones:'Relaciones por parejas',frecuencias:'Frecuencias',comparacion:'Comparar categorías'};
    this.$('[data-chart-title]').textContent=labels[chart.vista]; this.$('[data-chart-note]').textContent=chart.nota;
    if(!chart.paneles.length) {
      host.append(this.textNode('p',chart.vista === 'relaciones' ? 'Selecciona dos o más medidas para comparar sus relaciones.' : 'Selecciona variables compatibles para ver sus gráficos.','f1-note'));return;
    }
    const count=12, start=this.chartPage*count;
    const grid=document.createElement('div'); grid.className='f1-panel-grid';
    host.append(grid);
    chart.paneles.slice(start,start+count).forEach(p=>{
      const card=document.createElement('section'); card.className='f1-small-chart';
      const title=p.secundaria ? `${p.variable} · ${p.secundaria}` : p.variable;
      card.append(this.textNode('h4',title));
      const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('role','img');
      const legend=document.createElement('div');
      card.append(svg,this.textNode('p',p.nota,'f1-note'));grid.append(card);
      this.drawChart(p,svg,legend,true);
    });
    if(chart.paneles.length>count) {
      const pager=document.createElement('div');pager.className='f1-actions';
      const prev=this.textNode('button','Anteriores');prev.type='button';prev.disabled=this.chartPage===0;
      const next=this.textNode('button','Siguientes');next.type='button';next.disabled=start+count>=chart.paneles.length;
      prev.addEventListener('click',()=>{this.chartPage--;this.drawChart();});
      next.addEventListener('click',()=>{this.chartPage++;this.drawChart();});
      pager.append(prev,this.textNode('span',`${start+1}–${Math.min(start+count,chart.paneles.length)} de ${chart.paneles.length}`),next);host.append(pager);
    }
  }
  drawChart(chart=this.chart, node=this.$('[data-chart]'), legend=this.$('[data-series-legend]'), panel=false) {
    if (!this.host.isConnected || !chart) { this.resize?.disconnect(); return; }
    if (!panel && chart.paneles) { this.drawPanels(chart); return; }
    if (!panel) { this.$('[data-chart-panels]').hidden=true; node.removeAttribute('hidden'); }
    if (!window.d3) { this.$('[data-error]').textContent = 'No se pudo cargar la librería de gráficos. Comprueba tu conexión y recarga.'; return; }
    const bounds = node.getBoundingClientRect();
    const d3 = window.d3, svg = d3.select(node), w = Math.max(280, bounds.width), h = Math.max(200, bounds.height);
    const margin = { left: 60, right: 18, top: 34, bottom: 52 };
    const x0 = margin.left, x1 = w-margin.right, y0 = h-margin.bottom, y1 = margin.top;
    svg.attr('viewBox', `0 0 ${w} ${h}`).selectAll('*').remove();
    const labels = { evolucion: 'Media mensual', ciclicidad: 'Media por mes y hora', distribucion: 'Distribución', variabilidad: 'Cajas por mes del año', relaciones: 'Dispersión', frecuencias: 'Frecuencias por categoría', comparacion: `Media de ${chart.secundaria} por categoría` };
    const title = `${chart.vista === 'evolucion' ? (chart.variables || [chart.variable]).join(' · ') || 'Selecciona variables' : chart.variable} · ${labels[chart.vista]}`;
    if (!panel) { this.$('[data-chart-title]').textContent = title; this.$('[data-chart-note]').textContent = chart.nota; }
    node.setAttribute('aria-label', title); svg.append('title').text(title);
    legend.replaceChildren();
    if (chart.vista === 'evolucion') {
      legend.append(this.textNode('small','Pulsa los botones de variables para añadir o quitar series.'));
    }
    if (!chart.puntos.length) {
      svg.append('text').attr('x',w/2).attr('y',h/2).attr('text-anchor','middle').text(panel ? 'Sin observaciones suficientes para esta pareja.' : 'Selecciona variables compatibles con esta vista.');
      return;
    }
    const puntos = chart.puntos;
    const mark = '#137c87';
    const padded = values => { const [a,b] = d3.extent(values); const p = (b-a || Math.abs(a) || 1)*.05; return [a-p,b+p]; };
    let x, y, xlabel, ylabel = chart.variable;
    const tooltip = this.$('.f1-tooltip'); tooltip.hidden = true;
    const show = (event, text) => {
      tooltip.textContent = text; tooltip.hidden = false;
      const bounds = event.currentTarget.getBoundingClientRect();
      const px = Number.isFinite(event.clientX) ? event.clientX : bounds.left + bounds.width / 2;
      const py = Number.isFinite(event.clientY) ? event.clientY : bounds.top;
      const box = tooltip.getBoundingClientRect(), pad = 10, offset = 14;
      let left = px + offset, top = py + offset;
      if (left + box.width > window.innerWidth - pad) left = px - box.width - offset;
      if (top + box.height > window.innerHeight - pad) top = py - box.height - offset;
      tooltip.style.left = `${Math.max(pad, Math.min(left, window.innerWidth - box.width - pad))}px`;
      tooltip.style.top = `${Math.max(pad, Math.min(top, window.innerHeight - box.height - pad))}px`;
    };
    const hide = () => { tooltip.hidden = true; };
    node.closest('.f1-panel').onscroll = hide;
    const tip = (selection, text) => selection.attr('tabindex',0)
      .on('pointerenter pointermove focus', (event,d) => show(event,text(d)))
      .on('pointerleave blur',hide).on('keydown',event=>{if(event.key === 'Escape') hide();});
    if (['frecuencias', 'comparacion'].includes(chart.vista)) {
      const counts = chart.vista === 'frecuencias';
      const value = d => counts ? d.n : d.valor;
      x = d3.scaleBand().domain(puntos.map(d => d.categoria)).range([x0,x1]).padding(.2);
      const values = puntos.map(value);
      y = d3.scaleLinear().domain([Math.min(0, d3.min(values)), Math.max(0, d3.max(values)) || 1]).nice().range([y0,y1]);
      tip(svg.selectAll('rect').data(puntos).join('rect').attr('x',d=>x(d.categoria))
        .attr('y',d=>y(Math.max(0,value(d)))).attr('width',x.bandwidth())
        .attr('height',d=>Math.abs(y(value(d))-y(0))).attr('fill',mark),
        d=>`${d.categoria}: ${counts ? d.n + ' registros' : d.valor.toFixed(2) + ' · ' + d.n + ' registros'}`);
      xlabel = chart.variable; ylabel = counts ? 'Registros' : `Media de ${chart.secundaria}`;
    } else if (chart.vista === 'evolucion') {
      const series = (chart.series || [{variable:chart.variable,puntos}]).map(s=>({...s,
        values:s.puntos.map(p=>({...p,date:new Date(p.fecha)}))}));
      const normalized = series.length > 1;
      if (normalized) series.forEach(serie=>{
        const valid=serie.values.filter(p=>p.valor!==null).map(p=>p.valor);
        const low=d3.min(valid), high=d3.max(valid);
        serie.values=serie.values.map(p=>({...p,original:p.valor,
          valor:p.valor===null?null:high===low?0:(p.valor-low)/(high-low)}));
      });
      const all = series.flatMap(s=>s.values);
      x = d3.scaleTime().domain(d3.extent(all,p=>p.date)).range([x0,x1]);
      y = d3.scaleLinear().domain(padded(all.filter(p=>p.valor!==null).map(p=>p.valor))).nice().range([y0,y1]);
      const colors = d3.scaleOrdinal(d3.schemeTableau10).domain(series.map(s=>s.variable));
      series.forEach((serie,i)=>{
        const color = colors(serie.variable);
        const line = d3.line().defined(p=>p.valor!==null).x(p=>x(p.date)).y(p=>y(p.valor));
        svg.append('path').datum(serie.values).attr('d',line).attr('fill','none').attr('stroke',color)
          .attr('stroke-width',2).attr('stroke-dasharray',i >= 10 ? '5,3' : null);
        tip(svg.append('g').selectAll('circle').data(serie.values.filter(p=>p.valor!==null)).join('circle')
          .attr('cx',p=>x(p.date)).attr('cy',p=>y(p.valor)).attr('r',3.5).attr('fill',color).attr('tabindex',0),
          p=>`${serie.variable} · ${p.fecha.slice(0,7)}: ${normalized ? p.original.toFixed(2)+' original · '+p.valor.toFixed(3)+' normalizado' : p.valor.toFixed(2)} · ${p.n} registros`);
        const item=this.textNode('span',serie.variable); const swatch=document.createElement('i');
        swatch.style.backgroundColor=color;item.prepend(swatch);legend.append(item);
      });
      if(normalized) legend.append(this.textNode('small','Cada serie se normaliza entre su mínimo (0) y máximo (1) mensual. Compara patrones, no magnitudes; consulta el valor original al señalar un punto.'));
      xlabel = 'Fecha · medias mensuales'; ylabel = series.length > 1 ? 'Escala normalizada 0–1 por variable' : chart.variable;
    } else if (chart.vista === 'ciclicidad') {
      x = d3.scaleLinear().domain([-.5,23.5]).range([x0,x1]); y = d3.scaleLinear().domain([12.5,.5]).range([y0,y1]);
      const opacity = d3.scaleLinear().domain(d3.extent(puntos,d=>d.valor)).range([.15,1]);
      tip(svg.selectAll('rect').data(puntos).join('rect').attr('x',d=>x(d.hora-.5)).attr('y',d=>y(d.mes-.5)).attr('width',(x1-x0)/24-.5).attr('height',(y0-y1)/12-.5).attr('fill',mark).attr('opacity',d=>opacity(d.valor)),d=>`Mes ${d.mes}, ${d.hora}:00 · media ${d.valor.toFixed(2)} · ${d.n} registros`);
      xlabel = 'Hora · más intensidad = mayor media'; ylabel = 'Mes';
    } else if (chart.vista === 'distribucion') {
      x = d3.scaleLinear().domain([puntos[0].desde,puntos.at(-1).hasta]).range([x0,x1]);
      y = d3.scaleLinear().domain([0,d3.max(puntos,d=>d.n)*1.05]).nice().range([y0,y1]);
      tip(svg.selectAll('rect').data(puntos).join('rect').attr('x',d=>x(d.desde)+1).attr('y',d=>y(d.n)).attr('width',d=>Math.max(1,x(d.hasta)-x(d.desde)-2)).attr('height',d=>y0-y(d.n)).attr('fill',mark),d=>`${d.desde.toFixed(1)}–${d.hasta.toFixed(1)}: ${d.n} registros`);
      xlabel = chart.variable; ylabel = 'Registros';
    } else if (chart.vista === 'variabilidad') {
      x = d3.scaleLinear().domain([.4,12.6]).range([x0,x1]);
      y = d3.scaleLinear().domain(padded(puntos.flatMap(d=>[d.min,d.max]))).nice().range([y0,y1]);
      const bw = (x1-x0)/12*.55;
      const group = svg.selectAll('.box').data(puntos).join('g');
      group.append('line').attr('x1',d=>x(d.mes)).attr('x2',d=>x(d.mes)).attr('y1',d=>y(d.min)).attr('y2',d=>y(d.max)).attr('stroke',mark).attr('stroke-width',2);
      group.append('rect').attr('x',d=>x(d.mes)-bw/2).attr('y',d=>y(d.q3)).attr('width',bw).attr('height',d=>Math.max(1,y(d.q1)-y(d.q3))).attr('fill',mark).attr('opacity',.5);
      group.append('line').attr('x1',d=>x(d.mes)-bw/2).attr('x2',d=>x(d.mes)+bw/2).attr('y1',d=>y(d.mediana)).attr('y2',d=>y(d.mediana)).attr('stroke','currentColor').attr('stroke-width',2);
      tip(group,d=>`Mes ${d.mes} · mediana ${d.mediana.toFixed(2)} · ${d.n} registros · ${d.extremos} valores fuera de bigotes`);
      xlabel = 'Mes del año';
    } else {
      x = d3.scaleLinear().domain(padded(puntos.map(d=>d.x))).nice().range([x0,x1]);
      y = d3.scaleLinear().domain(padded(puntos.map(d=>d.y))).nice().range([y0,y1]);
      tip(svg.selectAll('circle').data(puntos).join('circle').attr('cx',d=>x(d.x)).attr('cy',d=>y(d.y)).attr('r',3).attr('fill',mark).attr('opacity',.4),d=>`${chart.secundaria}: ${d.x.toFixed(2)} · ${chart.variable}: ${d.y.toFixed(2)}`);
      xlabel = chart.secundaria;
    }
    const ticks = w<480?3:5;
    const axis = d3.axisBottom(x);
    if (x.bandwidth) {
      const step = Math.max(1, Math.ceil(puntos.length / ticks));
      axis.tickValues(puntos.filter((_,i)=>i % step === 0).map(d=>d.categoria))
        .tickFormat(d=>d.length > 14 ? d.slice(0,12) + '…' : d);
    } else axis.ticks(ticks);
    svg.append('g').attr('transform',`translate(0,${y0})`).call(axis);
    svg.append('g').attr('transform',`translate(${x0},0)`).call(d3.axisLeft(y).ticks(4));
    svg.append('text').attr('x',x0).attr('y',18).text(['evolucion','ciclicidad','distribucion','frecuencias','comparacion'].includes(chart.vista) ? ylabel : `${ylabel} · unidades del dataset`);
    svg.append('text').attr('x',(x0+x1)/2).attr('y',h-5).attr('text-anchor','middle').text(xlabel);
  }
};
