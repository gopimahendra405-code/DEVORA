const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let materials = [];
let current = null;
let cardIndex = 0;

async function api(url, options={}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

function setView(view) {
  $$(".view").forEach(v => v.classList.toggle("active", v.id === view));
  $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  const titles = {dashboard:"Good study session 👋",library:"Your study library",learn:"Active recall mode",progress:"Your learning progress"};
  $("#pageTitle").textContent = titles[view] || titles.dashboard;
  window.scrollTo({top:0,behavior:"smooth"});
}

$$("[data-view]").forEach(btn => btn.addEventListener("click", () => setView(btn.dataset.view)));

async function loadProgress() {
  const p = await api("/api/progress");
  $("#streak").textContent = p.streak;
  $("#xp").textContent = p.xp;
  $("#dashboardXp").textContent = p.xp;
  $("#bigXp").textContent = p.xp;
  $("#pStreak").textContent = p.streak;
  $("#pCards").textContent = p.cards_reviewed;
  $("#pQuizzes").textContent = p.quizzes_completed;
  const goal = Math.min(p.xp % 100, 20);
  $("#goalText").textContent = `${goal} / 20 XP`;
  $("#goalBar").style.width = `${goal/20*100}%`;
  const level = Math.floor(p.xp / 100);
  $("#levelName").textContent = ["Starter Scholar","Focused Learner","Recall Builder","Knowledge Navigator","Study Master"][Math.min(level,4)];
  $("#levelText").textContent = `${p.xp % 100} / 100 XP toward the next level.`;
  $("#levelBar").style.width = `${p.xp % 100}%`;
}

function materialCard(m) {
  return `<article class="material" data-id="${m.id}">
    <div class="doc">▱</div><h3>${escapeHtml(m.title)}</h3>
    <p>${escapeHtml(m.filename)} · ${new Date(m.uploaded_at).toLocaleDateString()}</p>
    <button class="open-btn">Open study set →</button>
  </article>`;
}

function bindMaterialCards() {
  $$(".material").forEach(el => el.addEventListener("click", () => openMaterial(el.dataset.id)));
}

async function loadMaterials() {
  materials = await api("/api/materials");
  $("#materialCount").textContent = materials.length;
  $("#recentMaterials").innerHTML = materials.slice(0,4).map(materialCard).join("") || emptyMaterials();
  $("#libraryGrid").innerHTML = materials.map(materialCard).join("") || emptyMaterials();
  bindMaterialCards();

  let cards = 0, quizzes = 0;
  for (const m of materials.slice(0, 12)) {
    try {
      const full = await api(`/api/materials/${m.id}`);
      cards += full.flashcards.length;
      quizzes += full.quiz.length;
    } catch {}
  }
  $("#cardCount").textContent = cards;
  $("#quizCount").textContent = quizzes;
}

function emptyMaterials() {
  return `<div class="empty"><div>＋</div><h3>No study sets yet</h3><p>Upload your first PDF or notes from the Dashboard.</p></div>`;
}

async function upload(file) {
  const status = $("#uploadStatus");
  status.textContent = "Reading material and building your study set…";
  const fd = new FormData();
  fd.append("file", file);
  try {
    const result = await api("/api/materials", {method:"POST", body:fd});
    status.textContent = "✓ Study set created. Open it from My Materials.";
    await loadMaterials();
    await loadProgress();
    openMaterial(result.id);
  } catch (e) {
    status.textContent = `Error: ${e.message}`;
  }
}

$("#fileInput").addEventListener("change", e => {
  if (e.target.files[0]) upload(e.target.files[0]);
});

async function openMaterial(id) {
  try {
    current = await api(`/api/materials/${id}`);
    cardIndex = 0;
    $("#learnEmpty").classList.add("hidden");
    $("#learnContent").classList.remove("hidden");
    $("#learnTitle").textContent = current.title;
    $("#summary").textContent = current.summary;
    $("#concepts").innerHTML = current.concepts.map(c => `<span class="chip">${escapeHtml(c)}</span>`).join("");
    renderCard();
    renderQuiz();
    setView("learn");
  } catch(e) { alert(e.message); }
}

function renderCard() {
  const cards = current?.flashcards || [];
  if (!cards.length) return;
  const c = cards[cardIndex];
  $("#cardNumber").textContent = `${cardIndex+1} / ${cards.length}`;
  $("#cardFront").textContent = c.front;
  $("#cardBack").textContent = c.back;
  $("#cardBack").classList.add("hidden");
  $("#revealBtn").textContent = "Reveal answer";
}

$("#revealBtn").addEventListener("click", () => {
  const back = $("#cardBack");
  const hidden = back.classList.toggle("hidden");
  $("#revealBtn").textContent = hidden ? "Reveal answer" : "Hide answer";
});

$("#nextCard").addEventListener("click", () => {
  if (!current) return;
  cardIndex = (cardIndex + 1) % current.flashcards.length;
  renderCard();
});
$("#prevCard").addEventListener("click", () => {
  if (!current) return;
  cardIndex = (cardIndex - 1 + current.flashcards.length) % current.flashcards.length;
  renderCard();
});
$("#knowBtn").addEventListener("click", async () => {
  await api("/api/progress", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({xp:5,cards_reviewed:1})});
  await loadProgress();
  cardIndex = (cardIndex + 1) % current.flashcards.length;
  renderCard();
});

function renderQuiz() {
  $("#quiz").innerHTML = (current.quiz || []).map(q => `
    <div class="quiz-q" data-q="${q.id}">
      <p>${escapeHtml(q.question)}</p>
      ${q.options.map(o => `<button class="option" data-answer="${escapeAttr(o)}">${escapeHtml(o)}</button>`).join("")}
    </div>`).join("") || "<p>No quiz available.</p>";

  $$(".quiz-q").forEach(qEl => {
    const q = current.quiz.find(x => String(x.id) === qEl.dataset.q);
    qEl.querySelectorAll(".option").forEach(btn => btn.addEventListener("click", async () => {
      qEl.querySelectorAll(".option").forEach(b => b.disabled = true);
      if (btn.dataset.answer === q.answer) {
        btn.classList.add("correct");
        await api("/api/progress", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({xp:10,quizzes_completed:1})});
      } else {
        btn.classList.add("wrong");
        [...qEl.querySelectorAll(".option")].find(b => b.dataset.answer === q.answer)?.classList.add("correct");
      }
      await loadProgress();
    }));
  });
}

function escapeHtml(v) {
  return String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}
function escapeAttr(v){return escapeHtml(v).replace(/`/g,"&#096;")}

async function init() {
  try { await loadProgress(); await loadMaterials(); }
  catch(e) { console.error(e); }
}
init();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(()=>{});
