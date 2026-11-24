import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const build = path.dirname(fileURLToPath(import.meta.url));
const workspace = path.resolve(build, '../..');
const skill = '/Users/xawii/.codex/plugins/cache/openai-primary-runtime/presentations/26.1105.12137/skills/presentations';
const runtime = '/Users/xawii/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const source = 'https://arxiv.org/html/2411.05651v2';
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const ink = '#342331', accent = '#9B3656', muted = '#65545D';

function text(slide, name, value, left, top, width, height, fontSize, color = ink, bold = false) {
  const shape = slide.shapes.add({ name, geometry: 'textbox', position: { left, top, width, height }, fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = value;
  shape.text.style = { typeface: 'Arial', fontSize, color, bold };
}
function page(title, note, section) {
  const slide = deck.slides.add();
  slide.background.fill = '#FFF8FA';
  const n = deck.slides.items.length;
  text(slide, 'Serie', 'PAPER 2  /  LIGHTVA', 58, 36, 1150, 30, 19, accent, true);
  if (title) text(slide, 'Título', title, 58, 80, 1160, 70, 47, ink, true);
  text(slide, 'Fuente', 'Zhao et al.  /  ' + section, 58, 662, 1030, 29, 17, muted);
  text(slide, 'Número', String(n).padStart(2, '0'), 1160, 662, 65, 29, 17, accent, true);
  slide.speakerNotes.text = note + '\n\nFuente: ' + source;
  return slide;
}
function group(slide, label, body, y, x = 58, w = 1150, size = 30) {
  text(slide, label, label, x, y, w, 35, 27, accent, true);
  text(slide, label + ' detalle', body, x, y + 41, w, 76, size);
}
async function figure(slide, basename, alt, left, top, width, height) {
  const data = await fs.readFile(path.join(build, '..', basename + '.png'));
  slide.images.add({ blob: data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength), contentType: 'image/png', alt, fit: 'contain', position: { left, top, width, height } });
}

let slide = page(null, 'LightVA se pronuncia «lait vi ei». Presenta la idea con una pregunta amplia y explica que el sistema recomienda tareas y produce visualizaciones para explorar sus resultados.', 'Introducción');
text(slide, 'Nombre', 'LightVA', 58, 160, 1120, 115, 98, accent, true);
text(slide, 'Título original', 'Lightweight Visual Analytics with LLM\nAgent-Based Task Planning and Execution', 64, 298, 1120, 116, 40, ink, true);
text(slide, 'Descripción', 'De un objetivo amplio a tareas de análisis y gráficos interactivos.', 64, 460, 1100, 80, 30, muted);

slide = page('Motivación, problema y objetivo', 'Motivación: el análisis visual cambia a medida que encontramos resultados. Problema: pasar de un objetivo amplio a una serie de tareas conectadas exige trabajo de planificación y conocimientos técnicos. Objetivo: facilitar ese recorrido con un agente que recomienda tareas, genera visualizaciones y permite al usuario seguir explorando.', 'Sección I');
group(slide, 'Motivación', 'Al explorar datos surgen preguntas nuevas. Cada una puede requerir otro método o gráfico.', 185);
group(slide, 'Problema', 'Ante un objetivo amplio, hay que decidir qué investigar primero y cómo conectar los resultados.', 330);
group(slide, 'Objetivo', 'Ayudar al usuario a convertir su objetivo en tareas concretas, ejecutarlas y explorar sus resultados.', 475);

slide = page('Modelo de interacción', 'Caso real: un experto del estudio usó el conjunto Auto MPG. Eligió una tarea inicial y examinó las propuestas de descomposición. Utilizó gráficos vinculados para explorar diferencias entre vehículos con distintos números de cilindros. La figura de la derecha muestra la interfaz de LightVA en otro caso del artículo, el análisis de eventos.', 'Secciones III, IV-B y VI-A');
text(slide, 'Caso', 'Caso del paper · Consumo de combustible', 58, 171, 1140, 49, 30, accent, true);
const steps = [
  ['01  Objetivo', 'Explorar qué se relaciona con la eficiencia de los autos.'],
  ['02  Tarea', 'LightVA propone tareas y el experto elige una.'],
  ['03  Exploración', 'El experto explora diferencias según el número de cilindros.'],
  ['04  Siguiente paso', 'Los hallazgos orientan nuevas tareas o subtareas.'],
];
steps.forEach(([h,b],i) => {
  const y = 229 + i * 99;
  text(slide,h,h,58,y,575,32,24,accent,true);
  text(slide,h+' detalle',b,58,y+33,575,64,25);
});
await figure(slide,'light_workflow','Figura 4 del paper con la interfaz de LightVA en el caso de eventos',650,235,570,305);
text(slide,'Pie de figura','Interfaz de LightVA en el caso de eventos · Fig. 4',650,552,570,46,18,muted);

slide = page('Módulos de LightVA', 'El planificador recibe el objetivo y el contexto del análisis. Propone tareas y, cuando corresponde, las descompone. El ejecutor produce los cálculos, gráficos y hallazgos. El controlador coordina las llamadas a ambos componentes y gestiona la continuación del flujo. La figura 3 reproduce el esquema del artículo.', 'Sección IV-A y Figura 3');
const modules = [
 ['Planificador','Recomienda tareas y divide una tarea compleja en subtareas.'],
 ['Ejecutor','Realiza el análisis y genera gráficos y hallazgos.'],
 ['Controlador','Coordina el flujo entre el planificador y el ejecutor.'],
];
modules.forEach(([h,b],i) => group(slide,h,b,166,58+i*388,350,24));
await figure(slide,'light_arch','Figura 3 del artículo: arquitectura de planificación y ejecución de LightVA',155,320,970,302);
text(slide,'Pie de figura','Flujo de planificación y ejecución del artículo',157,621,900,27,17,muted);

slide = page('Benchmark, línea base y evaluación', 'El artículo reúne tres tipos de evidencia: un caso de análisis de eventos, un estudio con dos expertos en analítica visual y un experto de dominio, y pruebas técnicas del modelo. Los expertos usaron datos de autos y ventas. En el apéndice B se comparan GPT-3.5-turbo y GPT-4-turbo. Tableau Ask Data aparece en la discusión como referencia de capacidades, sin un experimento comparativo de usuarios.', 'Secciones V–VII y apéndice B');
group(slide,'Benchmark técnico','El apéndice B compara GPT-3.5-turbo y GPT-4-turbo en tareas del sistema, con medidas de errores y tiempo.',169);
group(slide,'Línea base','Tableau Ask Data se discute como referencia. El estudio con expertos se realizó con LightVA.',322);
group(slide,'Evaluación','Los autores mostraron un caso de detección de eventos y observaron a tres expertos trabajando con datos de autos y ventas.',475);

slide = page('Conclusiones y trabajo futuro', 'Los autores presentan evidencia exploratoria de que LightVA reduce trabajo manual y facilita la exploración visual. Los comentarios de los expertos señalan la importancia de recomendar tareas pertinentes y explicar el plan. El estudio con tres expertos limita la generalización. La relación con SiGAD es una interpretación para la tesis: las tareas de LightVA organizan el análisis, mientras que una tarea de SiGAD permite observar una decisión del estudiante.', 'Secciones VI–VIII');
group(slide,'Conclusiones','El estudio sugiere que LightVA facilita la exploración y reduce parte del trabajo manual.',169);
group(slide,'Trabajo futuro','Ampliar el estudio con usuarios, incorporar conocimiento del dominio y detectar errores factuales.',322);
group(slide,'Relación con SiGAD','La estructura objetivo, tarea y resultado puede ayudar a definir qué decisión realiza el estudiante y cuándo necesita apoyo.',475);

const draft = path.join(build,'draft.pptx');
const final = path.join(workspace,'entrega','LightVA_Paper_2.pptx');
await (await PresentationFile.exportPptx(deck)).save(draft);
const { finalizePresentation } = await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
console.log(await finalizePresentation({
  workspaceDir: workspace,
  candidatePath: draft,
  finalPath: final,
  pythonExecutable: path.join(runtime,'python/bin/python3'),
  integrityValidatorPath: path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],
  explicitTotalSlideCount: 6,
  fontPolicy: {basis:'design',families:['Arial']},
  verifyArtifactToolImport:true,
  receiptPath:path.join(build,'validation.json')
}));
for (const [i,slide] of deck.slides.items.entries()) {
  const preview = await deck.export({slide,format:'png',scale:0.7});
  await fs.writeFile(path.join(build,'slide-'+(i+1)+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
