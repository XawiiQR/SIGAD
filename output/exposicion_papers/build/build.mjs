import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const dir=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(await fs.readFile(path.join(dir,'slides.json'),'utf8'));
const p=Presentation.create({slideSize:{width:1280,height:720}});
const C={ink:'#142B3B',muted:'#4C6575',paper:'#F7F8F5',blue:'#176B87',teal:'#187F79',orange:'#B8662B',purple:'#72539A'};
const font='Arial';
function text(sl,str,x,y,w,h,size=25,color=C.ink,bold=false){let a=sl.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});a.text=str;a.text.style={typeface:font,fontSize:size,color,bold};return a;}
function rect(sl,x,y,w,h,color){return sl.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:color,line:{fill:'none',width:0}});}
async function pic(sl,name,x,y,w,h){let b=await fs.readFile(path.join(dir,name+'.png'));sl.images.add({blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:name,fit:'contain',position:{left:x,top:y,width:w,height:h}});}
const wide=new Set(['light_arch','light_ui','wait_ui','wait_results','gu_workflows']);
for(let i=0;i<data.length;i++){
 let d=data[i],s=p.slides.add();let accent=d.section.startsWith('02')?C.teal:d.section.startsWith('03')?C.orange:d.section.startsWith('04')?C.purple:C.blue;s.background.fill=C.paper;
 if(d.kind==='cover'){
 s.background.fill=C.ink;rect(s,70,75,105,7,'#48B8AE');text(s,'REVISIÓN DE LITERATURA PARA SiGAD',70,111,1100,40,20,'#87D6CB',true);text(s,d.title,70,214,1110,215,52,'#FFFFFF',true);text(s,d.items.join('\n'),73,485,1060,100,28,'#C9D9DD');text(s,'Kazemitabaar · LightVA · WaitGPT · Gu',73,643,1050,35,19,'#8FB1BD');
 }else{
 rect(s,60,48,44,5,accent);text(s,d.section.toUpperCase(),60,69,1120,30,17,accent,true);text(s,d.title,60,116,1160,110,37,C.ink,true);
 if(d.kind==='table'){
 const vals=[['Trabajo','Aporte a la interacción','Uso propuesto en SiGAD'],['Kazemitabaar','Supuestos y pasos editables','Puntos de revisión por tarea'],['LightVA','Planificación, ejecución y control','Responsabilidades separadas'],['WaitGPT','Operaciones y estados visibles','Antes y después del tratamiento'],['Gu','Verificación con datos y procedimientos','Evidencia y explicación del estudiante']];
 let t=s.tables.add({rows:5,columns:3,left:60,top:260,width:1160,height:340,columnWidths:[210,450,500],values:vals});
 t.borders.assign({fill:'#D2DDDF',width:1,style:'solid'});
 for(let r=0;r<5;r++)for(let c=0;c<3;c++){let cell=t.getCell(r,c);cell.fill=r===0?C.ink:(r%2?'#FFFFFF':'#ECF1F0');cell.text.style={typeface:font,fontSize:23,color:r===0?'#FFFFFF':C.ink,bold:r===0};}
 }else if(d.image && wide.has(d.image)){
 const ui=d.image.endsWith('_ui'); const ih=ui?350:310; const cy=ui?585:541; const by=ui?620:596; await pic(s,d.image,65,227,1150,ih);text(s,d.caption,65,cy,1150,24,14,C.muted);
 const n=d.items.length,gap=26,w=(1150-gap*(n-1))/n;
 d.items.forEach((v,j)=>{if(!ui)rect(s,65+j*(w+gap),by-14,28,4,accent);text(s,v,65+j*(w+gap),by,w,ui?40:75,ui?19:21,C.ink);});
 }else if(d.image){
 const portrait=d.image.startsWith('kaz_');const iw=portrait?485:670;const ix=1280-60-iw;const tw=ix-95;
 d.items.forEach((v,j)=>{const step=portrait?106:113;text(s,String(j+1).padStart(2,'0'),60,250+j*step,44,35,19,accent,true);text(s,v,112,246+j*step,tw-52,step-14,25,C.ink);});
 rect(s,ix-8,228,iw+16,405,'#FFFFFF');await pic(s,d.image,ix,233,iw,391);text(s,d.caption,ix,643,iw,35,14,C.muted);
 }else{
 const n=d.items.length;const step=n===3?127:105;
 d.items.forEach((v,j)=>{const y=250+j*step;text(s,String(j+1).padStart(2,'0'),63,y+1,50,35,20,accent,true);text(s,v,137,y,1055,step-18,28,C.ink);});
 }
 text(s,'SiGAD · Análisis de cuatro artículos',60,686,950,20,13,C.muted);text(s,String(i+1).padStart(2,'0'),1160,684,60,22,15,accent,true);
 }
 s.speakerNotes.text=d.notes+'\n\n'+(d.caption?'Figura reproducida del artículo original: '+d.caption+'.':'');
}
await fs.mkdir(path.join(dir,'renders'),{recursive:true});
await (await PresentationFile.exportPptx(p)).save(path.join(dir,'candidate.pptx'));
console.log('PPTX creado',data.length);
for(let i=0;i<p.slides.items.length;i++){
 const blob=await p.export({slide:p.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(dir,'renders',`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));
 console.log('render',i+1);
}
const {finalizePresentation}=await import('/Users/xawii/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations/container_tools/artifact_tool_utils.mjs');
const skill='/Users/xawii/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
const result=await finalizePresentation({workspaceDir:path.dirname(dir),candidatePath:path.join(dir,'candidate.pptx'),finalPath:path.join(dir,'..','entrega','Exposicion_4_papers_SiGAD.pptx'),pythonExecutable:'/Users/xawii/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','35'],requiredNativeTableOwnerSlides:[35],fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,receiptPath:path.join(dir,'validation_v3.json')});
console.log(JSON.stringify(result));
