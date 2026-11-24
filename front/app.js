// Usa Flask incluso si el archivo se abre desde Live Server, VS Code o file://.
const API_BASE = window.SIGAD_API_BASE ?? (window.location.port === '5000' ? '' : 'http://127.0.0.1:5000');
const state = { level: 1, history: [], phase1Objective: '', phase2Plan: null };
const $ = (selector) => document.querySelector(selector);
const conversation = $('#conversation');
const interaction = $('#interaction');
const seguimiento = new SigadSeguimiento($('#abrir-seguimiento'));

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.error || 'No se pudo completar la solicitud.'); error.status = response.status; throw error; }
  return data;
}

function addMessage(title, text, kind = 'system') {
  const card = document.createElement('article');
  card.className = `message ${kind}`;
  card.innerHTML = `<h3>${title}</h3><p></p>`;
  card.querySelector('p').textContent = text;
  conversation.append(card);
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function addHistory(label) {
  seguimiento.evento(label);
  state.history.push({ time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), label });
  localStorage.setItem('fase1_historial', JSON.stringify(state.history));
  $('#history').innerHTML = state.history.map((item) => `<li><b>${item.time}</b> — ${item.label}</li>`).join('');
}

function setLevel(level) {
  state.level = level;
  document.querySelectorAll('.levels li').forEach((item) => item.classList.toggle('active', Number(item.dataset.level) === level));
}

function setScreen(title, sectionTitle, description) {
  window.phase2Controller?.destroy();
  window.phase1Controller?.resize?.disconnect();
  window.phase1Controller?.stopClock?.();
  conversation.classList.remove('phase1-host','f3-host');
  $('#timer').hidden = false;
  conversation.innerHTML = '';
  interaction.innerHTML = '';
  $('.sidebar h1').textContent = sectionTitle;
  $('.sidebar-copy').textContent = description;
  $('.topbar h2').textContent = title;
  document.title = `${sectionTitle} | Data Tutor`;
}

async function startPhase2() {
  setScreen('Planifica la preparación de tus datos', 'Plan', 'Define y justifica cómo preparar los datos para responder tu pregunta.');
  seguimiento.entrar(2);
  $('#timer').hidden = true;
  $('#session-status').textContent = 'Cargando plan…';
  window.phase2Controller = new SigadPhase2(conversation, interaction, api, {
    onState: session => {
      seguimiento.observar(2, session);
      setLevel(session.motor.nivel);
      $('#session-status').textContent = session.completada ? 'Plan confirmado' : session.motor.nombre_nivel;
    },
    onHistory: addHistory,
    onData: startPhase3,
    onFinish: plan => {
      state.phase2Plan = plan;
      sessionStorage.setItem('sigad_fase2_plan', JSON.stringify(plan));
    },
    onBack: () => restartPhase1().catch(error => addMessage('No se pudo abrir la fase 1', error.message, 'warning')),
  });
  try { await window.phase2Controller.mount(); }
  catch (error) {
    addMessage('No se pudo iniciar la fase 2', error.message, 'warning');
    const retry = document.createElement('button'); retry.textContent = 'Reintentar';
    retry.addEventListener('click', startPhase2); interaction.append(retry);
    const back = document.createElement('button'); back.textContent = 'Volver a la fase 1';
    back.addEventListener('click', restartPhase1); interaction.append(back);
  }
}

async function startPhase3(origin) {
  setScreen('Prepara tus datos para el análisis', 'Datos', 'Decide, comprueba y aplica la preparación de tus datos.');
  seguimiento.entrar(3);
  $('#timer').hidden=true;
  window.phase3Controller=new SigadPhase3(conversation,api,origin,s=>{
    seguimiento.observar(3, s);
    setLevel(s.nivel);$('#session-status').textContent='Preparación · '+s.historial.length+' tratamientos';
  });
  try{await window.phase3Controller.mount();}
  catch(error){addMessage('No se pudo abrir la fase 3',error.message,'warning');interaction.append(Object.assign(document.createElement('button'),{textContent:'Volver al plan',onclick:startPhase2}));}
}

async function restartPhase1() {
  state.phase1Objective = '';
  state.phase2Plan = null;
  sessionStorage.removeItem('sigad_fase2_plan');
  setScreen('Explora tus datos y define una pregunta', 'Problema', 'Observa los datos, descubre un patrón y formula una pregunta que puedas analizar.');
  seguimiento.entrar(1);
  $('#timer').hidden = true;
  $('#session-status').textContent = 'Cargando exploración…';
  window.phase1Controller = new SigadPhase1(conversation, api, {
    onState: (session) => {
      seguimiento.observar(1, session, window.phase1Controller.perfil);
      setLevel(session.motor.nivel);
      $('#session-status').textContent = session.completada ? 'Pregunta justificada' : session.motor.nombre_nivel;
    },
    onHistory: addHistory,
    onFinish: (objetivo) => {
      state.phase1Objective = objetivo.pregunta;
      state.phase1Context = objetivo;
      sessionStorage.setItem('sigad_fase1_objetivo', JSON.stringify(objetivo));
      startPhase2();
    },
  });
  await window.phase1Controller.mount();
}

async function init() {
  state.history = JSON.parse(localStorage.getItem('fase1_historial') || '[]');
  $('#history').innerHTML = state.history.map((item) => `<li><b>${item.time}</b> — ${item.label}</li>`).join('');
  $('#history-toggle').addEventListener('click', () => $('#history').classList.toggle('is-hidden'));
  try {
    await restartPhase1();
  } catch (error) { $('#session-status').textContent = 'Sin conexión'; addMessage('No se pudo iniciar', `${error.message}\nInicia Flask con: python3 app.py`, 'warning'); }
}

init();
