/* Plan: el servidor conserva evidencia, dominio, grado y plan confirmado. */
window.SigadPhase2 = class {
  constructor(host, interaction, api, callbacks) {
    this.host = host; this.interaction = interaction; this.api = api; this.callbacks = callbacks;
    this.busy = false; this.draft = ''; this.pending = null; this.focusColumn = null; this.qualityCache = {}; this.qualityTab = 'faltantes';
  }
  async request(path, body) {
    return this.api(`/api/fase2/${path}`, {
      ...(body ? { method: 'POST', body: JSON.stringify(body) } : {}),
      headers: { 'Content-Type': 'application/json',
        'X-SiGAD-Session': sessionStorage.getItem('sigad_fase1_sesion') || '',
        ...(this.session ? { 'X-SiGAD-Phase2': this.session.sesion } : {}) },
    });
  }
  node(tag, text, className) {
    const n = document.createElement(tag); n.textContent = text;
    if (className) n.className = className;
    return n;
  }
  button(text, handler, className = '') {
    const b = this.node('button', text, className); b.type = 'button';
    b.disabled = this.busy; b.addEventListener('click', handler); return b;
  }
  async mount() {
    this.session = await this.request('sesion', {});
    this.sample = await this.request('muestra');
    this.focusColumn = this.session.borrador?.variables.at(-1) || null;
    this.host.classList.add('phase1-host', 'phase2-host');
    await this.loadQuality();
    this.render();
    await this.ensureSupport();
    this.startClock();
  }
  stopClock() { clearTimeout(this.clock); this.clock = null; }
  startClock() {
    // Leer y explorar no escala automáticamente el apoyo.
    this.stopClock();
  }
  destroy() { this.stopClock(); this.host?.classList.remove('phase1-host', 'phase2-host'); this.host = null; }
  showPlan(plan, parent) {
    const list = document.createElement('ol');
    plan.pasos.forEach(paso => {
      const li = document.createElement('li');
      li.append(this.node('strong', paso.accion), this.node('p', paso.justificacion),
        this.node('small', `Variables: ${paso.variables.join(', ')}`));
      list.append(li);
    }); parent.append(list);
  }
  format(value) { return value == null ? 'Sin dato' : String(value); }
  renderExplorer(aside, content) {
    const c = this.session.contexto, sample = this.sample;
    const selected = new Set(this.session.borrador?.variables || []);
    aside.append(this.node('h3', 'Escoge tus variables'),
      this.node('p', 'Un clic para añadir; otro para quitar. Puedes elegir todas las que necesites.', 'f1-note'));
    const buttons = this.node('div', '', 'f2-variable-buttons');
    [...new Set(c.variables.map(v=>v.grupo))].forEach(group=>{
      const section = document.createElement('section'); section.className = 'f2-variable-group';
      section.append(this.node('h4', group));
      const chips = this.node('div', '', 'f1-var-list');
      c.variables.filter(v=>v.grupo === group).forEach(v=>{
        const chip = this.button(v.columna, ()=>this.toggleVariable(v.columna), 'f2-variable-chip');
        chip.dataset.column = v.columna; chip.title = v.nombre;
        chip.setAttribute('aria-pressed', String(selected.has(v.columna)));
        chip.disabled = this.busy || this.session.completada;
        chips.append(chip);
      }); section.append(chips); buttons.append(section);
    }); aside.append(buttons);
    const info = this.node('section', '', 'f2-variable-info');
    info.setAttribute('aria-live','polite');
    const v = c.variables.find(v=>v.columna === this.focusColumn);
    if (v) {
      const roles = {medida:'Medida numérica', categoria:'Categoría', tiempo:'Fecha y hora', identificador:'Identificador', coordenada:'Coordenada'};
      info.append(this.node('span', selected.has(v.columna) ? 'Incluida en tu investigación' : 'Fuera de tu selección', 'f2-role'),
        this.node('h4', `${v.columna} · ${v.nombre}`), this.node('p', v.descripcion),
        this.node('p', roles[v.rol] || v.rol, 'f1-note'),
        this.node('p', `Ejemplos: ${(sample.ejemplos[v.columna] || []).map(x=>this.format(x)).join(' · ') || 'Sin valores disponibles'}`));
      const missing = c.faltantes[v.columna] || 0, outliers = c.atipicos_iqr[v.columna]?.cantidad || 0;
      info.append(this.node('p', `Faltantes: ${missing.toLocaleString('es-PE')} de ${c.filas.toLocaleString('es-PE')} (${c.filas ? (missing / c.filas * 100).toFixed(1) : 0}%).`, missing ? 'f2-quality-alert' : 'f2-quality-ok'));
      if (v.rol === 'medida') info.append(this.node('p', `Atípicos candidatos: ${outliers.toLocaleString('es-PE')}. No implica que sean errores.`));
      if (c.escalas[v.columna]) info.append(this.node('p', `Rango: ${c.escalas[v.columna].min} a ${c.escalas[v.columna].max}.`));
      if (v.rol === 'tiempo') info.append(this.node('p', 'Puede usarse para organizar las observaciones en el tiempo.'));
      if (v.rol === 'identificador') info.append(this.node('p', 'Identifica registros; no representa una medida para promediar.'));
    } else info.append(this.node('h4','Conoce la variable'), this.node('p','Pulsa un botón para ver aquí su información y calidad.'));
    aside.append(info);
    const section = document.createElement('section'); section.className = 'f2-sample';
    section.append(this.node('h3', 'Una mirada a tus datos'),
      this.node('p', `Primeras ${sample.filas.length} filas de ${sample.total_filas.toLocaleString('es-PE')} registros. Desliza la tabla para ver todas las columnas.`, 'f1-note'));
    const wrap = document.createElement('div'); wrap.className = 'f2-table-wrap'; wrap.tabIndex = 0;
    wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', 'Muestra de datos con desplazamiento horizontal');
    const table = document.createElement('table');
    const caption = this.node('caption', 'Muestra del archivo original · los datos no han sido modificados');
    table.append(caption);
    const head = document.createElement('thead'), row = document.createElement('tr');
    sample.columnas.forEach(col=>{
      const th = this.node('th', col); th.scope = 'col'; th.dataset.column = col;
      if (selected.has(col)) th.classList.add('f2-highlight'); row.append(th);
    }); head.append(row); table.append(head);
    const body = document.createElement('tbody');
    sample.filas.forEach(values=>{
      const tr = document.createElement('tr');
      values.forEach((value,i)=>{
        const td = this.node('td', this.format(value));
        if (selected.has(sample.columnas[i])) td.classList.add('f2-highlight');
        if (value == null) td.classList.add('f2-missing'); tr.append(td);
      }); body.append(tr);
    }); table.append(body); wrap.append(table); section.append(wrap);
    if (!sample.filas.length) section.append(this.node('p', 'El archivo no contiene filas para mostrar.'));
    section.append(this.node('p', selected.size ? `${selected.size} variables elegidas: ${[...selected].join(', ')}.` : 'Aún no has elegido variables. Todas las columnas siguen visibles para explorar.', 'f1-note'));
    content.append(section);
    this.renderQualityLaboratory(content);
    this.renderOtherPreparation(content);
  }
  async toggleVariable(col) {
    const draft = structuredClone(this.session.borrador || {variables:[], tratamientos:{}});
    const index = draft.variables.indexOf(col);
    if (index >= 0) { draft.variables.splice(index,1); delete draft.tratamientos[col]; }
    else draft.variables.push(col);
    this.focusColumn = col;
    if (await this.mutate('borrador',draft)) {
      const chip = [...this.host.querySelectorAll('.f2-variable-chip')].find(n=>n.dataset.column === col);
      chip?.focus({preventScroll:true});
      const cell = [...this.host.querySelectorAll('th')].find(n=>n.dataset.column === col);
      const wrap = this.host.querySelector('.f2-table-wrap');
      if (cell && index < 0) wrap.scrollTo({left:Math.max(0,cell.offsetLeft-wrap.offsetLeft-wrap.clientWidth/2+cell.clientWidth/2),behavior:'smooth'});
      this.qualityColumn = null;
      await this.loadQuality();
    }
  }
  async chooseTreatment(col, group, action) {
    const draft = structuredClone(this.session.borrador);
    draft.tratamientos[col] = (draft.tratamientos[col] || []).filter(a=>!group.includes(a));
    if (action) draft.tratamientos[col].push(action);
    await this.mutate('borrador',draft);
  }
  renderOtherPreparation(content) {
    const draft = this.session.borrador || {variables:[],tratamientos:{}};
    const box = this.node('section','','f2-preparation');
    const disclosure = document.createElement('details'); disclosure.append(this.node('summary','Otras decisiones: escalas y organización'));
    box.append(this.node('p','Puedes organizar fechas, categorías y escalas cuando tu pregunta lo requiera.','f1-note'));
    if (!draft.variables.length) box.append(this.node('p','Selecciona una o más variables para ver sus opciones.','f1-note'));
    const groups = [
      {label:'Escalas', ids:['conservar_unidades','evaluar_escalado']},
      {label:'Organización', ids:['construir_fecha','revisar_categorias','excluir_identificador','revisar_coordenadas']},
    ];
    const grid = this.node('div','','f2-preparation-grid');
    draft.variables.forEach(col=>{
      const card = this.node('section','','f2-preparation-item'); card.append(this.node('h4',col));
      const c = this.session.contexto, missing = c.faltantes[col] || 0, outliers = c.atipicos_iqr[col]?.cantidad || 0;
      card.append(this.node('p',`${missing} faltantes · ${outliers} atípicos candidatos`, 'f1-note'));
      groups.forEach(group=>{
        const choices = (this.sample.acciones?.[col] || []).filter(a=>group.ids.includes(a.id));
        if (!choices.length) return;
        const label = this.node('label',group.label), select = document.createElement('select');
        select.setAttribute('aria-label',`${group.label} para ${col}`); select.disabled = this.busy || this.session.completada;
        const blank = this.node('option','Elegir una decisión…'); blank.value=''; select.append(blank);
        choices.forEach(a=>{const option=this.node('option',a.texto);option.value=a.id;select.append(option);});
        select.value=(draft.tratamientos[col] || []).find(a=>group.ids.includes(a)) || '';
        select.addEventListener('change',()=>this.chooseTreatment(col,group.ids,select.value));
        label.append(select);card.append(label);
      });
      if (missing) card.append(this.node('p','Completar datos requiere elegir un método adecuado; evita rellenarlos automáticamente con cero.','f1-note'));
      grid.append(card);
    });box.append(grid);disclosure.append(box);content.append(disclosure);
  }
  composedProposal() {
    const draft = this.session.borrador;
    if (!draft?.variables.length) return '';
    const lines = [`Variables que usaré: ${draft.variables.join(', ')}.`];
    draft.variables.forEach(col=>{
      const actions=(draft.tratamientos[col] || []).map(id=>this.sample.acciones[col].find(a=>a.id === id)?.texto).filter(Boolean);
      lines.push(`${col}: ${actions.length ? actions.join('; ') : 'Aún no he elegido preparación.'}`);
    });
    if (this.draft.trim()) lines.push(`Nota adicional: ${this.draft.trim()}`);
    return lines.join('\n');
  }
  render() {
    if (!this.host?.isConnected) return;
    const scrollLeft = this.host.querySelector('.f2-table-wrap')?.scrollLeft || 0;
    const scrollTop = this.host.querySelector('.f2-content')?.scrollTop || 0;
    const s = this.session, c = s.contexto;
    this.host.replaceChildren(); this.interaction.replaceChildren();
    this.host.setAttribute('aria-busy', String(this.busy));
    const intro = this.node('div', '', 'f1-intro');
    const nav = document.createElement('nav'); nav.className = 'f1-phase-strip'; nav.setAttribute('aria-label', 'Fases del ciclo PPDAC');
    ['Problema','Plan','Datos','Análisis','Conclusión'].forEach((label,i)=>{
      const step = document.createElement('span'); step.append(this.node('b', String(i+1)), document.createTextNode(label));
      if (i === 1) step.setAttribute('aria-current','step'); nav.append(step);
    });
    intro.append(nav, this.node('h3','¿Qué datos necesitas para tu análisis?'),
      this.node('p', `Tu pregunta: ${c.objetivo.pregunta}`));
    const layout = this.node('div', '', 'f1-layout f2-layout');
    const aside = this.node('aside', '', 'f1-panel f2-variables');
    const content = this.node('section', '', 'f1-panel f2-content');
    layout.append(aside,content); this.host.append(intro,layout);
    this.renderExplorer(aside,content);
    const controls = document.createElement('section'); controls.className = 'f2-controls';
    const overview = this.node('section', '', 'f2-diagnostic');
    const details = document.createElement('details');
    details.append(this.node('summary', 'Diagnóstico calculado con los datos'));
    details.append(this.node('p', `${c.filas.toLocaleString('es-PE')} registros. Variables del objetivo: ${(c.objetivo.variables || []).join(', ')}.`));
    details.append(this.node('h4', 'Valores faltantes'));
    details.append(this.node('p', Object.entries(c.faltantes).map(([k,v])=>`${k}: ${v}`).join(' · ') || 'No se detectaron.'));
    details.append(this.node('h4', 'Valores atípicos candidatos'));
    details.append(this.node('p', Object.entries(c.atipicos_iqr).map(([k,v])=>`${k}: ${v.cantidad}`).join(' · ') || 'No se detectaron con el criterio utilizado.'));
    details.append(this.node('h4', 'Rangos de las medidas'));
    details.append(this.node('p', Object.entries(c.escalas).map(([k,v])=>`${k}: ${v.min} a ${v.max}`).join(' · ') || 'Sin medidas numéricas.'));
    details.append(this.node('p', c.temporal.inicio ? `Cobertura: ${c.temporal.inicio.slice(0,10)} a ${c.temporal.fin.slice(0,10)}.` : 'Sin fechas válidas detectadas.'));
    details.append(this.node('p', `Columnas de tiempo: ${c.variables.filter(v=>v.rol === 'tiempo').map(v=>v.columna).join(', ') || 'ninguna'}.`));
    details.append(this.node('p', c.espacial.nota));
    c.advertencias.forEach(text=>details.append(this.node('p', text, 'hint')));
    overview.append(details); content.append(overview);
    if (s.resultado) {
      const result = this.node('article', '', 'message');
      result.append(this.node('h3', s.resultado.completa ? 'Evaluación del plan' : 'Tu siguiente paso'),
        this.node('p', s.resultado.feedback));
      const labels = {coherencia:'Relación con la pregunta', calidad:'Calidad de los datos', escalado:'Escalas', estructura:'Organización de los datos'};
      Object.entries(s.resultado.criterios).forEach(([k,v])=>result.append(this.node('p', `${labels[k]} (${v.puntuacion}/2): ${v.explicacion}`)));
      content.append(result);
    }
    if (s.apoyo && !this.sample.calidad_visual) {
      const help = this.node('article', '', 'message');
      help.append(this.node('h3', `Apoyo · ${s.motor.nombre_nivel}`), this.node('p', s.apoyo.mensaje));
      if (!s.completada && s.apoyo.opciones) {
        s.apoyo.opciones.forEach((plan,i)=>{
          const option = document.createElement('section'); option.className = 'f2-option';
          option.append(this.node('h4', `Plan ${i+1}`)); this.showPlan(plan, option);
          option.append(this.button('Elegir este plan', ()=>this.select(i))); help.append(option);
        });
      }
      content.append(help);
    }
    if (s.completada && s.plan) {
      const done = this.node('article', '', 'message success');
      const labels = {usuario:'formulado por ti', sugerido:'elegido con apoyo', prescrito:'prescrito'};
      done.append(this.node('h3', `Plan confirmado · ${labels[s.plan.origen]}`));
      this.showPlan(s.plan.contenido, done);
      done.append(this.node('p', 'El plan queda disponible para la fase 3. Los datos todavía no se han modificado.'));
      done.append(this.button('Continuar a la fase 3 · Preparar datos',()=>this.callbacks.onData(this.session.sesion)));
      content.append(done); this.callbacks.onFinish(s.plan);
    } else {
      const form = document.createElement('form'); form.className = 'question-form strategy-form';
      const label = this.node('label', 'Nota adicional (opcional)'); label.htmlFor = 'phase2-proposal';
      const input = document.createElement('textarea'); input.id = 'phase2-proposal';
      input.required = false; input.maxLength = 4000; input.value = this.draft; input.disabled = this.busy;
      input.placeholder = 'Si deseas, añade algún detalle de tus decisiones.';
      input.addEventListener('input', ()=>{ this.draft = input.value; });
      const submit = this.node('button', this.busy ? 'Procesando…' : 'Evaluar mi plan'); submit.type = 'submit'; submit.disabled = this.busy || !s.borrador?.variables.length;
      const notes = document.createElement('details'); notes.append(this.node('summary','Añadir una nota (opcional)'),label,input);
      form.append(this.node('p','Tu plan se construye con las variables y las decisiones que elegiste.','f1-note'),notes,submit);
      if (s.motor.nivel < 4) {
        form.append(this.button('Necesito ayuda', ()=>this.action('ayuda'), 'secondary'));
        form.append(this.button('Saltar a Prescribir', ()=>this.action('prescribir'), 'secondary'));
      }
      form.addEventListener('submit', e=>{e.preventDefault(); this.evaluate(this.composedProposal());});
      controls.append(form);
      if (!this.sample.calidad_visual && s.motor.nivel > 1 && !s.apoyo) {
        controls.append(this.button('Reintentar generación del apoyo', ()=>this.ensureSupport(), 'secondary'));
      }
    }
    const model = document.createElement('details');
    model.append(this.node('summary', 'Seguimiento de aprendizaje · BKT'));
    model.append(this.node('p', 'Parámetros del prototipo todavía no calibrados. Elegir o recibir un plan no acredita dominio.'));
    Object.entries(s.motor.habilidades).forEach(([k,v])=>model.append(this.node('p', `${k}: P(dominio) ${v.probabilidad.toFixed(3)}`)));
    model.append(this.node('p', `Regla aplicada: ${s.motor.decision.regla}.`)); content.append(model);
    controls.append(this.button('Volver a la fase 1', ()=>this.callbacks.onBack(), 'secondary'));
    if (this.error) { const p = this.node('p', this.error, 'f2-error'); p.setAttribute('role','alert'); controls.append(p); }
    content.append(controls);
    content.scrollTop = scrollTop;
    this.host.querySelector('.f2-table-wrap').scrollLeft = scrollLeft;
    this.callbacks.onState(s);
    if (!this.busy && s.completada && s.plan?.origen === 'prescrito' && !this.advancing) {
      this.advancing = true;
      // Esperar a que termine el render antes de desmontar esta fase.
      setTimeout(() => {
        if (this.host?.isConnected) this.callbacks.onData(s.sesion);
      }, 0);
    }
  }
  async failure(error) {
    this.error = error.message;
    if (error.status === 409) {
      try { this.session = await this.request('estado'); } catch (_) { /* Conservar error original. */ }
    }
  }
  async mutate(path, body) {
    if (this.busy) return false;
    this.stopClock(); this.busy = true; this.error = ''; this.render();
    let ok = false;
    try {
      this.session = await this.request(path, {...body, revision:this.session.revision}); ok = true;
    } catch (error) { await this.failure(error); }
    finally { this.busy = false; this.render(); this.startClock(); }
    return ok;
  }
  async evaluate(propuesta) {
    if (!propuesta || this.busy) return;
    if (this.pending?.propuesta !== propuesta) this.pending = {propuesta, intento:crypto.randomUUID()};
    if (await this.mutate('evaluar', this.pending)) {
      this.pending = null;
      this.callbacks.onHistory(`Fase 2: plan ${this.session.completada ? 'aprobado' : 'evaluado'}; dominio actualizado por habilidad`);
      await this.ensureSupport();
    }
  }
  async action(accion) {
    if (await this.mutate('accion', {accion})) {
      this.callbacks.onHistory(`Fase 2: ${accion}; ${this.session.motor.nombre_nivel}; BKT sin cambio`);
      await this.ensureSupport();
    }
  }
  async ensureSupport() {
    if (this.sample?.calidad_visual && this.session.motor.nivel < 4) return;
    if (this.busy || this.session.completada || this.session.motor.nivel === 1 || this.session.apoyo) return;
    await this.mutate('apoyo', {});
  }
  async select(indice) {
    if (await this.mutate('seleccionar', {indice})) this.callbacks.onHistory('Fase 2: plan elegido con apoyo; BKT sin cambio');
  }
};
