/* Client presentation. Reads only /api/present/<id>, which carries client-safe data. */
(() => {
  "use strict";
  const ID = document.body.dataset.presentation;
  const API = `/api/present/${ID}`;
  const app = document.getElementById("app");
  const [WELCOME, ABOUT, INTERESTS, TOPICS, QUESTIONS, FINDINGS, SOLUTIONS, RECAP, NEXT, CLOSING] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
  const LAST = CLOSING;
  const MONTHS = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου", "Αυγούστου",
    "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"];
  const svg = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const ICON = {
    right: svg('<path d="M5 12h14M13 6l6 6-6 6"/>'),
    left: svg('<path d="M19 12H5M11 6l-6 6 6 6"/>'),
    check: svg('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
    full: svg('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'),
    close: svg('<path d="M6 6l12 12M18 6L6 18"/>'),
    people: svg('<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20c.6-3.4 2.8-5.3 5.5-5.3s4.9 1.9 5.5 5.3"/><circle cx="17" cy="9" r="2.6"/><path d="M16 14.6c2.4.2 4 1.9 4.5 5.4"/>'),
    heart: svg('<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.5 2.5C19.5 15.4 12 20 12 20z"/><path d="M8.5 12h2l1-2 1.5 4 1-2h1.5"/>'),
    team: svg('<circle cx="12" cy="7" r="2.6"/><circle cx="5.5" cy="9.5" r="2"/><circle cx="18.5" cy="9.5" r="2"/><path d="M7.5 20c0-3.2 2-5.4 4.5-5.4s4.5 2.2 4.5 5.4M2 19c.3-2.4 1.6-3.8 3.5-3.8M22 19c-.3-2.4-1.6-3.8-3.5-3.8"/>'),
    piggy: svg('<path d="M4 12.5C4 9 7.4 6.5 11.5 6.5c1.7 0 3.2.4 4.4 1.1L19 6v3.4c.8.8 1.3 1.7 1.5 2.6H22v3h-1.8c-.6 1.2-1.6 2.2-2.9 2.9V20h-3v-1.4a10 10 0 0 1-3.6 0V20H7.7v-2.4C5.5 16.5 4 14.6 4 12.5z"/><circle cx="15.5" cy="11" r=".8"/>'),
    bank: svg('<path d="M3 9.5L12 4l9 5.5M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20.5h18"/>'),
    building: svg('<path d="M4 21V8l8-5 8 5v13M9 21v-6h6v6M3 21h18"/>'),
    shield: svg('<path d="M12 3l7.5 3v5.5c0 4.6-3.2 8.1-7.5 9.5-4.3-1.4-7.5-4.9-7.5-9.5V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>'),
  };

  let S = null;
  let screen = 0;
  let sub = 0;
  let dir = "next";
  let overlay = null;
  let ended = false;
  const ui = { diagram: "with", need: null, note: {}, noteOpen: null, draft: {}, pick: null };

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const greekDate = (iso) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : esc(iso);
  };
  const questions = () => S.flow.questions;
  const answerOf = (qid) => S.flow.answers[qid];
  const axisTitle = (id) => (S.axes.find((a) => a.id === id) || {}).title || "";
  const list = (items, tag = "ul") => (items && items.length
    ? `<${tag}>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</${tag}>` : '<p class="muted">—</p>');

  function topicSlides() {
    return S.topics.flatMap((ax) => (S.content.categories[ax] || []).map((slide, i, all) => ({ axis: ax, slide, i, n: all.length })));
  }

  function subCount(section) {
    if (section === TOPICS) return Math.max(1, topicSlides().length);
    if (section === QUESTIONS) return questions().length + 1;
    if (section === SOLUTIONS) return Math.max(1, S.recommendations.length);
    return 1;
  }

  /* ----- server ------------------------------------------------------------------------------- */

  async function call(method, path = "", body, attempt = 0) {
    try {
      const res = await fetch(API + path, {
        method, credentials: "same-origin",
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json().catch(() => ({ error: "Μη αναμενόμενη απάντηση από τον Jarvis" }));
      if (!res.ok) {
        const err = new Error(data.error || "Η αποθήκευση απέτυχε");
        err.final = true;
        throw err;
      }
      return data;
    } catch (err) {
      if (!err.final && attempt < 4) {
        saved("Χωρίς σύνδεση — νέα προσπάθεια…", true);
        await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
        return call(method, path, body, attempt + 1);
      }
      throw err;
    }
  }

  let savedTimer = null;
  function saved(text, error = false) {
    const el = document.getElementById("saved");
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("error", error);
    el.style.opacity = 1;
    clearTimeout(savedTimer);
    if (!error) savedTimer = setTimeout(() => { el.style.opacity = 0; }, 2200);
  }

  let positionTimer = null;
  function savePosition() {
    clearTimeout(positionTimer);
    positionTimer = setTimeout(() => {
      let marker = sub ? `slide:${sub}` : null;
      if (screen === QUESTIONS) marker = questions()[sub] ? questions()[sub].id : null;
      call("POST", "/position", { screen, question: marker }).catch(() => saved("Η θέση δεν αποθηκεύτηκε", true));
    }, 350);
  }

  async function answer(qid, status, value) {
    const note = (ui.note[qid] ?? (answerOf(qid) || {}).note) || null;
    S.flow.answers[qid] = { status, value, note };
    saved("Αποθήκευση…");
    try {
      S = await call("POST", "/answer", { question: qid, status, value, note });
      const idx = questions().findIndex((q) => q.id === qid);
      if (idx >= 0) sub = idx;
      delete ui.draft[qid];
      saved("✓ Αποθηκεύτηκε");
      return true;
    } catch (err) {
      saved(err.message, true);
      return false;
    }
  }

  async function applyTopics(topics) {
    try {
      S = await call("POST", "/topics", { topics });
      saved("✓ Αποθηκεύτηκε");
      return true;
    } catch (err) {
      saved(err.message, true);
      return false;
    }
  }

  /* ----- navigation --------------------------------------------------------------------------- */

  function firstOpen() {
    const i = questions().findIndex((q) => !answerOf(q.id));
    return i < 0 ? questions().length : i;
  }

  function go(target, direction, at) {
    if (target < 0 || target > LAST) return;
    dir = direction || (target >= screen ? "next" : "prev");
    screen = target;
    if (at !== undefined) sub = at;
    else if (target === QUESTIONS) sub = dir === "next" ? firstOpen() : questions().length;
    else sub = dir === "next" ? 0 : subCount(target) - 1;
    if (target === INTERESTS) ui.pick = S.topics.slice();
    render(true);
    savePosition();
  }

  async function next() {
    if (screen === INTERESTS) {
      if (!ui.pick || !ui.pick.length) { saved("Επιλέξτε τουλάχιστον ένα θέμα", true); return; }
      if (!(await applyTopics(ui.pick))) return;
    }
    if (sub < subCount(screen) - 1) {
      sub += 1;
      dir = "next";
      if (screen === QUESTIONS) patchQuestions(); else render(true);
      savePosition();
      return;
    }
    go(screen + 1, "next");
  }

  function prev() {
    if (sub > 0) {
      sub = Math.min(sub, subCount(screen)) - 1;
      dir = "prev";
      if (screen === QUESTIONS) patchQuestions(); else render(true);
      savePosition();
      return;
    }
    go(screen - 1, "prev");
  }

  function toggleFullscreen(force) {
    const el = document.documentElement;
    if (!document.fullscreenElement && force !== false) {
      (el.requestFullscreen || el.webkitRequestFullscreen || (() => Promise.resolve())).call(el)?.catch?.(() => {});
    } else if (document.fullscreenElement && force !== true) {
      document.exitFullscreen?.();
    }
  }

  /* ----- layout ------------------------------------------------------------------------------- */
  /* Each slide is designed on a fixed canvas (landscape or portrait) and scaled as a whole to the
     screen, like a keynote slide; slides change with a 3D turn. */

  const CANVAS = { land: [1280, 740], port: [860, 1060] };
  let orientation = "land";

  function shell() {
    app.innerHTML = `
      <header class="topbar"><div class="brand"><img src="/static/advisor/logo-mark.png" alt="Κόλτσης Χρήστος"><span class="section" id="section"></span></div>
        <div class="tools"><button class="icon-btn" data-act="fullscreen" title="Πλήρης οθόνη" aria-label="Πλήρης οθόνη">${ICON.full}</button>
        <button class="icon-btn" data-act="exit" title="Έξοδος" aria-label="Έξοδος">${ICON.close}</button></div></header>
      <main class="stage" id="stage"><div class="viewport" id="viewport"></div></main>
      <footer class="bottombar" id="bottombar"></footer>`;
  }

  function render(animate) {
    if (ended) {
      app.innerHTML = `<div class="ended"><div><img src="/static/advisor/logo-full.png" alt="Κόλτσης Χρήστος — Insurance & Financial Advisor">
        <h2 class="display">Η παρουσίαση έκλεισε.</h2><p class="muted">Μπορείτε να κλείσετε αυτό το παράθυρο. Η πρόοδος έχει αποθηκευτεί.</p>
        <button class="btn" data-act="resume">Επιστροφή στην παρουσίαση</button></div></div>`;
      return;
    }
    if (!document.getElementById("viewport")) shell();
    sub = Math.min(sub, subCount(screen) - 1);
    setOrientation();
    document.getElementById("section").textContent = sectionLabel();
    document.getElementById("bottombar").innerHTML = bottombar();
    const vp = document.getElementById("viewport");
    const old = document.getElementById("screen");
    const slide = document.createElement("div");
    slide.className = `slide s-${S.content.screens[screen].id}`;
    slide.innerHTML = `<div class="tilt"><div class="inner">${SCREENS[screen]()}</div></div>`;
    if (old) {
      old.removeAttribute("id");
      old.querySelectorAll("[id]").forEach((n) => n.removeAttribute("id"));
      if (animate) {
        old.classList.add("leaving", `leave-${dir}`);
        setTimeout(() => old.remove(), 520);
      } else {
        old.remove();
      }
    }
    slide.id = "screen";
    if (animate) slide.classList.add(`enter-${dir}`);
    vp.appendChild(slide);
    document.querySelector(".overlay")?.remove();
    if (overlay) app.insertAdjacentHTML("beforeend", overlayHtml());
    fit();
    if (screen === QUESTIONS) focusQuestion();
  }

  function setOrientation() {
    const stage = document.getElementById("stage");
    if (!stage) return;
    orientation = stage.clientWidth / Math.max(stage.clientHeight, 1) >= 1.05 ? "land" : "port";
    app.classList.toggle("land", orientation === "land");
    app.classList.toggle("port", orientation === "port");
  }

  function sectionLabel() {
    if (screen === TOPICS) {
      const t = topicSlides()[sub];
      return t ? axisTitle(t.axis) : S.content.screens[screen].eyebrow;
    }
    return S.content.screens[screen].eyebrow;
  }

  function progressLabel() {
    if (screen === QUESTIONS) return `Ερώτηση ${Math.min(sub + 1, questions().length)} από ${questions().length}`;
    if (subCount(screen) > 1) return `${sub + 1} / ${subCount(screen)}`;
    return `${screen + 1} / ${LAST + 1}`;
  }

  function bottombar() {
    const segs = S.content.screens.map((s, i) =>
      `<button data-act="goto" data-i="${i}" class="${i < screen ? "done" : ""} ${i === screen ? "current" : ""}" title="${esc(s.eyebrow)}" aria-label="${esc(s.eyebrow)}"><span></span></button>`).join("");
    return `<div class="progress">${segs}</div><span class="progress-label" id="plabel">${progressLabel()}</span>
      <span class="saved" id="saved"></span>
      <div class="navbtns"><button class="btn quiet" data-act="prev" ${screen === 0 ? "disabled" : ""}>${ICON.left}<span>Πίσω</span></button>
      <button class="btn dark" data-act="next" ${screen === LAST ? "disabled" : ""}><span>Επόμενο</span>${ICON.right}</button></div>`;
  }

  function fit() {
    const stage = document.getElementById("stage");
    const vp = document.getElementById("viewport");
    if (!stage || !vp) return;
    setOrientation();
    // The canvas keeps its design size along the tighter side and stretches along the other one
    // (within limits), so the slide fills the screen instead of leaving empty bands.
    const [W0, H0] = CANVAS[orientation];
    const scale = Math.min(stage.clientWidth / W0, stage.clientHeight / H0);
    const W = Math.min(stage.clientWidth / scale, W0 * 1.4);
    const H = Math.min(stage.clientHeight / scale, H0 * 1.3);
    vp.style.width = `${W}px`;
    vp.style.height = `${H}px`;
    vp.style.transform = `translate(-50%, -50%) scale(${scale})`;
    const slide = document.getElementById("screen");
    const inner = slide && slide.querySelector(".inner");
    if (!inner) return;
    inner.style.transform = "";
    const need = inner.scrollHeight;
    const have = inner.clientHeight;
    if (need > have + 1) inner.style.transform = `scale(${Math.max(0.6, have / need)})`;
  }
  window.addEventListener("resize", () => { clearTimeout(fit.t); fit.t = setTimeout(fit, 120); });

  /* ----- screens ------------------------------------------------------------------------------ */

  const bars3d = () => `<div class="bars3d" aria-hidden="true">
      <div class="bar3d b1"><i class="f"></i><i class="s"></i></div>
      <div class="bar3d b2"><i class="f"></i><i class="s"></i></div>
      <div class="bar3d b3"><i class="f"></i><i class="s"></i></div></div>`;

  function sWelcome() {
    const w = S.content.welcome;
    const b = S.business;
    const who = [b.business_name && `<b>${esc(b.business_name)}</b>`, b.owner_name && esc(b.owner_name)].filter(Boolean).join(" · ");
    return `<div class="split welcome">
      <div class="welcome-text depth-2">
        <p class="eyebrow">${greekDate(S.meeting_date)}</p>
        ${who ? `<p class="business">${who}</p>` : ""}
        <h1 class="hero">${w.lines.map((l) => `<span>${esc(l)}</span>`).join("")}</h1>
        <hr class="rule">
        <p class="sub">${esc(w.subtitle)}</p>
        <button class="btn primary big" data-act="start">${esc(w.button)}${ICON.right}</button>
      </div>
      <div class="logo-hero depth-3"><img src="/static/advisor/logo-full.png" alt="Κόλτσης Χρήστος — Insurance & Financial Advisor"></div>
    </div>`;
  }

  function sAbout() {
    const a = S.content.advisor;
    return `<div class="split about">
      <div class="logo-card big depth-3"><img class="logo-full" src="/static/advisor/logo-full.png" alt="Κόλτσης Χρήστος — Insurance & Financial Advisor">
        <img class="partner" src="/static/advisor/nn-partner.png" alt="NN — ${esc(a.partner)}"></div>
      <div class="depth-1">
        <p class="eyebrow">Ποιος είμαι</p>
        <h1 class="title">${esc(a.name)}</h1>
        <p class="lead">${esc(a.title)}</p>
        <div class="creds">${a.credentials.map((c) => `<div class="card3d cred"><b>${esc(c.title)}</b><span>${esc(c.detail)}</span></div>`).join("")}</div>
        <blockquote class="slash">${a.philosophy.map((l) => `<span>${esc(l)}</span>`).join("")}</blockquote>
        <p class="contact"><span><b>Τ.</b> ${esc(a.phone)}</span><span>${esc(a.email)}</span></p>
      </div></div>`;
  }

  function sInterests() {
    const c = S.content.interests;
    if (!ui.pick) ui.pick = S.topics.slice();
    const tiles = S.axes.map((a) => {
      const item = c.items[a.id] || {};
      const on = ui.pick.includes(a.id);
      return `<button class="card3d choice ${on ? "on" : ""}" data-act="pick-topic" data-axis="${a.id}" role="checkbox" aria-checked="${on}">
        <span class="ic">${ICON[item.icon] || ""}</span><b>${esc(a.title)}</b><small>${esc(item.text)}</small>
        <span class="tick">${ICON.check}</span></button>`;
    }).join("");
    return `<div class="head-row"><h1 class="title">${esc(c.title)}</h1><p class="lead">${esc(c.lead)}</p></div>
      <div class="choices">${tiles}
        <button class="card3d choice go" data-act="next" id="pick-go" ${ui.pick.length ? "" : "disabled"}>
          <span class="count" id="pick-count">${pickCount()}</span><span class="go-label">Συνέχεια ${ICON.right}</span></button></div>`;
  }

  function pickCount() {
    const n = ui.pick ? ui.pick.length : 0;
    return n ? `${n} ${n === 1 ? "θέμα" : "θέματα"} για σήμερα` : "Επιλέξτε τουλάχιστον ένα θέμα";
  }

  function sTopics() {
    const t = topicSlides()[sub];
    if (!t) return "";
    const s = t.slide;
    const cards = (s.cards || []).map((c) => `<article class="card3d tcard">
        <p class="tag">${esc(c.tag)}</p><h3>${esc(c.title)}</h3>
        ${c.text ? `<p>${esc(c.text)}</p>` : ""}
        ${c.uses ? `<div class="uses">${c.uses.map((u, i) => `<div><b>0${i + 1}</b>${esc(u)}</div>`).join("")}</div>` : ""}
        ${c.example ? `<p class="example"><b>Για παράδειγμα</b>${esc(c.example)}</p>` : ""}</article>`).join("");
    return `<div class="split topic">
      <div class="depth-1"><p class="eyebrow">${esc(axisTitle(t.axis))}${t.n > 1 ? ` · ${t.i + 1}/${t.n}` : ""}</p>
        <h1 class="title">${esc(s.title)}</h1><p class="lead">${esc(s.lead)}</p>
        ${s.term ? `<p class="term"><b>${esc(s.term.word)}:</b> ${esc(s.term.meaning)}</p>` : ""}
        ${s.note ? `<p class="slash small">${esc(s.note)}</p>` : ""}</div>
      <div class="depth-2">${cards ? `<div class="tcards n${(s.cards || []).length}">${cards}</div>` : ""}
        ${s.diagram === "partners" ? partnerDiagram() : ""}</div></div>`;
  }

  function partnerDiagram() {
    const d = S.content.diagram;
    const mode = ui.diagram;
    return `<div class="diagram" id="diagram"><div class="seg" role="group" aria-label="Σενάριο">
        <button data-act="diagram" data-mode="without" class="${mode === "without" ? "on" : ""}">${esc(d.without.label)}</button>
        <button data-act="diagram" data-mode="with" class="${mode === "with" ? "on" : ""}">${esc(d.with.label)}</button></div>
      <div class="flow ${mode}">${d[mode].steps.map((s, i) => `<div class="card3d"><b>0${i + 1}</b>${esc(s)}</div>`).join("")}</div></div>`;
  }

  function sQuestions() {
    return `<div class="split questions">
      <div class="q-side depth-1"><h1 class="title">${esc(S.content.questions.title)}</h1>
        <div class="axes" id="axes">${axesChips()}</div></div>
      <div id="qzone" class="depth-2">${qZone()}</div></div>`;
  }

  function sFindings() {
    const f = S.content.findings;
    if (!S.flow.handled) {
      return `<div class="center-col"><h1 class="title">${esc(f.title)}</h1><div class="card3d empty-state"><p class="lead">${esc(f.empty)}</p>
        <button class="btn primary" data-act="goto" data-i="${QUESTIONS}">Στις ερωτήσεις</button></div></div>`;
    }
    const legend = S.levels.map((l) => `<span class="lv-${l.id}"><i></i>${esc(l.label)}</span>`).join("");
    const cols = S.pillars.filter((p) => S.needs.some((n) => n.pillar === p.id)).map((p) => {
      const tiles = S.needs.filter((n) => n.pillar === p.id).map((n) =>
        `<button class="tile ${n.level}" data-act="need" data-id="${n.id}"><span>${esc(n.title)}</span><small>${esc(n.level_label)}</small></button>`).join("");
      return `<div class="col"><h3>${esc(p.title)}</h3><div class="tiles">${tiles}</div></div>`;
    }).join("");
    return `<div class="split findings">
      <div class="depth-1"><h1 class="title">${esc(f.title)}</h1><p class="lead">${esc(f.lead)}</p>
        <div class="legend">${legend}</div><p class="muted small">Πατήστε ένα θέμα για λεπτομέρειες.</p></div>
      <div class="map depth-2">${cols}</div></div>`;
  }

  function sSolutions() {
    const c = S.content.solutions;
    const recs = S.recommendations;
    if (!recs.length) {
      return `<div class="center-col"><h1 class="title">${esc(c.title)}</h1>
        <div class="card3d empty-state"><p class="lead">${esc(c.empty)}</p></div><p class="disclaimer">${esc(S.solution_labels.disclaimer)}</p></div>`;
    }
    const r = recs[sub];
    const status = r.products.length
      ? `<div class="status-pill doc">${esc(r.status_label)}${r.products.map((p) => `<small><b>${esc(p.name)}</b>${p.provider ? ` · ${esc(p.provider)}` : ""}</small>`).join("")}</div>`
      : `<div class="status-pill">${esc(r.status_label)}</div>`;
    const documented = r.products.flatMap((p) => p.benefits);
    const limits = r.products.flatMap((p) => p.limitations);
    const more = sub === recs.length - 1 && S.more_topics.length
      ? `<div class="more-topics"><b class="muted">Επίσης για επόμενη συζήτηση:</b>${S.more_topics.map((t) => `<span>${esc(t)}</span>`).join("")}</div>` : "";
    return `<div class="split solution">
      <div class="depth-1"><p class="eyebrow">Κατεύθυνση ${sub + 1} από ${recs.length} · ${esc(r.need_title)}</p>
        <h1 class="title">${esc(r.title)}</h1>
        <p class="lbl">Γιατί έχει σημασία</p><p class="lead dark">${esc(r.why)}</p>
        <p class="lbl">Κατεύθυνση προστασίας</p><p>${esc(r.direction)}</p>${status}</div>
      <div class="card3d sol-side depth-2">
        <p class="lbl">Πιθανά οφέλη</p>${list(r.benefits)}
        ${documented.length ? `<p class="lbl">Από τους όρους του προϊόντος</p><ul>${documented.map((b) => `<li>${esc(b.text)} <span class="muted">(${esc(b.source)})</span></li>`).join("")}</ul>` : ""}
        <p class="lbl">Τι εξετάζουμε πριν από οποιαδήποτε πρόταση</p>${list(r.examine)}
        ${limits.length ? `<p class="lbl">Περιορισμοί από τους όρους</p><ul>${limits.map((l) => `<li>${esc(l.text)} <span class="muted">(${esc(l.source)})</span></li>`).join("")}</ul>` : ""}
        ${more}<p class="disclaimer">${esc(S.solution_labels.disclaimer)}</p></div></div>`;
  }

  const shortList = (items, max = 5) => {
    const shown = (items || []).slice(0, max);
    const rest = (items || []).length - shown.length;
    return shown.length ? `<ul>${shown.map((x) => `<li>${esc(x)}</li>`).join("")}${rest > 0 ? `<li class="muted">και ${rest} ακόμη στην περίληψη</li>` : ""}</ul>` : '<p class="muted">—</p>';
  };

  function sRecap() {
    const s = S.summary.content;
    return `<div class="head-row"><h1 class="title">${esc(S.content.recap.title)}</h1></div>
      <div class="recap">
        <section class="card3d"><span class="num">01</span><h3>Θέματα που συζητήσαμε</h3>${shortList(s.topics)}</section>
        <section class="card3d"><span class="num">02</span><h3>Οι ανάγκες που εντοπίσαμε</h3>${shortList(s.priorities, 4)}</section>
        <section class="card3d"><span class="num">03</span><h3>Τι χρειάζεται να διερευνήσουμε</h3>${shortList(s.information_needed)}</section>
      </div>`;
  }

  function sNext() {
    const n = S.content.next;
    return `<div class="head-row"><h1 class="title">${esc(n.title)}</h1></div>
      <div class="process">${n.process.map((p, i) => `<div class="card3d pstep ${i === 0 ? "now" : ""}">${i === 0 ? '<span class="today">Σήμερα</span>' : ""}<b>${esc(p.number)}</b><strong>${esc(p.title)}</strong><span>${esc(p.text)}</span></div>`).join("")}</div>
      <div class="steps"><h3>Πώς προχωράμε</h3>${list(n.steps, "ol")}</div>`;
  }

  function sClosing() {
    const n = S.content.next;
    const a = S.content.advisor;
    return `<div class="split closing">
      <div class="welcome-art">${bars3d()}
        <div class="logo-card depth-3"><img src="/static/advisor/logo-full.png" alt="Κόλτσης Χρήστος — Insurance & Financial Advisor"></div></div>
      <div class="depth-2"><h1 class="hero small">${n.closing.map((l) => `<span>${esc(l)}</span>`).join("")}</h1>
        <p class="contact"><span><b>Τ.</b> ${esc(a.phone)}</span><span>${esc(a.email)}</span></p>
        <div class="acts"><button class="btn" data-act="summary">Προβολή περίληψης</button>
          <button class="btn primary" data-act="export">Εξαγωγή PDF</button></div>
        <p class="disclaimer">${esc(S.content.footer)}</p></div></div>`;
  }

  function axesChips() {
    const current = questions()[sub];
    return S.topics.filter((ax) => questions().some((q) => q.axis === ax)).map((ax) => {
      const qs = questions().filter((q) => q.axis === ax);
      const done = qs.every((q) => answerOf(q.id));
      const cur = current && current.axis === ax;
      return `<button data-act="axis" data-axis="${ax}" class="${done ? "done" : ""} ${cur ? "current" : ""}">${esc(axisTitle(ax))}</button>`;
    }).join("") + `<button class="pick" data-act="topics">Αλλαγή θεμάτων</button>`;
  }

  function qZone() {
    const qs = questions();
    if (sub >= qs.length) {
      const open = qs.filter((q) => !answerOf(q.id)).length;
      return `<div class="qcard card3d q-done"><div class="check-circle">${ICON.check}</div>
        <h2>Ευχαριστώ για τις απαντήσεις!</h2>
        <p>${open ? `Μένουν ${open} ερωτήσεις — μπορούμε να επιστρέψουμε σε αυτές όποτε θέλετε.` : "Ας δούμε τι διαπιστώσαμε."}</p>
        <div class="q-actions center">${open ? `<button class="btn" data-act="first-open">Στις υπόλοιπες ερωτήσεις</button>` : ""}
        <button class="btn primary" data-act="next">Τι διαπιστώσαμε${ICON.right}</button></div></div>`;
    }
    const q = qs[sub];
    const a = answerOf(q.id);
    const status = a ? (a.status === "answered" ? "✓ Απαντήθηκε" : a.status === "unknown" ? "Δεν γνωρίζω" : "Παραλείφθηκε") : "";
    const note = ui.note[q.id] ?? (a && a.note) ?? "";
    const noteOpen = ui.noteOpen === q.id || Boolean(note);
    const needsSubmit = q.type === "multi" || q.type === "number";
    return `<div class="qcard card3d" data-q="${esc(q.id)}">
      <p class="axis"><span>${esc(axisTitle(q.axis))}</span><span>${sub + 1} / ${qs.length}</span></p>
      ${q.hint ? `<p class="hint">${esc(q.hint)}</p>` : ""}
      <h2 id="qtext">${esc(q.text)}</h2>
      ${controls(q, a)}
      <div class="q-actions">
        ${q.allow_unknown ? `<button class="btn quiet ${a && a.status === "unknown" ? "on" : ""}" data-act="unknown">Δεν γνωρίζω</button>` : ""}
        <button class="btn quiet ${a && a.status === "skipped" ? "on" : ""}" data-act="skip">Παράλειψη</button>
        ${q.allow_note ? `<button class="btn quiet ${noteOpen ? "on" : ""}" data-act="note">Σχόλιο</button>` : ""}
        <span class="spacer"></span><span class="q-status">${status}</span>
        ${needsSubmit ? `<button class="btn primary" data-act="submit">Συνέχεια${ICON.right}</button>` : ""}
      </div>
      ${noteOpen ? `<div class="q-note"><textarea id="note" maxlength="500" rows="2" placeholder="Σχόλιο για αυτή την ερώτηση (προαιρετικό)">${esc(note)}</textarea></div>` : ""}
    </div>`;
  }

  function controls(q, a) {
    const answered = a && a.status === "answered" ? a.value : null;
    if (q.type === "yes_no" || q.type === "single") {
      return `<div class="options ${q.type === "yes_no" ? "yn" : ""}" role="radiogroup">${q.options.map((o) =>
        `<button class="opt ${answered === o.value ? "on" : ""}" role="radio" aria-checked="${answered === o.value}" data-act="pick" data-v="${esc(o.value)}"><span class="box"></span>${esc(o.label)}</button>`).join("")}</div>`;
    }
    if (q.type === "multi") {
      const draft = ui.draft[q.id] || (Array.isArray(answered) ? answered.slice() : []);
      ui.draft[q.id] = draft;
      return `<div class="options" role="group">${q.options.map((o) =>
        `<button class="opt multi ${draft.includes(o.value) ? "on" : ""}" role="checkbox" aria-checked="${draft.includes(o.value)}" data-act="toggle" data-v="${esc(o.value)}"><span class="box"></span>${esc(o.label)}</button>`).join("")}</div>`;
    }
    let value = ui.draft[q.id];
    if (value == null && typeof answered === "number") value = answered;
    if (value == null && q.suggested != null && /^\d+$/.test(String(q.suggested))) value = Number(q.suggested);
    const suggested = (answered == null && q.suggested != null && ui.draft[q.id] == null)
      ? `<p class="suggested">Από την προετοιμασία: ${esc(q.suggested)} — επιβεβαιώστε ή αλλάξτε.</p>` : "";
    return `<div class="number"><button class="step" data-act="step" data-d="-1" aria-label="Μείωση">−</button>
      <input id="num" inputmode="numeric" autocomplete="off" aria-labelledby="qtext" value="${value == null ? "" : esc(value)}" placeholder="0">
      <button class="step" data-act="step" data-d="1" aria-label="Αύξηση">+</button><span class="unit">${esc(q.unit || "")}</span></div>${suggested}`;
  }

  const SCREENS = [sWelcome, sAbout, sInterests, sTopics, sQuestions, sFindings, sSolutions, sRecap, sNext, sClosing];

  /* ----- overlays ----------------------------------------------------------------------------- */

  function overlayHtml() {
    const wrap = (label, body) => `<div class="overlay" data-act="close-overlay"><div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(label)}">${body}</div></div>`;
    if (overlay === "summary") {
      const s = S.summary.content;
      return wrap("Περίληψη συνάντησης", `
        <p class="eyebrow">Περίληψη συνάντησης</p><h2>${esc(s.business_name || "Η επιχείρησή σας")}</h2><p class="muted">${greekDate(s.meeting_date)}</p>
        <h4>Τι συζητήσαμε</h4>${list(s.topics)}
        <h4>Οι προτεραιότητες που αναδείχθηκαν</h4>${list(s.priorities)}
        <h4>Προτεινόμενες κατευθύνσεις</h4>${(s.directions || []).map((d) => `<div class="dir"><b>${esc(d.title)}</b>${d.need ? `<br><span class="muted">${esc(d.need)}</span>` : ""}<br>${esc(d.why)}${d.solution ? `<br><i class="muted">${esc(d.solution)}</i>` : ""}</div>`).join("") || '<p class="muted">—</p>'}
        <h4>Τι χρειάζεται να συγκεντρώσουμε</h4>${list(s.information_needed)}
        <h4>Τα επόμενα βήματα</h4>${list(s.next_steps, "ol")}
        <div class="acts"><button class="btn quiet" data-act="close-overlay">Κλείσιμο</button><button class="btn dark" data-act="export">Εξαγωγή PDF</button></div>`);
    }
    if (overlay === "need") {
      const n = S.needs.find((x) => x.id === ui.need);
      if (!n) return "";
      const ev = n.evidence.length
        ? `<h4>Με βάση όσα συζητήσαμε</h4><ul>${n.evidence.map((e) => `<li>${esc(e.label)}: ${esc(e.answer)}</li>`).join("")}</ul>`
        : `<p class="muted">Δεν έχουμε ακόμη απαντήσεις για αυτό το θέμα.</p>`;
      return wrap(n.title, `<p class="eyebrow">${esc(n.level_label)}</p><h2>${esc(n.title)}</h2><p class="big">${esc(n.statement)}</p>${ev}
        <div class="acts"><button class="btn dark" data-act="close-overlay">Κλείσιμο</button></div>`);
    }
    if (overlay === "approve") {
      return wrap("Έγκριση περίληψης", `
        <p class="eyebrow">Έλεγχος από τον σύμβουλο</p><h2>Έγκριση πριν από την εξαγωγή</h2>
        <p>Η περίληψη εξάγεται σε PDF μόνο αφού ο σύμβουλος ελέγξει το περιεχόμενό της. Για αλλαγές στο κείμενο χρησιμοποιήστε την επεξεργασία περίληψης στο περιβάλλον του συμβούλου.</p>
        <label><input type="checkbox" id="approve-check"> Έχω ελέγξει το περιεχόμενο της περίληψης και εγκρίνω την εξαγωγή.</label>
        <div class="acts"><button class="btn quiet" data-act="close-overlay">Άκυρο</button><button class="btn primary" data-act="approve" id="approve-btn" disabled>Έγκριση & εξαγωγή PDF</button></div>`);
    }
    if (overlay === "topics") {
      const rows = S.axes.map((a) => `<label><input type="checkbox" data-topic="${a.id}" ${S.topics.includes(a.id) ? "checked" : ""}><span>${esc(a.title)}</span></label>`).join("");
      return wrap("Θέματα συζήτησης", `
        <p class="eyebrow">Θέματα συζήτησης</p><h2>Τι θα συζητήσουμε σήμερα;</h2>
        <p class="muted">Ρωτάμε μόνο τα επιλεγμένα θέματα. Οι απαντήσεις που έχουν δοθεί δεν χάνονται.</p>${rows}
        <div class="acts"><button class="btn quiet" data-act="close-overlay">Άκυρο</button><button class="btn primary" data-act="apply-topics">Εφαρμογή</button></div>`);
    }
    if (overlay === "exit") {
      return wrap("Έξοδος", `<h2>Έξοδος από την παρουσίαση;</h2><p class="muted">Η πρόοδος και οι απαντήσεις έχουν αποθηκευτεί.</p>
        <div class="acts"><button class="btn quiet" data-act="close-overlay">Συνέχεια παρουσίασης</button><button class="btn dark" data-act="end">Έξοδος</button></div>`);
    }
    return "";
  }

  function openOverlay(name) {
    overlay = name;
    document.querySelector(".overlay")?.remove();
    app.insertAdjacentHTML("beforeend", overlayHtml());
  }
  function closeOverlay() {
    overlay = null;
    document.querySelector(".overlay")?.remove();
  }

  const printUrl = () => `/advisor/p/${ID}/summary/print`;

  async function exportPdf() {
    if (S.summary.approved) {
      window.open(printUrl(), "_blank");
      return;
    }
    openOverlay("approve");
  }

  async function approveAndExport() {
    const win = window.open("about:blank", "_blank");
    try {
      await call("POST", "/approve", {});
      S.summary.approved = true;
      closeOverlay();
      saved("✓ Εγκρίθηκε");
      if (win) win.location.href = printUrl(); else window.open(printUrl(), "_blank");
    } catch (err) {
      if (win) win.close();
      saved(err.message, true);
    }
  }

  /* ----- partial updates ---------------------------------------------------------------------- */

  function patch(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }

  function patchQuestions() {
    if (screen !== QUESTIONS) return;
    patch("qzone", qZone());
    patch("axes", axesChips());
    patch("plabel", progressLabel());
    fit();
    focusQuestion();
  }

  function focusQuestion() {
    const card = document.querySelector(".qcard");
    if (!card || !window.matchMedia("(pointer: fine)").matches) return;
    const first = card.querySelector("#num, .opt.on, .opt, .btn.primary");
    if (first) first.focus({ preventScroll: true });
  }

  const currentQuestion = () => (screen === QUESTIONS ? questions()[sub] : null);

  async function submitCurrent() {
    const q = currentQuestion();
    if (!q) return;
    if (q.type === "multi") {
      const value = ui.draft[q.id] || [];
      if (!value.length) { saved("Επιλέξτε τουλάχιστον μία απάντηση", true); return; }
      if (await answer(q.id, "answered", value)) next();
    } else if (q.type === "number") {
      const digits = ((document.getElementById("num") || {}).value || "").replace(/[^\d]/g, "");
      if (!digits) { saved("Συμπληρώστε έναν αριθμό ή επιλέξτε «Παράλειψη»", true); return; }
      if (await answer(q.id, "answered", Number(digits))) next();
    }
  }

  /* ----- events ------------------------------------------------------------------------------- */

  app.addEventListener("click", async (ev) => {
    const el = ev.target.closest("[data-act]");
    if (!el || !app.contains(el)) return;
    const act = el.dataset.act;
    if (act === "close-overlay" && el.classList.contains("overlay") && ev.target !== el) return;
    const q = currentQuestion();
    switch (act) {
      case "next": next(); break;
      case "prev": prev(); break;
      case "goto": go(Number(el.dataset.i)); break;
      case "start": toggleFullscreen(true); go(ABOUT, "next"); break;
      case "fullscreen": toggleFullscreen(); break;
      case "exit": openOverlay("exit"); break;
      case "end":
        closeOverlay();
        window.close();
        setTimeout(() => { ended = true; render(false); }, 150);
        break;
      case "resume": ended = false; render(true); break;
      case "pick-topic": {
        const ax = el.dataset.axis;
        ui.pick = ui.pick.includes(ax) ? ui.pick.filter((x) => x !== ax) : ui.pick.concat(ax);
        el.classList.toggle("on", ui.pick.includes(ax));
        el.setAttribute("aria-checked", String(ui.pick.includes(ax)));
        patch("pick-count", pickCount());
        document.getElementById("pick-go").disabled = !ui.pick.length;
        break;
      }
      case "diagram":
        ui.diagram = el.dataset.mode;
        document.getElementById("diagram").outerHTML = partnerDiagram();
        fit();
        break;
      case "axis": {
        const ax = el.dataset.axis;
        let i = questions().findIndex((x) => x.axis === ax && !answerOf(x.id));
        if (i < 0) i = questions().findIndex((x) => x.axis === ax);
        if (i >= 0) { sub = i; patchQuestions(); savePosition(); }
        break;
      }
      case "first-open": sub = firstOpen(); patchQuestions(); savePosition(); break;
      case "pick":
        if (!q) break;
        el.parentElement.querySelectorAll(".opt").forEach((o) => o.classList.toggle("on", o === el));
        if (await answer(q.id, "answered", el.dataset.v)) setTimeout(next, 260);
        break;
      case "toggle": {
        if (!q) break;
        const v = el.dataset.v;
        let draft = ui.draft[q.id] || [];
        if (draft.includes(v)) draft = draft.filter((x) => x !== v);
        else if ((q.exclusive || []).includes(v)) draft = [v];
        else draft = draft.filter((x) => !(q.exclusive || []).includes(x)).concat(v);
        ui.draft[q.id] = draft;
        el.parentElement.querySelectorAll(".opt").forEach((o) => {
          const on = draft.includes(o.dataset.v);
          o.classList.toggle("on", on);
          o.setAttribute("aria-checked", String(on));
        });
        break;
      }
      case "submit": submitCurrent(); break;
      case "step": {
        const input = document.getElementById("num");
        const val = Math.max(0, (Number((input.value || "0").replace(/[^\d]/g, "")) || 0) + Number(el.dataset.d));
        input.value = String(val);
        ui.draft[q.id] = val;
        break;
      }
      case "unknown": if (q && await answer(q.id, "unknown", null)) setTimeout(next, 200); break;
      case "skip": if (q && await answer(q.id, "skipped", null)) setTimeout(next, 200); break;
      case "note":
        if (!q) break;
        ui.noteOpen = ui.noteOpen === q.id ? null : q.id;
        patch("qzone", qZone());
        fit();
        document.getElementById("note")?.focus();
        break;
      case "need": ui.need = el.dataset.id; openOverlay("need"); break;
      case "topics": openOverlay("topics"); break;
      case "apply-topics": {
        const topics = [...document.querySelectorAll("[data-topic]")].filter((x) => x.checked).map((x) => x.dataset.topic);
        if (!topics.length) { saved("Επιλέξτε τουλάχιστον ένα θέμα", true); break; }
        if (await applyTopics(topics)) { overlay = null; sub = firstOpen(); render(false); }
        break;
      }
      case "summary": openOverlay("summary"); break;
      case "export": exportPdf(); break;
      case "approve": approveAndExport(); break;
      case "close-overlay": closeOverlay(); break;
      default: break;
    }
  });

  let noteTimer = null;
  app.addEventListener("input", (ev) => {
    const t = ev.target;
    const q = currentQuestion();
    if (t.id === "num" && q) {
      const digits = t.value.replace(/[^\d]/g, "");
      if (digits !== t.value) t.value = digits;
      ui.draft[q.id] = digits ? Number(digits) : null;
    } else if (t.id === "note" && q) {
      ui.note[q.id] = t.value;
      clearTimeout(noteTimer);
      const a = answerOf(q.id);
      if (a) noteTimer = setTimeout(() => answer(q.id, a.status, a.value), 700);
    } else if (t.id === "approve-check") {
      document.getElementById("approve-btn").disabled = !t.checked;
    }
  });

  document.addEventListener("keydown", (ev) => {
    if (!S || ended) return;
    const tag = (ev.target.tagName || "").toLowerCase();
    if (ev.key === "Escape" && overlay) { closeOverlay(); return; }
    if (overlay) return;
    if (ev.key === "Enter" && ev.target.id === "num") { ev.preventDefault(); submitCurrent(); return; }
    if (tag === "input" || tag === "textarea") return;
    if (ev.key === "ArrowRight" || ev.key === "PageDown") { ev.preventDefault(); next(); }
    if (ev.key === "ArrowLeft" || ev.key === "PageUp") { ev.preventDefault(); prev(); }
    if (ev.key === "f" || ev.key === "F") toggleFullscreen();
  });

  let touch = null;
  app.addEventListener("touchstart", (ev) => {
    const t = ev.touches[0];
    touch = ev.target.closest("input, textarea, .overlay") ? null : { x: t.clientX, y: t.clientY };
  }, { passive: true });
  app.addEventListener("touchend", (ev) => {
    if (!touch || overlay) return;
    const t = ev.changedTouches[0];
    const dx = t.clientX - touch.x;
    const dy = t.clientY - touch.y;
    touch = null;
    if (Math.abs(dx) > 80 && Math.abs(dy) < 50) (dx < 0 ? next : prev)();
  }, { passive: true });

  /* ----- start -------------------------------------------------------------------------------- */

  (async () => {
    try {
      S = await call("GET");
    } catch (err) {
      app.innerHTML = `<div class="ended"><div><h2 class="display">Η παρουσίαση δεν είναι διαθέσιμη</h2><p class="muted">${esc(err.message)}</p></div></div>`;
      return;
    }
    if (location.hash === "#start") {
      screen = 0;
      history.replaceState(null, "", location.pathname);
      savePosition();
    } else {
      screen = Math.min(Math.max(S.position.screen || 0, 0), LAST);
      const marker = S.position.question || "";
      if (screen === QUESTIONS) {
        const i = questions().findIndex((q) => q.id === marker);
        sub = i >= 0 ? i : firstOpen();
      } else if (marker.startsWith("slide:")) {
        sub = Number(marker.slice(6)) || 0;
      }
    }
    if (screen === INTERESTS) ui.pick = S.topics.slice();
    document.title = S.business.business_name ? `${S.business.business_name} · Παρουσίαση` : "Παρουσίαση";
    render(true);
    if (document.fonts) document.fonts.ready.then(fit);
  })();
})();
