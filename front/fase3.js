window.SigadPhase3 = class {
  constructor(host,api,origin,onState) {Object.assign(this,{host,api,origin,onState,step:'nulos',column:null,choice:null,preview:null,busy:false,error:''});}
  node(tag,text,cls) {const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
  button(text,fn) {const b=this.node('button',text);b.type='button';b.disabled=this.busy;b.onclick=fn;return b;}
  async mount() {
    this.session=await this.api('/api/fase3/sesion',{method:'POST',headers:{'Content-Type':'application/json','X-SiGAD-Phase2':this.origin},body:'{}'});
    this.scaleColumns=[...(this.session.medidas||[])];
    this.column=this.session.variables.find(c=>this.session.datos.numericas.includes(c)&&this.session.datos.nulos[c]>0)||this.session.variables[0];this.render();
  }
  async action(operacion,extra={}) {
    if(this.busy)return;
    this.busy=true;this.error='';this.notice='';this.render();
    try {
      const r=await this.api('/api/fase3/operacion',{method:'POST',headers:{'Content-Type':'application/json','X-SiGAD-Phase3':this.session.sesion},
        body:JSON.stringify({operacion:operacion==='previsualizar'&&this.step==='escalas'?'escalas':operacion,revision:this.session.revision,columna:this.column,accion:this.choice,variables:this.scaleColumns,...extra})});
      this.session=r.estado;
      if(!['ayuda','prescribir','comparar','ventana'].includes(operacion))this.preview=r.previa||null;
      if(operacion==='previsualizar'){this.focusResult=true;this.missingWindow=r.previa?.ventana||null;}
      if(r.ventana)this.missingWindow=r.ventana;
      if(['aplicar','deshacer'].includes(operacion))this.missingWindow=null;
      if(operacion==='aplicar'){this.notice='Tratamiento aplicado: la tabla y los gráficos ya usan la copia actualizada.';}
      if(operacion==='deshacer'){this.notice='Tratamiento deshecho: se restauraron los datos anteriores.';}
    } catch(e){this.error=e.message;}
    finally{this.busy=false;this.render();}
  }
  options() {
    if(this.step==='nulos')return [['conservar','Conservar los valores nulos','Mantiene los huecos; no inventa mediciones.'],['media','Completar con la media','Rellena los nulos con el promedio de los valores disponibles. Puede suavizar la evolución.'],['mediana','Completar con la mediana','Sustituye los nulos por un valor central. Puede ocultar cambios temporales.'],['excluir_nulos','Trabajar sin esos registros','Elimina las filas sin valor en esta variable y reduce la cobertura.']];
    if(this.step==='atipicos')return [['conservar','Conservar e investigar','Un extremo puede ser un episodio real.'],['excluir_atipicos','Excluir candidatos atípicos','Elimina filas fuera de los límites IQR; puede borrar episodios reales y datos de otras columnas.'],['limitar_iqr','Limitar los extremos con IQR','Recorta valores a los límites Q1 − 1,5 IQR y Q3 + 1,5 IQR. Puede ocultar episodios reales.']];
    return [['conservar','Conservar las unidades','Permite interpretar las magnitudes originales.'],['normalizar','Normalizar entre 0 y 1','Facilita comparar patrones entre variables; no corrige errores ni demuestra relaciones.']];
  }
  table(data) {
    const wrap=this.node('div',null,'f3-table'),t=this.node('table'),head=this.node('tr');
    data.columnas.forEach(c=>head.append(this.node('th',c)));t.append(head);
    data.muestra.forEach(row=>{const tr=this.node('tr');data.columnas.forEach(c=>tr.append(this.node('td',row[c]===null?'Nulo':typeof row[c]==='number'?Number(row[c].toFixed(4)):row[c])));t.append(tr);});
    wrap.append(t);return wrap;
  }
  svg(tag,attrs={},text) {
    const n=document.createElementNS('http://www.w3.org/2000/svg',tag);
    Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));
    if(text!=null)n.textContent=text;return n;
  }
  changedChart(examples) {
    const card=this.node('div',null,'f3-record-chart');
    card.append(this.node('h4','Mediciones modificadas · antes y después'));
    const svg=this.svg('svg',{viewBox:'0 0 720 225',role:'img','aria-label':'Valores originales y resultado de los registros modificados'});
    const values=examples.flatMap(e=>[e.antes,e.despues]).filter(v=>typeof v==='number');
    const low=Math.min(0,...values),high=Math.max(1,...values),y=v=>165-(v-low)/(high-low)*125;
    const step=620/Math.max(1,examples.length);
    [low,(low+high)/2,high].forEach(v=>{svg.append(this.svg('line',{x1:48,x2:690,y1:y(v),y2:y(v),stroke:'#dbe3ef'}),this.svg('text',{x:43,y:y(v)+4,'text-anchor':'end'},Number(v.toPrecision(4))));});
    examples.forEach((e,i)=>{
      const x=55+step*(i+.5);
      [['antes','#137c87',-9],['despues','#2866d6',9]].forEach(([key,color,dx])=>{
        const value=e[key];
        if(typeof value==='number') {
          const mark=this.svg('circle',{cx:x+dx,cy:y(value),r:5,fill:color,tabindex:0});
          mark.append(this.svg('title',{},'Fila '+e.fila+' · '+key+': '+value));svg.append(mark);
        } else svg.append(this.svg('text',{x:x+dx,y:190,'text-anchor':'middle',fill:color},key==='antes'?'∅':'×'));
      });
      if(typeof e.antes==='number'&&typeof e.despues==='number')svg.append(this.svg('line',{x1:x-9,x2:x+9,y1:y(e.antes),y2:y(e.despues),stroke:'#9baec8','stroke-dasharray':'3,3'}));
      svg.append(this.svg('text',{x,y:214,'text-anchor':'middle'},'Fila '+e.fila));
    });
    card.append(svg,this.node('p','Verde: antes · Azul: después · ∅: nulo original · ×: valor retirado. Se muestran hasta ocho registros afectados, no promedios.'));
    return card;
  }
  comparison(before,after) {
    const original=before.graficos?.[this.column],result=after?.graficos?.[this.column];
    if(!original)return null;
    const box=this.node('section',null,'f3-card f3-chart');
    box.append(this.node('h3',result?'Así cambiarían tus datos':'Así están tus datos'));
    const scenarios=[['Antes',original,'#137c87']];
    if(result)scenarios.push(['Después',result,'#2866d6']);
    const labels=[...new Set(scenarios.flatMap(([,g])=>g.puntos.map(p=>p.x)))].sort((a,b)=>original.temporal?a.localeCompare(b):Number(a.replace('Bloque ',''))-Number(b.replace('Bloque ','')));
    const values=scenarios.flatMap(([,g])=>g.puntos.filter(p=>p.valor!==null).map(p=>p.valor));
    const lo=Math.min(0,...values),hi=Math.max(1,...values),y=v=>156-(v-lo)/(hi-lo)*120;
    const x=i=>52+(labels.length===1?310:i*620/(labels.length-1));
    const svg=this.svg('svg',{viewBox:'0 0 720 210',role:'img','aria-label':'Comparación de medias por periodo de '+this.column});
    svg.append(this.svg('title',{},'Antes y después: '+this.column));
    [0,.5,1].forEach(t=>{const value=lo+(hi-lo)*t;svg.append(this.svg('line',{x1:52,x2:680,y1:y(value),y2:y(value),stroke:'#dbe3ef'}),this.svg('text',{x:45,y:y(value)+4,'text-anchor':'end'},Number(value.toPrecision(4))));});
    scenarios.forEach(([name,g,color],seriesIndex)=>{
      const map=new Map(g.puntos.map(p=>[p.x,p]));
      let path='',connected=false;
      labels.forEach((label,i)=>{
        const p=map.get(label);
        if(!p||p.valor===null){connected=false;return;}
        path+=(connected?'L':'M')+x(i)+','+y(p.valor)+' ';connected=true;
        const dot=this.svg('circle',{cx:x(i),cy:y(p.valor),r:seriesIndex?3:4,fill:seriesIndex?'white':color,stroke:color,'stroke-width':1.5,tabindex:0});
        dot.append(this.svg('title',{},name+' · '+label+': '+p.valor.toFixed(3)+' · '+p.disponibles+' disponibles / '+p.total+' registros'));svg.append(dot);
      });
      svg.append(this.svg('path',{d:path,fill:'none',stroke:color,'stroke-width':2,'stroke-dasharray':seriesIndex?'6,4':'none'}));
      const badge=this.node('p',name+': promedio global '+(g.media===null?'sin datos':g.media.toFixed(3))+' · '+g.disponibles+' valores disponibles · '+g.nulos+' nulos','f3-chart-legend');
      badge.style.color=color;box.append(badge);
    });
    const tickIndices=[...new Set([0,Math.floor((labels.length-1)/2),labels.length-1])].filter(i=>i>=0);
    tickIndices.forEach(i=>svg.append(this.svg('text',{x:x(i),y:180,'text-anchor':'middle'},labels[i])));
    svg.append(this.svg('text',{x:52,y:18},'Media por '+(original.temporal?'periodo':'bloque de filas')+' · '+this.column));
    box.append(svg);
    box.append(this.node('p',original.temporal?'Cada punto resume las mediciones del periodo. Los huecos se mantienen; las medias pueden ocultar valores extremos.':'Sin fecha válida: se muestran medias por bloques de filas, no una evolución temporal.'));
    if(original.sin_fecha)box.append(this.node('p',original.sin_fecha+' registros sin fecha válida quedan fuera de la curva, pero cuentan en el promedio global.'));
    if(result&&this.choice==='excluir_nulos')box.append(this.node('p','Las curvas pueden coincidir: excluir una celda sin valor no cambia la media calculada con los valores disponibles de esa variable. Sí elimina filas y sus datos en otras columnas.','f3-hint'));
    if(result&&this.choice==='conservar')box.append(this.node('p','Las curvas coinciden porque conservaste los datos.','f3-hint'));
    const coverage=this.node('div',null,'f3-coverage');
    scenarios.forEach(([name,g])=>{
      const section=this.node('div');section.append(this.node('strong',name+' · Disponibilidad'));
      const band=this.node('div',null,'f3-coverage-band');
      g.puntos.forEach(p=>{
        const ratio=p.total?p.disponibles/p.total:0;
        const segment=this.node('span');segment.style.background=p.total?'linear-gradient(to top,#c8e9e4 '+ratio*100+'%,#f3d5a1 '+ratio*100+'%)':'#d8dee8';
        segment.title=p.x+': '+p.disponibles+' disponibles, '+(p.total-p.disponibles)+' nulos';band.append(segment);
      });section.append(band);coverage.append(section);
    });
    box.append(coverage,this.node('p','Disponibilidad por periodo: verde = valores presentes; ámbar = nulos; gris = sin registros. Los gráficos resumen todos los datos, no solo las ocho filas de la tabla.','f1-note'));
    return box;
  }
  outlierScatter(before,after) {
    const d=before.diagnostico?.[this.column],updated=after?.diagnostico?.[this.column];
    const box=this.node('section',null,'f3-card f3-chart f3-outlier-scatter');
    box.append(this.node('h3','Valores atípicos · mediciones individuales'));
    if(!d){box.append(this.node('p','No hay mediciones numéricas válidas.'));return box;}
    const percentage=s=>s.disponibles?100*s.candidatos/s.disponibles:0;
    box.append(this.node('p','Antes: '+d.candidatos.toLocaleString('es-PE')+' de '+d.disponibles.toLocaleString('es-PE')+' valores válidos ('+percentage(d).toFixed(2)+'%) candidatos IQR.','f3-chart-legend'));
    if(after)box.append(this.node('p',updated?'Después: '+updated.candidatos.toLocaleString('es-PE')+' de '+updated.disponibles.toLocaleString('es-PE')+' ('+percentage(updated).toFixed(2)+'%) candidatos.':'Después: no quedan valores válidos.','f3-chart-legend'));
    const points=this.preview?.dispersion||d.dispersion||[];
    const lo=Math.min(0,d.minimo,updated?.minimo??d.minimo),hi=Math.max(1,d.maximo,updated?.maximo??d.maximo);
    const lastRow=Math.max(1,...points.map(p=>p.fila));
    const x=f=>58+(f-1)/Math.max(1,lastRow-1)*620,y=v=>218-(v-lo)/(hi-lo)*170;
    const svg=this.svg('svg',{viewBox:'0 0 720 270',role:'img','aria-label':'Mediciones de '+this.column+' antes y después, a lo largo del archivo'});
    [lo,(hi+lo)/2,hi].forEach(v=>svg.append(this.svg('line',{x1:58,x2:680,y1:y(v),y2:y(v),stroke:'#dbe3ef'}),this.svg('text',{x:50,y:y(v)+4,'text-anchor':'end'},Number(v.toPrecision(4)))));
    [['media','#2866d6','none'],['q1','#9766c2','5,4'],['q3','#9766c2','5,4']].forEach(([key,color,dash])=>{
      const line=this.svg('line',{x1:58,x2:680,y1:y(d[key]),y2:y(d[key]),stroke:color,'stroke-dasharray':dash,opacity:.7});
      line.append(this.svg('title',{},key+': '+d[key].toFixed(3)));svg.append(line);
    });
    points.forEach(p=>{
      const dot=this.svg('circle',{cx:x(p.fila),cy:y(p.valor),r:3,fill:p.atipico?'#b97520':'#137c87',opacity:.6,tabindex:0});
      dot.append(this.svg('title',{},'Fila '+p.fila+' · original '+p.valor+(p.atipico?' · candidato IQR':'')));svg.append(dot);
      if(after&&(p.eliminado||p.despues!==p.valor)){
        if(p.eliminado){
          const cross=this.svg('text',{x:x(p.fila),y:y(p.valor)+4,'text-anchor':'middle',fill:'#627086'},'×');
          cross.append(this.svg('title',{},'Fila '+p.fila+' · excluida'));svg.append(cross);
        }else{
          svg.append(this.svg('line',{x1:x(p.fila),x2:x(p.fila),y1:y(p.valor),y2:y(p.despues),stroke:'#2866d6',opacity:.4}));
          const newPoint=this.svg('circle',{cx:x(p.fila),cy:y(p.despues),r:3.5,fill:'white',stroke:'#2866d6','stroke-width':1.5,tabindex:0});
          newPoint.append(this.svg('title',{},'Fila '+p.fila+' · resultado '+p.despues));svg.append(newPoint);
        }
      }
    });
    [1,Math.ceil(lastRow/2),lastRow].forEach(f=>svg.append(this.svg('text',{x:x(f),y:240,'text-anchor':'middle'},String(f))));
    svg.append(this.svg('text',{x:370,y:265,'text-anchor':'middle'},'Posición original en el archivo · no distancia temporal'));
    box.append(svg,this.node('p','Verde: habitual · Ámbar: candidato · Azul hueco: valor modificado · ×: excluido. Líneas: media, Q1 y Q3 originales.','f1-note'),
      this.node('p','Hasta 800 valores espaciados por filas, sin igualar la cantidad de candidatos y habituales. Los recuentos y porcentajes se calculan con todos los valores válidos. Q1 y Q3 no son los límites de detección.','f1-note'));
    const details=this.node('details');details.append(this.node('summary','Ver también el boxplot'),this.outlierComparison(before,after));box.append(details);
    return box;
  }
  outlierComparison(before,after) {
    const datasets=[['Antes',before,'#137c87']];
    if(after)datasets.push(['Después',after,'#2866d6']);
    const box=this.node('section',null,'f3-card f3-chart');
    box.append(this.node('h3','Valores atípicos · distribución antes y después'));
    const stats=datasets.map(([name,data,color])=>({name,color,stats:data.diagnostico?.[this.column]}));
    const valid=stats.filter(s=>s.stats);
    if(!valid.length){box.append(this.node('p','No hay mediciones numéricas disponibles para construir el boxplot.'));return box;}
    const lo=Math.min(...valid.map(s=>s.stats.minimo)),hi=Math.max(...valid.map(s=>s.stats.maximo));
    const y=v=>220-(v-lo)/(hi-lo||1)*170;
    const svg=this.svg('svg',{viewBox:'0 0 720 275',role:'img','aria-label':'Boxplots de '+this.column+' con escala compartida'});
    [lo,(hi+lo)/2,hi].forEach(v=>svg.append(this.svg('line',{x1:65,x2:690,y1:y(v),y2:y(v),stroke:'#dbe3ef'}),this.svg('text',{x:58,y:y(v)+4,'text-anchor':'end'},Number(v.toPrecision(4)))));
    stats.forEach((s,i)=>{
      const x=stats.length===1?360:240+i*280,d=s.stats;
      svg.append(this.svg('text',{x,y:255,'text-anchor':'middle'},s.name));
      if(!d){svg.append(this.svg('text',{x,y:140,'text-anchor':'middle'},'Sin valores válidos'));return;}
      svg.append(this.svg('line',{x1:x,x2:x,y1:y(d.bigote_inferior),y2:y(d.bigote_superior),stroke:s.color,'stroke-width':2}),
        this.svg('rect',{x:x-38,y:y(d.q3),width:76,height:Math.max(1,y(d.q1)-y(d.q3)),fill:s.color,'fill-opacity':.18,stroke:s.color,'stroke-width':2}));
      [d.bigote_inferior,d.bigote_superior,d.mediana].forEach(v=>svg.append(this.svg('line',{x1:x-38,x2:x+38,y1:y(v),y2:y(v),stroke:s.color,'stroke-width':2})));
      d.puntos.forEach((p,j)=>{
        const dot=this.svg('circle',{cx:x+55+(j%7)*4,cy:y(p.valor),r:p.atipico?3.5:2.5,fill:p.atipico?'#b97520':s.color,opacity:.7,tabindex:0});
        dot.append(this.svg('title',{},s.name+' · Fila '+p.fila+': '+p.valor+(p.atipico?' · candidato atípico':'')));svg.append(dot);
      });
      box.append(this.node('p',s.name+': '+d.candidatos+' candidatos · mediana '+d.mediana.toFixed(3),'f3-chart-legend'));
    });
    box.append(svg,this.node('p','Caja: Q1–Q3 · raya: mediana · puntos ámbar: candidatos IQR. Misma escala antes y después. Estadísticas sobre todas las mediciones; hasta 80 puntos habituales y 80 candidatos por gráfico.','f1-note'));
    return box;
  }
  kdeComparison(data) {
    const kde=data.kde?.[this.column];
    if(!kde)return null;
    const box=this.node('section',null,'f3-card f3-chart f3-kde');
    box.append(this.node('h3','Distribución · observados, media y mediana'));
    if(!kde.x.length){box.append(this.node('p',kde.motivo));return box;}
    const series=[['original','Observados','#137c87'],['media','Imputación con media','#2866d6'],['mediana','Imputación con mediana','#9766c2']];
    const lo=kde.x[0],hi=kde.x.at(-1),maximum=Math.max(...series.flatMap(([key])=>kde.curvas[key]))||1;
    const x=v=>65+(v-lo)/(hi-lo)*610,y=v=>200-v/maximum*150;
    const svg=this.svg('svg',{viewBox:'0 0 720 255',role:'img','aria-label':'Densidades KDE superpuestas de '+this.column});
    [0,.5,1].forEach(t=>svg.append(this.svg('line',{x1:65,x2:675,y1:y(t*maximum),y2:y(t*maximum),stroke:'#dbe3ef'}),this.svg('text',{x:58,y:y(t*maximum)+4,'text-anchor':'end'},Number((t*maximum).toPrecision(3)))));
    [0,.25,.5,.75,1].forEach(t=>{const v=lo+t*(hi-lo);svg.append(this.svg('text',{x:x(v),y:220,'text-anchor':'middle'},Number(v.toPrecision(4))));});
    series.forEach(([key,label,color],i)=>{
      let path='';kde.x.forEach((v,j)=>{path+=(j?'L':'M')+x(v)+','+y(kde.curvas[key][j])+' ';});
      const line=this.svg('path',{d:path,fill:'none',stroke:color,'stroke-width':this.choice===key?3:2,'stroke-dasharray':['none','7,3','3,3'][i]});
      line.append(this.svg('title',{},label));svg.append(line);
    });
    svg.append(this.svg('text',{x:65,y:24},'Densidad'),this.svg('text',{x:370,y:248,'text-anchor':'middle'},this.column+' · unidades actuales'));
    const legend=this.node('div',null,'f3-kde-legend');
    series.forEach(([key,label,color],i)=>{
      const item=this.node('span',label),swatch=this.node('i');
      swatch.style.borderTop='3px '+(i?'dashed':'solid')+' '+color;item.prepend(swatch);legend.append(item);
    });
    box.append(legend,svg);
    const stats=this.node('div',null,'f3-kde-stats');
    series.forEach(([key,label,color])=>{
      const d=kde.estadisticas[key],original=kde.estadisticas.original.desviacion;
      const change=original?100*(d.desviacion-original)/original:0;
      const item=this.node('span',label+': desv. '+d.desviacion.toFixed(3)+(key==='original'?'':' ('+(change>0?'+':'')+change.toFixed(1)+'%)'));
      item.style.color=color;stats.append(item);
    });
    box.append(stats,this.node('p',kde.faltantes+' nulos · '+kde.observados+' valores observados. Misma rejilla y suavizado en las tres curvas.','f1-note'));
    if(!kde.faltantes)box.append(this.node('p','No hay nulos: las tres curvas coinciden.'));
    else if(this.choice==='excluir_nulos')box.append(this.node('p','Excluir nulos conserva la distribución de los valores observados, pero elimina filas completas.'));
    return box;
  }
  missingComparison(before,after) {
    const box=this.node('section',null,'f3-card f3-chart');
    box.append(this.node('h3','Datos nulos · dónde están y qué cambia'));
    const original=before.graficos?.[this.column],result=after?.graficos?.[this.column];
    if(original){
      const bands=this.node('div',null,'f3-missing-map');
      [['Antes',null],...(after?[['Después',result]]:[])].forEach(([name,g])=>{
        const row=this.node('div');row.append(this.node('strong',name));
        const track=this.node('div',null,'f3-coverage-band');
        const map=new Map((g?.puntos||[]).map(p=>[p.x,p]));
        original.puntos.forEach(p=>{
          const q=name==='Antes'?p:map.get(p.x);
          const n=p.total||1,available=Math.min(p.disponibles,q?.disponibles||0)/n*100;
          const filled=Math.max(0,(q?.disponibles||0)-p.disponibles)/n*100;
          const missing=(q?Math.max(0,q.total-q.disponibles):0)/n*100;
          const b=this.button('',()=>this.action('ventana',{fila:p.fila}));b.disabled=this.busy||!p.fila;
          b.style.background=p.total?'linear-gradient(to top,#c8e9e4 0% '+available+'%,#9766c2 '+available+'% '+(available+filled)+'%,#f3d5a1 '+(available+filled)+'% '+(available+filled+missing)+'%,#d8dee8 '+(available+filled+missing)+'% 100%)':'#d8dee8';
          b.title=p.x+' · '+(q?.disponibles||0)+' disponibles · '+(q?Math.max(0,q.total-q.disponibles):0)+' nulos · pulsa para ampliar';
          b.setAttribute('aria-label',name+' · '+p.x+' · ampliar registros');track.append(b);
        });
        row.append(track);bands.append(row);
      });box.append(bands);
    }
    box.append(this.node('p','Verde: original disponible · Ámbar: nulo · Morado: completado · Gris: excluido o sin registros. Pulsa un periodo para ampliar.','f1-note'));
    const records=this.missingWindow||this.preview?.ventana||before.ventanas?.[this.column]||[];
    if(!records.length){box.append(this.node('p','No hay registros para ampliar.'));return box;}
    box.append(this.node('h4','Vista ampliada · mediciones individuales'+(records[0].estacion?' · estación '+records[0].estacion:'')));
    const nums=records.flatMap(p=>[p.antes,p.despues]).filter(v=>typeof v==='number'),lo=Math.min(0,...nums),hi=Math.max(1,...nums);
    const y=v=>160-(v-lo)/(hi-lo)*115,x=i=>55+i*620/Math.max(1,records.length-1);
    const svg=this.svg('svg',{viewBox:'0 0 720 220',role:'img','aria-label':'Registros originales y valores completados de '+this.column});
    [lo,(lo+hi)/2,hi].forEach(v=>svg.append(this.svg('line',{x1:50,x2:690,y1:y(v),y2:y(v),stroke:'#dbe3ef'}),this.svg('text',{x:44,y:y(v)+4,'text-anchor':'end'},Number(v.toPrecision(4)))));
    ['antes',...(after?['despues']:[])].forEach(key=>{
      let path='',connected=false;
      records.forEach((p,i)=>{const v=p[key];if(typeof v!=='number'){connected=false;return;}path+=(connected?'L':'M')+x(i)+','+y(v)+' ';connected=true;});
      svg.append(this.svg('path',{d:path,fill:'none',stroke:key==='antes'?'#137c87':'#2866d6','stroke-width':1.5,'stroke-dasharray':key==='despues'?'5,3':'none'}));
    });
    records.forEach((p,i)=>{
      const value=after?p.despues:p.antes;
      if(typeof value==='number'){
        const dot=this.svg('circle',{cx:x(i),cy:y(value),r:p.imputado?5:3,fill:p.imputado?'#9766c2':'#137c87',tabindex:0});
        dot.append(this.svg('title',{},'Fila '+p.fila+' · '+(p.fecha||'Sin fecha')+' · '+value+(p.imputado?' · imputado':'')));svg.append(dot);
      }else {const label=this.svg('text',{x:x(i),y:180,'text-anchor':'middle'},p.eliminado?'×':value===null?'∅':String(value).slice(0,8));label.append(this.svg('title',{},'Fila '+p.fila+' · '+(value??'Nulo')));svg.append(label);}
    });
    [...new Set([0,Math.floor((records.length-1)/2),records.length-1])].forEach(i=>svg.append(this.svg('text',{x:x(i),y:208,'text-anchor':'middle'},'Fila '+records[i].fila)));
    box.append(svg,this.node('p','Hasta 31 registros cercanos, dentro de la misma estación cuando existe. El eje conserva sus posiciones: ∅ = nulo; × = fila excluida. No se unen líneas a través de huecos.','f1-note'));
    return box;
  }
  scaleComparison(before,after) {
    const box=this.node('section',null,'f3-scale-comparison');
    box.append(this.node('h3','Compara las variables de tu investigación'));
    if(!this.scaleColumns.length){box.append(this.node('p','Selecciona al menos una medida del panel izquierdo.'));return box;}
    const colors=['#137c87','#2866d6','#b96d21','#9366bc','#ba4265','#51913c'];
    const grid=this.node('div',null,'f3-scale-grid');
    [['Antes · escalas actuales',before,false],['Después · '+(this.choice==='normalizar'?'escala 0–1':'unidades originales'),after,this.choice==='normalizar']].forEach(([title,data,normalized])=>{
      const card=this.node('article',null,'f3-card');
      card.append(this.node('h3',title));
      if(!data){card.append(this.node('p','Selecciona «Normalizar entre 0 y 1» para calcular la comparación.'));grid.append(card);return;}
      const series=this.scaleColumns.map((c,i)=>({column:c,color:colors[i%colors.length],graph:data.graficos?.[c]})).filter(s=>s.graph);
      const labels=[...new Set(series.flatMap(s=>s.graph.puntos.map(p=>p.x)))].sort((a,b)=>series[0]?.graph.temporal?a.localeCompare(b):Number(a.replace('Bloque ',''))-Number(b.replace('Bloque ','')));
      const values=series.flatMap(s=>s.graph.puntos.filter(p=>p.valor!==null).map(p=>p.valor));
      const low=normalized?0:Math.min(0,...values),high=normalized?1:Math.max(1,...values);
      const x=i=>52+(labels.length===1?310:i*620/Math.max(1,labels.length-1)),y=v=>165-(v-low)/(high-low)*125;
      const svg=this.svg('svg',{viewBox:'0 0 720 215',role:'img','aria-label':title+' de '+this.scaleColumns.join(', ')});
      [low,(low+high)/2,high].forEach(v=>svg.append(this.svg('line',{x1:52,x2:680,y1:y(v),y2:y(v),stroke:'#dbe3ef'}),this.svg('text',{x:46,y:y(v)+4,'text-anchor':'end'},Number(v.toPrecision(4)))));
      series.forEach(s=>{
        const points=new Map(s.graph.puntos.map(p=>[p.x,p]));let path='',connected=false;
        labels.forEach((label,i)=>{
          const p=points.get(label);if(!p||p.valor===null){connected=false;return;}
          path+=(connected?'L':'M')+x(i)+','+y(p.valor)+' ';connected=true;
          const dot=this.svg('circle',{cx:x(i),cy:y(p.valor),r:3,fill:s.color,tabindex:0});
          dot.append(this.svg('title',{},s.column+' · '+label+': '+p.valor.toFixed(4)));svg.append(dot);
        });
        svg.append(this.svg('path',{d:path,fill:'none',stroke:s.color,'stroke-width':2}));
      });
      [...new Set([0,Math.floor((labels.length-1)/2),labels.length-1])].filter(i=>i>=0).forEach(i=>svg.append(this.svg('text',{x:x(i),y:191,'text-anchor':'middle'},labels[i])));
      card.append(svg);
      const legend=this.node('div',null,'f3-scale-legend');
      series.forEach(s=>{const label=this.node('span',s.column);label.style.color=s.color;legend.append(label);});
      card.append(legend);grid.append(card);
    });
    box.append(grid);
    return box;
  }
  render() {
    const s=this.session;if(!s)return;
    const scroll=this.host.querySelector('.f3-content')?.scrollTop||0;
    this.onState(s);this.host.replaceChildren();this.host.classList.add('phase1-host','f3-host');
    const intro=this.node('div',null,'f1-intro'),strip=this.node('nav',null,'f1-phase-strip');
    strip.setAttribute('aria-label','Fases del ciclo PPDAC');
    ['Problema','Plan','Datos','Análisis','Conclusión'].forEach((label,i)=>{
      const item=this.node('span');item.append(this.node('b',String(i+1)),document.createTextNode(label));
      if(i===2)item.setAttribute('aria-current','step');strip.append(item);
    });
    intro.append(strip,this.node('h3','Aplica tu plan de preparación'),this.node('p','Selecciona una variable, revisa el resultado y confirma cada tratamiento.'));
    const layout=this.node('div',null,'f1-layout f3-layout'),aside=this.node('aside',null,'f1-panel f3-variables'),content=this.node('section',null,'f1-panel f3-content');
    aside.append(this.node('h3','Variables de tu plan'),this.node('p',this.step==='escalas'?'Escoge las medidas que compararás. Otro clic las quita.':'Elige la variable que vas a preparar.','f1-note'));
    const chips=this.node('div',null,'f3-options f3-variable-chips');
    s.variables.forEach(c=>{
      const b=this.button(c,()=>{
        if(this.step==='escalas'){
          this.scaleColumns=this.scaleColumns.includes(c)?this.scaleColumns.filter(v=>v!==c):[...this.scaleColumns,c];
          this.preview=null;
          if(this.scaleColumns.length){this.choice=this.choice||'normalizar';this.action('previsualizar');}else this.render();
        }else{this.column=c;this.choice=null;this.preview=null;this.missingWindow=null;this.render();}
      });
      b.disabled=this.busy||(this.step==='escalas'&&!s.medidas.includes(c));
      b.setAttribute('aria-pressed',String(this.step==='escalas'?this.scaleColumns.includes(c):c===this.column));chips.append(b);
    });
    aside.append(chips);
    const info=this.node('div',null,'f3-variable-info');
    if(this.step==='escalas')info.append(this.node('h3',this.scaleColumns.join(' · ')||'Sin medidas seleccionadas'),this.node('p','La normalización se calcula por separado para cada medida.'),this.node('p','Las columnas de fecha se usan para el eje temporal y conservan sus valores.'));
    else info.append(this.node('h3',this.column),this.node('p',s.datos.numericas.includes(this.column)?'Medida numérica':'Variable de contexto'),
      this.node('p',s.datos.nulos[this.column]+' valores nulos de '+s.datos.filas.toLocaleString('es-PE')+' registros.'));
    aside.append(info);
    const plan=document.createElement('details');plan.open=true;plan.append(this.node('summary','Tu plan confirmado'));
    s.plan.pasos.filter(p=>this.step==='escalas'?p.variables.some(c=>this.scaleColumns.includes(c)):p.variables.includes(this.column)).forEach(p=>plan.append(this.node('p',p.accion)));
    aside.append(plan);layout.append(aside,content);this.host.append(intro,layout);
    const main=this.node('section',null,'f3-main');
    const nav=this.node('div',null,'f3-options');
    [['nulos','1 · Datos nulos'],['atipicos','2 · Valores atípicos'],['escalas','3 · Escalas']].forEach(([id,label])=>{
      const b=this.button(label,()=>{this.step=id;this.choice=null;this.preview=null;this.missingWindow=null;if(id==='escalas'&&this.scaleColumns.length){this.choice='normalizar';this.action('previsualizar');}else this.render();});b.setAttribute('aria-pressed',String(this.step===id));nav.append(b);
    });main.append(nav);
    const questions={nulos:'¿Qué harás con los datos nulos de ',atipicos:'¿Cómo tratarás los posibles valores atípicos de ',escalas:'¿Qué escala necesitas para analizar '};
    const heading=this.node('div',null,'f3-question-row');
    heading.append(this.node('h2',this.step==='escalas'?'¿Cómo se comparan '+(this.scaleColumns.join(', ')||'tus variables')+' en una misma escala?':questions[this.step]+this.column+'?'));
    const names=['Autónomo','Orientar','Dirigir','Prescribir'];
    const support=this.node('div',null,'f3-support-tools');
    support.append(this.node('strong','Apoyo '+s.nivel+' · '+names[s.nivel-1],'f2-support-badge'));
    if(s.nivel<4){
      support.append(this.button('Necesito apoyo',()=>this.action('ayuda')));
      support.append(this.button('Saltar a Prescribir',()=>this.action('prescribir')));
    }
    heading.append(support);main.append(heading);
    const hints={
      nulos:['Elige una alternativa y comprueba sus consecuencias.','¿Los huecos se concentran en algún periodo? Completarlos puede cambiar la evolución.','Compara la pérdida de filas al excluir con el supuesto de usar una mediana constante. Revisa los registros antes de aplicar.','Propuesta prudente: conservar los nulos mientras investigas su distribución. No rellenes automáticamente con cero.'],
      atipicos:['Revisa las mediciones antes de decidir. Un valor extremo no confirma un error.','Comprueba si el valor coincide con un episodio real y qué ocurre en sus fechas cercanas.','Compara conservar con limitar: limitar modifica mediciones válidas y puede borrar picos relevantes para tu pregunta.','Propuesta prudente: conservar e investigar los extremos. Aplica un recorte solo si puedes justificarlo.'],
      escalas:['Decide según el análisis que necesitas.','¿Compararás magnitudes reales o la forma de varias curvas?','Conserva unidades para interpretar concentraciones; normaliza cada variable para comparar patrones en una escala común.','Para comparar patrones entre varias variables, normaliza cada una de 0 a 1. Si necesitas magnitudes, conserva las unidades.']
    };
    if(s.nivel>1)main.append(this.node('p',hints[this.step][s.nivel-1],'f3-hint'));
    const options=this.node('div',null,'f3-options');
    this.options().forEach(([id,text,description])=>{
      if(!s.datos.numericas.includes(this.column)&&['media','mediana','normalizar','limitar_iqr','excluir_atipicos'].includes(id))return;
      const b=this.button(text,()=>{this.choice=id;this.preview=null;this.missingWindow=null;this.action('previsualizar');});b.setAttribute('aria-pressed',String(this.choice===id));b.title=description;options.append(b);
    });main.append(options);
    const description=this.choice?this.options().find(o=>o[0]===this.choice)[2]:'Selecciona una alternativa para ver su efecto en el gráfico.';
    const status=this.node('div',null,'f3-choice-status');
    status.append(this.node('p',this.busy?'Calculando cambios…':description));
    if(this.error&&this.choice)status.append(this.button('Reintentar comparación',()=>this.action('previsualizar')));
    main.append(status);content.append(main);
    if(this.notice)content.append(this.node('p',this.notice,'f3-hint'));
    if(this.error)content.append(this.node('p',this.error,'f3-error'));
    if(this.step==='escalas')content.append(this.scaleComparison(s.datos,this.preview?.datos));
    else if(this.step==='atipicos')content.append(this.outlierScatter(s.datos,this.preview?.datos));
    else {
      const kde=this.kdeComparison(s.datos);
      if(kde){
        content.append(kde);
        const location=this.node('details',null,'f3-location-details');
        location.open=!!this.locationOpen;
        location.addEventListener('toggle',()=>{if(location.isConnected)this.locationOpen=location.open;});
        location.append(this.node('summary','Ver dónde están los huecos y los valores completados'),this.missingComparison(s.datos,this.preview?.datos));
        content.append(location);
      }else content.append(this.missingComparison(s.datos,this.preview?.datos));
    }
    if(this.preview) {
      const p=this.preview,box=this.node('section',null,'f3-card f3-active-preview');
      box.append(this.node('h3','Vista previa · todavía no aplicada'),this.node('p',p.cambios+' registros afectados · '+s.datos.filas+' → '+p.datos.filas+' filas · Nulos: '+(p.variables||[this.column]).reduce((n,c)=>n+s.datos.nulos[c],0)+' → '+(p.variables||[this.column]).reduce((n,c)=>n+p.datos.nulos[c],0)));
      if(!p.cambios)box.append(this.node('p',this.choice==='conservar'?'Conservar mantiene los datos sin cambios.':'No hay registros que cambien con esta opción.'));
      box.append(this.button('Aplicar tratamiento',()=>this.action('aplicar')));
      content.append(box);
    }
    const current=this.node('section',null,'f3-card f3-data-tools');
    if(s.historial.length){current.append(this.button('Deshacer último tratamiento',()=>this.action('deshacer')));s.historial.forEach(h=>current.append(this.node('p',h.columna+' · '+h.accion+' · '+h.cambios+' cambios · Apoyo '+h.apoyo)));}
    current.append(this.button('Descargar copia preparada',()=>this.download()));content.append(current);
    if(this.focusResult&&this.preview) {
      const target=content.querySelector(':scope > .f3-chart, :scope > .f3-scale-comparison')||content.querySelector('.f3-active-preview');
      content.scrollTop=Math.max(0,target.offsetTop-content.offsetTop-main.offsetHeight-12);
      this.focusResult=false;
    } else content.scrollTop=scroll;
  }
  async download() {
    try{
      const response=await fetch((window.SIGAD_API_BASE??(location.port==='5000'?'':'http://127.0.0.1:5000'))+'/api/fase3/descargar',{headers:{'X-SiGAD-Phase3':this.session.sesion}});
      if(!response.ok)throw Error('No se pudo descargar la copia.');
      const url=URL.createObjectURL(await response.blob()),a=this.node('a');a.href=url;a.download='datos_preparados.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){this.error=e.message;this.render();}
  }
};
