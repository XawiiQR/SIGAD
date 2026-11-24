/* Exploración visual local: el apoyo sigue el grado elegido por el backend. */
Object.assign(window.SigadPhase2.prototype, {
  async loadQuality() {
    const chosen = this.session.borrador?.variables || [];
    const roles = this.session.contexto.variables;
    if (!chosen.includes(this.qualityColumn)) {
      this.qualityColumn = chosen.find(col=>roles.find(v=>v.columna === col)?.rol === 'medida') || chosen[0] || null;
    }
    if (!this.qualityColumn) { this.quality = null; this.render(); return; }
    const col = this.qualityColumn;
    try {
      const result = this.qualityCache[col] || await this.request(`calidad?variable=${encodeURIComponent(col)}`);
      this.qualityCache[col] = result;
      if (this.qualityColumn === col) { this.quality = result; this.qualityError = ''; this.qualityDetail = null; this.qualityBand = null; }
    } catch (e) { this.quality = null; this.qualityError = e.message; }
    this.render();
  },
  svgNode(tag, attributes = {}, text) {
    const n = document.createElementNS('http://www.w3.org/2000/svg',tag);
    Object.entries(attributes).forEach(([k,v])=>n.setAttribute(k,String(v)));
    if (text != null) n.textContent = text;
    return n;
  },
  visualGuidance(q,missing=true) {
    const level = this.session.motor.nivel;
    const texts = missing ? [
      'Explora la disponibilidad y pulsa un periodo para consultar sus registros.',
      '¿Hay mediciones disponibles durante todo el periodo que necesitas? Busca huecos y compara su tamaño.',
      'Compara el periodo destacado con otro que sí tiene mediciones. Observa cuántos registros conservarías antes de elegir una decisión.',
      q.faltantes ? 'Propuesta: revisar primero la distribución y duración de los faltantes. Todavía no elegimos un método para completarlos ni rellenamos con cero.' : 'Propuesta: conservar los valores disponibles. Esta variable no presenta celdas vacías; revisa por separado los periodos sin registros.',
    ] : [
      'Explora la distribución y pulsa una medición para ver los registros cercanos.',
      '¿Hay mediciones alejadas del conjunto? Comprueba su fecha y qué ocurre alrededor antes de decidir.',
      'Examina el candidato destacado y compáralo con sus registros vecinos. Un valor distinto puede corresponder a un episodio real.',
      q.atipicos ? 'Propuesta: investigar los candidatos y su contexto antes de decidir un tratamiento. No eliminarlos solo por estar alejados de los demás.' : 'Propuesta: conservar las observaciones. El criterio utilizado no identifica candidatos atípicos; eso no demuestra que todo el archivo esté libre de errores.',
    ];
    return texts[level-1];
  },
  renderQualityLaboratory(content) {
    const chosen = this.session.borrador?.variables || [];
    const box = this.node('section','','f2-lab');
    const header = this.node('div','','f2-lab-header');
    header.append(this.node('h3','Explora la calidad de tus datos'));
    const level = this.session.motor.nivel;
    header.append(this.node('span',`Apoyo ${level} · ${this.session.motor.nombre_nivel}`,'f2-support-badge'));
    box.append(header, this.node('p','Observa → compara → añade una decisión al plan. El archivo original se conserva.','f1-note'));
    if (!chosen.length) { box.append(this.node('p','Selecciona una variable para comenzar la exploración.')); content.append(box); return; }
    const label = this.node('label','Variable que explorarás'), select = document.createElement('select');
    select.setAttribute('aria-label','Variable para explorar calidad');
    chosen.forEach(col=>{const o=this.node('option',col);o.value=col;select.append(o);});
    select.value=this.qualityColumn;select.disabled=this.busy;
    select.addEventListener('change',async()=>{this.qualityColumn=select.value;await this.loadQuality();});label.append(select);box.append(label);
    const q=this.quality;
    if (!q || q.variable !== this.qualityColumn) {
      box.append(this.node('p',this.qualityError || 'Cargando resumen de calidad…'));
      if(this.qualityError) box.append(this.button('Reintentar vista',()=>this.loadQuality()));
      content.append(box);return;
    }
    [true,false].forEach(missing=>{
      box.append(this.node('h4',missing?'Datos nulos (faltantes)':'Valores atípicos'));
      const guidance=this.node('div','','f2-visual-guidance');
      guidance.append(this.node('strong',level === 1 ? 'Tu exploración' : level === 4 ? 'Caso explicado' : 'Pista para observar'),this.node('p',this.visualGuidance(q,missing)));
      if(level < 4 && !this.session.completada) {
        guidance.append(this.button('Necesito más apoyo',()=>this.action('ayuda'),'secondary'));
        guidance.append(this.button('Saltar a Prescribir',()=>this.action('prescribir'),'secondary'));
      }
      box.append(guidance);
      if(missing) this.drawMissing(q,box); else this.drawDifferent(q,box);
      this.renderVisualDecisions(q,box,missing);
    });
    content.append(box);
  },
  drawReferences(svg,ref,y,box,periodos) {
    if(!ref) return;
    const lines=[['media','Promedio','#315fc7',null],['q1','Q1 (25%)','#9868b8','5,4'],['q3','Q3 (75%)','#9868b8','5,4']];
    const legend=this.node('div','','f2-reference-legend');
    lines.forEach(([key,label,color,dash])=>{
      const attrs={x1:40,x2:700,y1:y(ref[key]),y2:y(ref[key]),stroke:color,'stroke-width':1.5,opacity:.85};
      if(dash) attrs['stroke-dasharray']=dash;
      const line=this.svgNode('line',attrs);
      line.append(this.svgNode('title',{},`${label}: ${ref[key].toFixed(2)}`));svg.append(line);
      const item=this.node('span',`${label}: ${ref[key].toFixed(2)}`), swatch=document.createElement('i');
      swatch.style.borderTop=`2px ${dash?'dashed':'solid'} ${color}`;item.prepend(swatch);legend.append(item);
    });box.append(legend,this.node('p',periodos ? 'Referencias calculadas sobre las medias de los periodos con datos. El promedio de esta curva puede diferir del promedio de todos los registros.' : 'Referencias calculadas con todos los registros numéricos válidos, no solo con la muestra de puntos.','f1-note'));
  },
  drawMissing(q,box) {
    const stats=this.node('div','','f2-quality-stats');
    stats.append(this.node('span',`${q.disponibles.toLocaleString('es-PE')} disponibles`),this.node('span',`${q.faltantes.toLocaleString('es-PE')} faltantes`),this.node('span',`${q.total ? (q.faltantes/q.total*100).toFixed(1) : 0}% sin valor`));box.append(stats);
    const svg=this.svgNode('svg',{viewBox:'0 0 720 170',role:'group','aria-label':`Disponibilidad y medias de ${q.variable} por periodo`});
    const bands=q.bandas, step=660/Math.max(1,bands.length), means=bands.map(b=>b.media).filter(v=>v !== null);
    const min=Math.min(...means,0), max=Math.max(...means,1), y=v=>100-(v-min)/(max-min || 1)*72;
    let path='', connected=false;
    const suggested = bands.findIndex(b=>b.faltantes > 0 || b.total === 0);
    bands.forEach((b,i)=>{
      if(b.media === null) {connected=false;return;}
      path+=`${connected?'L':'M'}${40+i*step+step/2},${y(b.media)} `;connected=true;
    });
    if(q.numerica) {
      svg.append(this.svgNode('path',{d:path,fill:'none',stroke:'#137c87','stroke-width':2}));
      bands.forEach((b,i)=>{if(b.media !== null) {
        const dot=this.svgNode('circle',{cx:40+i*step+step/2,cy:y(b.media),r:4,fill:'#137c87',stroke:'none','stroke-width':1.5,tabindex:0,role:'button','aria-label':`${b.etiqueta}: media ${b.media.toFixed(2)}`});
        dot.append(this.svgNode('title',{},`${b.etiqueta}: media ${b.media.toFixed(2)}`));
        const inspect=()=>{this.qualityBand=b;this.render();};dot.addEventListener('click',inspect);
        dot.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect();}});svg.append(dot);
      }});
    }
    bands.forEach((b,i)=>{
      const ratio=b.total ? b.faltantes/b.total : 1;
      const rect=this.svgNode('rect',{x:40+i*step,y:115,width:Math.max(1,step-2),height:25,rx:3,
        fill:!b.total ? '#d8dee8' : ratio ? '#e5ab48' : '#c8e9e4',opacity:b.total && ratio ? .4+.6*ratio : 1,
        stroke:this.session.motor.nivel >= 3 && i === suggested ? '#845100' : 'none','stroke-width':3,
        tabindex:0,role:'button','aria-label':`${b.etiqueta}: ${b.faltantes} faltantes de ${b.total} registros`});
      rect.append(this.svgNode('title',{},`${b.etiqueta} · ${b.faltantes} faltantes / ${b.total} registros`));
      const inspect=()=>{this.qualityBand=b;this.render();};rect.addEventListener('click',inspect);rect.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect();}});svg.append(rect);
      if(i===0||i===bands.length-1||i===Math.floor(bands.length/2)) svg.append(this.svgNode('text',{x:40+i*step+step/2,y:158,'text-anchor':'middle'},b.etiqueta));
    });
    svg.append(this.svgNode('text',{x:8,y:25},q.numerica?'Media del periodo':'Disponibilidad de registros'));box.append(svg);
    box.append(this.node('p','Verde: valores disponibles · Ámbar: celdas sin valor · Gris: periodo sin registros. Pulsa una franja.','f1-note'));
    const b=this.qualityBand || (this.session.motor.nivel >=3 ? bands[suggested] : null);
    if(b) box.append(this.node('p',`${b.etiqueta}: ${b.total ? `${b.faltantes} celdas vacías de ${b.total} registros; ${b.total-b.faltantes} valores disponibles.` : 'No hay registros en este periodo. Esto no equivale a una celda vacía.'}`,'f2-observation'));
    box.append(this.node('p',q.nota,'f1-note'));
    if(q.sin_fecha) box.append(this.node('p',`${q.sin_fecha} registros no tienen fecha válida y no aparecen en la vista temporal.`,'f1-note'));
    box.append(this.node('p',`Si utilizas solo registros con valor en ${q.variable}, conservarías ${q.disponibles.toLocaleString('es-PE')} de ${q.total.toLocaleString('es-PE')}. Este cálculo se refiere solo a esta variable.`,'f2-observation'));
  },
  drawDifferent(q,box) {
    if(!q.numerica) {box.append(this.node('p','Esta variable no es una medida numérica. Explora sus faltantes o elige una medida para observar valores atípicos.'));return;}
    box.append(this.node('p',`${q.atipicos.toLocaleString('es-PE')} candidatos según el criterio de distribución. Un candidato no es un error confirmado.`));
    const svg=this.svgNode('svg',{viewBox:'0 0 720 190',role:'group','aria-label':`Mediciones de ${q.variable}; pulsa un punto para consultar sus vecinos`});
    const ref=q.referencias_registros;
    const values=[...q.puntos.map(p=>p.valor),...(ref ? [ref.media,ref.q1,ref.q3] : [])], lo=Math.min(...values,0), hi=Math.max(...values,1);
    const y=v=>150-(v-lo)/(hi-lo || 1)*115, x=f=>45+f/Math.max(1,q.total-1)*640;
    svg.append(this.svgNode('path',{d:'M40 25 V155 H700',fill:'none',stroke:'#b8c7d9'}));
    svg.append(this.svgNode('text',{x:5,y:25},String(Number(hi.toPrecision(4)))));
    svg.append(this.svgNode('text',{x:5,y:150},String(Number(lo.toPrecision(4)))));
    this.drawReferences(svg,ref,y,box,false);
    const highlight=q.puntos.find(p=>p.atipico);
    q.puntos.forEach(p=>{
      const guided=this.session.motor.nivel >=3 && p===highlight;
      const point=this.svgNode('circle',{cx:x(p.fila),cy:y(p.valor),r:guided?7:4,fill:p.atipico?'#b97520':'#137c87',opacity:.8,
        stroke:guided?'#54330c':'white','stroke-width':guided?2:1,tabindex:0,role:'button','aria-label':`Registro ${p.fila+1}, valor ${p.valor}${p.atipico?', candidato atípico':''}`});
      point.append(this.svgNode('title',{},`Registro ${p.fila+1} · ${p.valor} · ${p.fecha || 'Sin fecha'}`));
      const inspect=()=>this.inspectPoint(q.variable,p.fila);point.addEventListener('click',inspect);point.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect();}});svg.append(point);
    });svg.append(this.svgNode('text',{x:350,y:183,'text-anchor':'middle'},'Posición del registro en el archivo (no distancia temporal)'));box.append(svg,this.node('p',q.nota_puntos,'f1-note'));
    if(this.qualityDetail?.variable === q.variable) {
      const detail=this.node('div','','f2-observation');detail.append(this.node('strong',`Alrededor del registro ${this.qualityDetail.fila+1}`));
      this.qualityDetail.registros.forEach(r=>detail.append(this.node('p',`${r.fila === this.qualityDetail.fila?'→ ':''}Registro ${r.fila+1} · ${r.fecha || 'Sin fecha'} · ${this.format(r.valor)}${r.estacion?' · '+r.estacion:''}`)));
      detail.append(this.node('p',this.qualityDetail.nota,'f1-note'));box.append(detail);
    } else if(this.session.motor.nivel >=3 && highlight) box.append(this.button('Comparar el candidato destacado con sus vecinos',()=>this.inspectPoint(q.variable,highlight.fila),'secondary'));
  },
  async inspectPoint(variable,fila) {
    try {this.qualityDetail=await this.request(`calidad?variable=${encodeURIComponent(variable)}&fila=${fila}`);this.render();}
    catch(e){this.error=e.message;this.render();}
  },
  renderVisualDecisions(q,box,missing=this.qualityTab==='faltantes') {
    const group=missing?['revisar_faltantes','imputar','excluir_faltantes']:['revisar_atipicos','conservar_atipicos'];
    const actions=(this.sample.acciones?.[q.variable] || []).filter(a=>group.includes(a.id));
    const section=this.node('section','','f2-visual-decisions');section.append(this.node('h4','Añade tu decisión al plan'));
    if(!actions.length) {section.append(this.node('p',missing?'No hay celdas vacías que requieran un tratamiento en esta variable.':'No hay candidatos atípicos que requieran una decisión con este criterio.','f1-note'));box.append(section);return;}
    const level=this.session.motor.nivel;
    const shown=level===4?actions.filter(a=>a.id===(missing?'revisar_faltantes':'revisar_atipicos')):actions;
    shown.forEach(a=>{
      const chosen=(this.session.borrador.tratamientos[q.variable] || []).includes(a.id);
      const b=this.button(level===4?`${chosen?'Propuesta añadida':'Adoptar propuesta'}: ${a.texto}`:a.texto,()=>this.chooseTreatment(q.variable,group,chosen?'':a.id),'f2-decision');
      b.setAttribute('aria-pressed',String(chosen));b.disabled=this.busy||this.session.completada;section.append(b);
    });
    if(level>=3) section.append(this.node('p',missing?'Completar exige elegir y comprobar un método. Excluir registros puede reducir cobertura. Revisar primero mantiene abiertas esas decisiones.':'Conservar permite investigar el episodio; revisar no significa borrar. Un gráfico por sí solo no confirma un error.','f1-note'));
    if(level===4) section.append(this.node('p','Esta decisión se registra con apoyo de nivel Prescribir, sin acreditar un acierto autónomo.','f1-note'));
    box.append(section);
  },
});
