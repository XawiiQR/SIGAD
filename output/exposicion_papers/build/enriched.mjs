import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
import {finalizePresentation} from '/Users/xawii/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations/container_tools/artifact_tool_utils.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const papers=JSON.parse(await fs.readFile(path.join(dir,'enriched.json'),'utf8'));
const p=Presentation.create({slideSize:{width:1600,height:900}});
function tx(s,str,x,y,w,h,size=26,color='#142B3B',bold=false){let z=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});z.text=str;z.text.style={typeface:'Arial',fontSize:size,color,bold};}
function rect(s,x,y,w,h,fill){s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}});}
function base(a,n,title,notes){let s=p.slides.add();s.background.fill='#F7F8F5';rect(s,60,38,48,5,a.color);tx(s,a.label.toUpperCase(),60,60,1470,30,20,a.color,true);tx(s,title,60,105,1480,96,42,'#142B3B',true);tx(s,'Fuentes: PDF aportado, secciones indicadas en las notas del expositor.',60,872,1390,22,15,'#4C6575');tx(s,`${n}/8`,1480,872,65,22,16,a.color,true);s.speakerNotes.text=a.full+'\n\n'+notes+'\n\nLas aplicaciones a SiGAD son propuestas propias y requieren evaluación independiente.';return s;}
function group(s,heading,body,x,y,w,color,first=false){tx(s,heading,x,y,w,31,26,color,true);tx(s,body,x,y+39,w,first?110:137,26);}
for(let k=0;k<papers.length;k++){
 let a=papers[k];let s=base(a,k*2+1,a.title,a.notes1);
 a.intro.forEach(([h,b],i)=>group(s,h,b,60,211+i*155,670,a.color,true));
 let b=await fs.readFile(path.join(dir,a.image+'.png'));
 s.images.add({blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:a.caption,fit:'contain',position:{left:775,top:211,width:765,height:443}});
 tx(s,a.caption,775,666,765,24,17,'#4C6575');
 tx(s,'Cómo leer la figura',775,714,765,31,24,a.color,true);
 tx(s,a.figure_read,775,756,765,99,25);
 s=base(a,k*2+2,'Evaluación, hallazgos y discusión',a.notes2);
 a.left.forEach(([h,b],i)=>group(s,h,b,60,217+i*187,710,a.color));
 a.right.forEach(([h,b],i)=>group(s,h,b,825,217+i*187,715,a.color));
 rect(s,60,790,1480,66,'#E7EEEC');tx(s,a.sigad,76,801,1448,51,25,'#142B3B',true);
}
await fs.mkdir(path.join(dir,'enriched_renders'),{recursive:true});
await (await PresentationFile.exportPptx(p)).save(path.join(dir,'enriched_candidate.pptx'));
for(let i=0;i<8;i++){let b=await p.export({slide:p.slides.items[i],format:'png',scale:1});await fs.writeFile(path.join(dir,'enriched_renders',`slide-${i+1}.png`),new Uint8Array(await b.arrayBuffer()));}
const skill='/Users/xawii/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
console.log(await finalizePresentation({workspaceDir:path.dirname(dir),candidatePath:path.join(dir,'enriched_candidate.pptx'),finalPath:path.join(dir,'..','entrega','Exposicion_8_diapositivas_ampliada.pptx'),pythonExecutable:'/Users/xawii/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','15240000,8572500','--validate-heading-fit'],explicitTotalSlideCount:8,fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,receiptPath:path.join(dir,'enriched_validation_v2.json')}));
