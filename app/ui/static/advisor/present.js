/* Client presentation. Reads only /api/present/<id>, which carries client-safe data. */
(() => {
  "use strict";
  const ID = document.body.dataset.presentation;
  const API = `/api/present/${ID}`;
  const app = document.getElementById("app");
  const QUESTIONS = 6;
  const LAST = 9;
  const MONTHS = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου", "Αυγούστου",
    "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"];
  const svg = (d, extra = "") => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra}>${d}</svg>`;
  const ICON = {
    right: svg('<path d="M5 12h14M13 6l6 6-6 6"/>'),
    left: svg('<path d="M19 12H5M11 6l-6 6 6 6"/>'),
    down: svg('<path d="M6 9l6 6 6-6"/>'),
    check: svg('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
    full: svg('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'),
    close: svg('<path d="M6 6l12 12M18 6L6 18"/>'),
    building: svg('<path d="M4 21V8l8-5 8 5v13M9 21v-6h6v6M3 21h18"/>'),
    people: svg('<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20c.6-3.4 2.8-5.3 5.5-5.3s4.9 1.9 5.5 5.3"/><circle cx="17" cy="9" r="2.6"/><path d="M16 14.6c2.4.2 4 1.9 4.5 5.4"/>'),
    gear: svg('<circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.6M12 18.6v2.6M4.2 6.5l2.2 1.3M17.6 16.2l2.2 1.3M4.2 17.5l2.2-1.3M17.6 7.8l2.2-1.3"/><circle cx="12" cy="12" r="7.2"/>'),
    truck: svg('<path d="M2 6h11v10H2zM13 10h4.5L21 13.5V16h-8"/><circle cx="6.5" cy="17.5" r="1.8"/><circle cx="16.5" cy="17.5" r="1.8"/>'),
    shield: svg('<path d="M12 3l7.5 3v5.5c0 4.6-3.2 8.1-7.5 9.5-4.3-1.4-7.5-4.9-7.5-9.5V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>'),
    clock: svg('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
    flag: svg('<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>'),
  };

  let S = null;
  let screen = 0;
  let qIndex = 0;
  let dir = "next";
  let overlay = null;
  let ended = false;
  const ui = { help: {}, key: 0, staff: 0, ops: {}, diagram: "with", need: null, solTab: {}, note: {}, months: 6, draft: {} };

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => `${Math.round(n).toLocaleString("el-GR")} €`;
  const greekDate = (iso) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : esc(iso);
  };
  const relevant = (axes) => (axes || []).some((a) => S.emphasis.includes(a));
  const forYou = (axes) => (relevant(axes) ? '<span class="badge">Σχετικό για εσάς</span>' : "");
  const questions = () => S.flow.questions;
  const answerOf = (qid) => S.flow.answers[qid];
  const axisTitle = (id) => (S.axes.find((a) => a.id === id) || {}).title || "";

  /* ----- server ------------------------------------------------------------------------------- */

  async function call(method, path = "", body, attempt = 0) {
    try {
      const res = await fetch(API + path, {
        method, credentials: "same-origin",
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json();
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
      const q = screen === QUESTIONS && questions()[qIndex] ? questions()[qIndex].id : null;
      call("POST", "/position", { screen, question: q }).catch(() => saved("Η θέση δεν αποθηκεύτηκε", true));
    }, 350);
  }

  async function answer(qid, status, value) {
    const note = (ui.note[qid] ?? (answerOf(qid) || {}).note) || null;
    S.flow.answers[qid] = { status, value, note };
    saved("Αποθήκευση…");
    try {
      const view = await call("POST", "/answer", { question: qid, status, value, note });
      S = view;
      const idx = questions().findIndex((q) => q.id === qid);
      if (idx >= 0) qIndex = idx;
      delete ui.draft[qid];
      saved("✓ Αποθηκεύτηκε");
      return true;
    } catch (err) {
      saved(err.message, true);
      return false;
    }
  }

  async function clearAnswer(qid) {
    try {
      S = await call("POST", "/clear", { question: qid });
      const idx = questions().findIndex((q) => q.id === qid);
      if (idx >= 0) qIndex = idx;
      delete ui.draft[qid];
      patchQuestions();
      saved("✓ Αποθηκεύτηκε");
    } catch (err) { saved(err.message, true); }
  }

  /* ----- navigation --------------------------------------------------------------------------- */

  function firstOpen() {
    const i = questions().findIndex((q) => !answerOf(q.id));
    return i < 0 ? questions().length : i;
  }

  function go(target, direction) {
    if (target < 0 || target > LAST) return;
    dir = direction || (target >= screen ? "next" : "prev");
    if (target === QUESTIONS && screen !== QUESTIONS) qIndex = dir === "next" ? firstOpen() : questions().length;
    screen = target;
    render(true);
    savePosition();
  }

  function next() {
    if (screen === QUESTIONS && qIndex < questions().length) {
      qIndex += 1;
      dir = "next";
      patchQuestions();
      savePosition();
      return;
    }
    go(screen + 1, "next");
  }

  function prev() {
    if (screen === QUESTIONS && qIndex > 0) {
      qIndex = Math.min(qIndex, questions().length) - 1;
      dir = "prev";
      patchQuestions();
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

  function render(animate) {
    if (ended) {
      app.innerHTML = `<div class="ended"><div><img src="/static/advisor/logo-full.png" alt="Κόλτσης Χρήστος — Insurance & Financial Advisor">
        <h2 class="display">Η παρουσίαση έκλεισε.</h2><p class="muted">Μπορείτε να κλείσετε αυτό το παράθυρο. Η πρόοδος έχει αποθηκευτεί.</p>
        <button class="btn" data-act="resume">Επιστροφή στην παρουσίαση</button></div></div>`;
      return;
    }
    const stage = document.getElementById("stage");
    const keepScroll = !animate && stage ? stage.scrollTop : 0;
    const eyebrow = S.content.screens[screen].eyebrow;
    app.innerHTML = `
      <header class="topbar"><div class="brand"><img src="/static/advisor/logo-mark.png" alt="Κόλτσης Χρήστος"><span class="section">${esc(eyebrow)}</span></div>
        <div class="tools"><button class="icon-btn" data-act="fullscreen" title="Πλήρης οθόνη" aria-label="Πλήρης οθόνη">${ICON.full}</button>
        <button class="icon-btn" data-act="exit" title="Έξοδος" aria-label="Έξοδος">${ICON.close}</button></div></header>
      <main class="stage" id="stage"><div class="screen ${animate ? `enter-${dir}` : ""}">${SCREENS[screen]()}</div></main>
      ${bottombar()}
      ${overlay ? overlayHtml() : ""}`;
    const st = document.getElementById("stage");
    if (st) st.scrollTop = keepScroll;
    afterRender();
  }

  function bottombar() {
    const segs = S.content.screens.map((s, i) =>
      `<button data-act="goto" data-i="${i}" class="${i < screen ? "done" : ""} ${i === screen ? "current" : ""}" title="${esc(s.eyebrow)}" aria-label="${esc(s.eyebrow)}"><span></span></button>`).join("");
    let label = `${screen + 1} / ${LAST + 1}`;
    if (screen === QUESTIONS) label = `Συζητήσαμε ${S.flow.handled} από ${S.flow.total}`;
    return `<footer class="bottombar"><div class="progress">${segs}</div><span class="progress-label" id="plabel">${label}</span>
      <span class="saved" id="saved"></span>
      <div class="navbtns"><button class="btn quiet" data-act="prev" ${screen === 0 ? "disabled" : ""}>${ICON.left}Πίσω</button>
      <button class="btn dark" data-act="next" ${screen === LAST ? "disabled" : ""}>Επόμενο${ICON.right}</button></div></footer>`;
  }

  function afterRender() {
    if (screen === QUESTIONS) focusQuestion();
  }

  /* ----- screens ------------------------------------------------------------------------------ */

  function sWelcome() {
    const w = S.content.welcome;
    const b = S.business;
    const who = [b.business_name && `<b>${esc(b.business_name)}</b>`, b.owner_name && esc(b.owner_name)].filter(Boolean).join(" · ");
    return `<div class="welcome">
      <div>
        <p class="eyebrow rise">${greekDate(S.meeting_date)}</p>
        ${who ? `<p class="business rise">${who}</p>` : ""}
        <h1 class="title rise">${w.lines.map((l) => `<span>${esc(l)}</span>`).join("")}</h1>
        <hr class="rule rise">
        <p class="sub rise">${esc(w.subtitle)}</p>
        <button class="btn primary rise" data-act="start">${esc(w.button)}${ICON.right}</button>
        <div class="pillars rise">${S.pillars.map((p) => `<div><b>${esc(p.number)}</b>${esc(p.title)}</div>`).join("")}</div>
      </div>
      <div class="stripes" aria-hidden="true"><i></i><i></i><i></i>
        <img class="logo" src="/static/advisor/logo-full.png" alt="Κόλτσης Χρήστος — Insurance & Financial Advisor"></div>
    </div>`;
  }

  function sAbout() {
    const a = S.content.advisor;
    return `<div class="about">
      <div class="rise"><img class="logo-full" src="/static/advisor/logo-full.png" alt="Κόλτσης Χρήστος — Insurance & Financial Advisor">
        <img class="partner" src="/static/advisor/nn-partner.png" alt="NN — ${esc(a.partner)}"></div>
      <div>
        <p class="eyebrow rise">Ποιος είμαι</p>
        <h1 class="name rise">${esc(a.name)}</h1>
        <p class="role rise">${esc(a.title)}</p>
        <div class="creds rise">${a.credentials.map((c) => `<div class="cred"><b>${esc(c.title)}</b><span>${esc(c.detail)}</span></div>`).join("")}</div>
        <blockquote class="slash philosophy rise">${a.philosophy.map((l) => `<span>${esc(l)}</span>`).join("")}</blockquote>
        <div class="contact rise"><span><b>Τ.</b> ${esc(a.phone)}</span><span>${esc(a.email)}</span></div>
      </div></div>`;
  }

  function sHelp() {
    const h = S.content.help;
    return `<p class="eyebrow">${esc(S.content.screens[2].eyebrow)}</p><h1 class="title">${esc(h.title)}</h1><p class="lead">${esc(h.lead)}</p>
      <div class="cards3">${h.cards.map((c, i) => `
        <button class="pcard rise ${ui.help[i] ? "open" : ""}" data-act="help" data-i="${i}" aria-expanded="${ui.help[i] ? "true" : "false"}">
          ${forYou(c.axes)}<span class="num">${esc(c.number)}</span><h3>${esc(c.title)}</h3><p>${esc(c.text)}</p>
          <div class="example"><div><p>${esc(c.example)}</p></div></div>
          <span class="more">Ένα παράδειγμα ${ICON.down.replace("<svg", '<svg width="18" height="18"')}</span>
        </button>`).join("")}</div>`;
  }

  function explorer(section, key) {
    const topics = section.topics;
    const list = topics.map((t, i) => `<button class="topic ${ui[key] === i ? "active" : ""}" data-act="topic" data-key="${key}" data-i="${i}">
        <small>${esc(t.tag)}</small><b>${esc(t.title)}</b>${forYou(t.axes)}</button>`).join("");
    return `<div class="explorer"><nav class="topics rise" aria-label="Θέματα">${list}</nav><div id="detail">${topicDetail(topics[ui[key]], key)}</div></div>`;
  }

  function topicDetail(t, key) {
    if (key === "staff") {
      return `<article class="detail"><p class="eyebrow">${esc(t.tag)}</p><h2>${esc(t.title)}</h2>
        <p class="plain">${esc(t.logic)}</p>
        ${t.uses ? `<div class="uses">${t.uses.map((u, i) => `<div><b>0${i + 1}</b>${esc(u)}</div>`).join("")}</div>` : ""}
        <div class="example-box"><b>Για παράδειγμα</b>${esc(t.example)}</div></article>`;
    }
    return `<article class="detail"><p class="eyebrow">${esc(t.tag)}</p><h2>${esc(t.title)}</h2>
      <p class="plain">${esc(t.plain)}</p>
      <ul class="points">${t.points.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
      <div class="example-box"><b>Για παράδειγμα</b>${esc(t.example)}</div>
      ${t.term ? `<p class="term"><b>${esc(t.term.word)}:</b> ${esc(t.term.meaning)}</p>` : ""}
      ${t.diagram === "partners" ? partnerDiagram() : ""}</article>`;
  }

  function partnerDiagram() {
    const d = S.content.key_people.diagram;
    const mode = ui.diagram;
    return `<div class="diagram"><div class="seg" role="group" aria-label="Σενάριο">
        <button data-act="diagram" data-mode="without" class="${mode === "without" ? "on" : ""}">${esc(d.without.label)}</button>
        <button data-act="diagram" data-mode="with" class="${mode === "with" ? "on" : ""}">${esc(d.with.label)}</button></div>
      <div class="flow ${mode}">${d[mode].steps.map((s) => `<div>${esc(s)}</div>`).join("")}</div></div>`;
  }

  function sKeyPeople() {
    const k = S.content.key_people;
    return `<p class="eyebrow">${esc(S.content.screens[3].eyebrow)}</p><h1 class="title">${esc(k.title)}</h1><p class="lead">${esc(k.lead)}</p>${explorer(k, "key")}`;
  }

  function sStaff() {
    const s = S.content.staff;
    return `<p class="eyebrow">${esc(S.content.screens[4].eyebrow)}</p><h1 class="title">${esc(s.title)}</h1><p class="lead">${esc(s.lead)}</p>
      ${explorer(s, "staff")}<p class="note">${esc(s.note)}</p>`;
  }

  function sOperations() {
    const o = S.content.operations;
    return `<p class="eyebrow">${esc(S.content.screens[5].eyebrow)}</p><h1 class="title">${esc(o.title)}</h1><p class="lead">${esc(o.lead)}</p>
      <div class="grid6">${o.topics.map((t, i) => `
        <button class="ocard rise ${ui.ops[i] ? "open" : ""}" data-act="ops" data-i="${i}" aria-expanded="${ui.ops[i] ? "true" : "false"}">
          ${forYou(t.axes)}${ICON[t.icon] || ""}<h3>${esc(t.title)}</h3>
          <p class="txt">${esc(t.text)}</p><p class="ex"><b>Για παράδειγμα</b>${esc(t.example)}</p>
          <span class="tap">${ui.ops[i] ? "Πίσω στην περιγραφή" : "Δείτε ένα παράδειγμα"}</span></button>`).join("")}</div>
      <p class="slash" style="margin-top:22px">${esc(o.note)}</p>
      ${o.terms.map((t) => `<p class="note"><b>${esc(t.word)}:</b> ${esc(t.meaning)}</p>`).join("")}`;
  }

  function sQuestions() {
    const q = S.content.questions;
    return `<div class="q-head"><div><p class="eyebrow">${esc(S.content.screens[6].eyebrow)}</p><h1 class="title">${esc(q.title)}</h1></div>
      <div class="axes" id="axes">${axesChips()}</div></div>
      <p class="muted" style="margin:-6px 0 18px">${esc(q.lead)}</p>
      <div id="qzone">${qZone()}</div>`;
  }

  function axesChips() {
    const current = questions()[qIndex];
    const order = [];
    questions().forEach((q) => { if (!order.includes(q.axis)) order.push(q.axis); });
    return order.map((ax) => {
      const qs = questions().filter((q) => q.axis === ax);
      const done = qs.every((q) => answerOf(q.id));
      const cur = current && current.axis === ax;
      return `<button data-act="axis" data-axis="${ax}" class="${done ? "done" : ""} ${cur ? "current" : ""}">${esc(axisTitle(ax))}</button>`;
    }).join("");
  }

  function qZone() {
    const qs = questions();
    if (qIndex >= qs.length) {
      const open = qs.filter((q) => !answerOf(q.id)).length;
      return `<div class="qcard q-done"><div class="check-circle">${ICON.check}</div>
        <h2>Ευχαριστώ για τις απαντήσεις!</h2>
        <p>Συζητήσαμε ${S.flow.handled} από ${S.flow.total} θέματα. ${open ? `Μένουν ${open} ερωτήσεις — μπορούμε να επιστρέψουμε σε αυτές όποτε θέλετε.` : "Ας δούμε τι διαπιστώσαμε."}</p>
        <div class="q-actions" style="justify-content:center">${open ? `<button class="btn" data-act="first-open">Στις υπόλοιπες ερωτήσεις</button>` : ""}
        <button class="btn primary" data-act="next">Τι διαπιστώσαμε${ICON.right}</button></div></div>`;
    }
    const q = qs[qIndex];
    const a = answerOf(q.id);
    const status = a ? (a.status === "answered" ? "✓ Απαντήθηκε" : a.status === "unknown" ? "Δεν γνωρίζω" : "Παραλείφθηκε") : "";
    const note = ui.note[q.id] ?? (a && a.note) ?? "";
    const noteOpen = ui.noteOpen === q.id || Boolean(note);
    const needsSubmit = q.type === "multi" || q.type === "number";
    return `<div class="qcard" data-q="${esc(q.id)}">
      <p class="axis"><span>${esc(axisTitle(q.axis))}</span><span>${qIndex + 1} / ${qs.length}</span></p>
      ${q.hint ? `<p class="hint">${esc(q.hint)}</p>` : ""}
      <h2 id="qtext">${esc(q.text)}</h2>
      ${controls(q, a)}
      <div id="chart">${q.chart === "closure" ? closureChart(currentNumber(q, a)) : ""}</div>
      <div class="q-actions">
        ${q.allow_unknown ? `<button class="btn quiet ${a && a.status === "unknown" ? "on" : ""}" data-act="unknown">Δεν γνωρίζω</button>` : ""}
        <button class="btn quiet ${a && a.status === "skipped" ? "on" : ""}" data-act="skip">Παράλειψη</button>
        ${q.allow_note ? `<button class="btn quiet ${noteOpen ? "on" : ""}" data-act="note">Σχόλιο</button>` : ""}
        ${a ? `<button class="btn quiet" data-act="clear" title="Αναίρεση απάντησης">Αναίρεση</button>` : ""}
        <span class="spacer"></span><span class="q-status">${status}</span>
        ${needsSubmit ? `<button class="btn primary" data-act="submit" id="submit">Συνέχεια${ICON.right}</button>` : ""}
      </div>
      ${noteOpen ? `<div class="q-note"><textarea id="note" maxlength="500" placeholder="Σχόλιο για αυτή την ερώτηση (προαιρετικό)">${esc(note)}</textarea></div>` : ""}
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
    const value = currentNumber(q, a);
    const suggested = (answered == null && q.suggested != null && ui.draft[q.id] == null)
      ? `<p class="suggested">Από την προετοιμασία: ${esc(q.suggested)} — επιβεβαιώστε ή αλλάξτε.</p>` : "";
    return `<div class="number"><button class="step" data-act="step" data-d="-1" aria-label="Μείωση">−</button>
      <input id="num" inputmode="numeric" autocomplete="off" aria-labelledby="qtext" value="${value == null ? "" : esc(value)}" placeholder="0">
      <button class="step" data-act="step" data-d="1" aria-label="Αύξηση">+</button><span class="unit">${esc(q.unit || "")}</span></div>${suggested}`;
  }

  function currentNumber(q, a) {
    if (ui.draft[q.id] != null) return ui.draft[q.id];
    if (a && a.status === "answered" && typeof a.value === "number") return a.value;
    if (q.suggested != null && /^\d+$/.test(String(q.suggested))) return Number(q.suggested);
    return null;
  }

  function closureChart(amount, compact = false) {
    const costs = answerOf("ops.closure_costs");
    const q = questions().find((x) => x.id === "ops.closure_costs");
    const labels = costs && costs.status === "answered" && q
      ? costs.value.map((v) => (q.options.find((o) => o.value === v) || {}).label).filter(Boolean) : [];
    if (!amount) {
      return compact ? "" : `<div class="chart"><h4>Τι σημαίνει ένας μήνας χωρίς έσοδα</h4>
        <p class="muted">Συμπληρώστε ένα ποσό για να δούμε μαζί το μέγεθος.</p>
        ${labels.length ? `<div class="costs">${labels.map((l) => `<span>${esc(l)}</span>`).join("")}</div>` : ""}</div>`;
    }
    const n = ui.months;
    const rows = [[1, "1 μήνας"], [3, "3 μήνες"], [n, `${n} μήνες`]];
    const max = Math.max(...rows.map((r) => r[0])) * amount;
    return `<div class="chart"><h4>Τα σταθερά έξοδα σε μια διακοπή εργασιών</h4>
      <p class="muted">Ενδεικτικός υπολογισμός με το ποσό που αναφέρατε: μηνιαία σταθερά έξοδα × μήνες διακοπής.</p>
      ${labels.length ? `<div class="costs">${labels.map((l) => `<span>${esc(l)}</span>`).join("")}</div>` : ""}
      <div class="bars">${rows.map(([m, label]) => `<div class="bar"><span>${label}</span><div class="track"><div class="fill" style="width:${(m * amount / max) * 100}%"></div></div><b>${money(m * amount)}</b></div>`).join("")}</div>
      <label class="muted" style="display:block;margin-top:10px">Διάρκεια διακοπής: <b id="months">${n}</b> μήνες
        <input type="range" min="1" max="12" step="1" value="${n}" data-range="months" aria-label="Μήνες διακοπής"></label></div>`;
  }

  function sFindings() {
    const f = S.content.findings;
    const head = `<p class="eyebrow">${esc(S.content.screens[7].eyebrow)}</p><h1 class="title">${esc(f.title)}</h1>`;
    if (!S.flow.handled) {
      return `${head}<div class="empty-state"><p class="lead" style="margin:0 auto 20px">${esc(f.empty)}</p>
        <button class="btn primary" data-act="goto" data-i="${QUESTIONS}">Στις ερωτήσεις</button></div>`;
    }
    const legend = S.levels.map((l) => `<span class="lv-${l.id}"><i></i>${esc(l.label)}</span>`).join("");
    const cols = S.pillars.map((p) => {
      const tiles = S.needs.filter((n) => n.pillar === p.id).map((n) =>
        `<button class="tile ${n.level} ${ui.need === n.id ? "sel" : ""}" data-act="need" data-id="${n.id}"><span>${esc(n.title)}</span><small>${esc(n.level_label)}</small></button>`).join("");
      return `<div class="col"><h3><b>${esc(p.number)}</b>${esc(p.title)}</h3><div class="tiles">${tiles}</div></div>`;
    }).join("");
    const confirmed = S.needs.filter((n) => n.level === "confirmed");
    const shown = confirmed.length ? confirmed : S.needs.filter((n) => n.level === "possible").slice(0, 3);
    const pr = shown.length ? `<div class="priorities"><h3>${confirmed.length ? "Οι προτεραιότητές σας" : "Θέματα που αξίζει να εξετάσουμε"}</h3>
      <ul>${shown.map((n) => `<li>${ICON.check}<span>${esc(n.statement)}</span></li>`).join("")}</ul></div>` : "";
    const fixed = answerOf("ops.monthly_fixed");
    const chart = fixed && fixed.status === "answered" ? `<div id="chart">${closureChart(fixed.value, true)}</div>` : "";
    return `${head}<p class="lead">${esc(f.lead)}</p><div class="legend">${legend}</div><div class="map">${cols}</div>
      <div id="need-detail">${needDetail()}</div>${pr}${chart}`;
  }

  function needDetail() {
    const n = S.needs.find((x) => x.id === ui.need);
    if (!n) return "";
    const ev = n.evidence.length
      ? `<p class="lbl">Με βάση όσα συζητήσαμε</p><ul>${n.evidence.map((e) => `<li>${esc(e.label)}: ${esc(e.answer)}</li>`).join("")}</ul>`
      : `<p class="lbl">Δεν έχουμε ακόμη απαντήσεις για αυτό το θέμα</p>`;
    return `<div class="need-detail"><p class="lbl">${esc(n.level_label)}</p><h3>${esc(n.title)}</h3><p>${esc(n.statement)}</p>${ev}</div>`;
  }

  function sSolutions() {
    const c = S.content.solutions;
    const head = `<p class="eyebrow">${esc(S.content.screens[8].eyebrow)}</p><h1 class="title">${esc(c.title)}</h1><p class="lead">${esc(c.lead)}</p>`;
    if (!S.recommendations.length) {
      return `${head}<div class="empty-state"><p class="lead" style="margin:0 auto">${esc(c.empty)}</p></div>
        <p class="disclaimer">${esc(S.solution_labels.disclaimer)}</p>`;
    }
    const cards = S.recommendations.map((r, i) => {
      const status = r.products.length
        ? `<div class="status-pill doc">${esc(r.status_label)}${r.products.map((p) => `<small><b>${esc(p.name)}</b>${p.provider ? ` · ${esc(p.provider)}` : ""}</small>`).join("")}</div>`
        : `<div class="status-pill">${esc(r.status_label)}</div>`;
      const tab = ui.solTab[i] || "benefits";
      return `<article class="sol"><div class="need"><span>${esc(r.need_title)}</span><span class="badge">${esc(r.level_label)}</span></div>
        <h3>${esc(r.title)}</h3>
        <p class="lbl">Γιατί έχει σημασία</p><p>${esc(r.why)}</p>
        <p class="lbl">Κατεύθυνση προστασίας</p><p>${esc(r.direction)}</p>
        ${status}
        <div class="tabs"><button data-act="soltab" data-i="${i}" data-tab="benefits" class="${tab === "benefits" ? "on" : ""}">Πιθανά οφέλη</button>
          <button data-act="soltab" data-i="${i}" data-tab="examine" class="${tab === "examine" ? "on" : ""}">Τι εξετάζουμε πρώτα</button></div>
        <div id="sol-${i}">${solTab(r, tab)}</div></article>`;
    }).join("");
    const more = S.more_topics.length
      ? `<div class="more-topics"><b class="muted">Επίσης για επόμενη συζήτηση:</b>${S.more_topics.map((t) => `<span>${esc(t)}</span>`).join("")}</div>` : "";
    return `${head}<div class="sols">${cards}</div>${more}<p class="disclaimer">${esc(S.solution_labels.disclaimer)}</p>`;
  }

  function solTab(r, tab) {
    if (tab === "examine") {
      const limits = r.products.flatMap((p) => p.limitations);
      return `<ul>${r.examine.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        ${limits.length ? `<p class="lbl">Περιορισμοί από τους όρους</p><ul>${limits.map((l) => `<li>${esc(l.text)} <span class="muted">(${esc(l.source)})</span></li>`).join("")}</ul>` : ""}`;
    }
    const documented = r.products.flatMap((p) => p.benefits);
    return `<ul>${r.benefits.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      ${documented.length ? `<p class="lbl">Από τους όρους του προϊόντος</p><ul>${documented.map((b) => `<li>${esc(b.text)} <span class="muted">(${esc(b.source)})</span></li>`).join("")}</ul>` : ""}`;
  }

  function sNext() {
    const n = S.content.next;
    const s = S.summary.content;
    const list = (items) => (items && items.length ? `<ul>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : `<p class="muted">—</p>`);
    const a = S.content.advisor;
    return `<p class="eyebrow">${esc(S.content.screens[9].eyebrow)}</p><h1 class="title">${esc(n.title)}</h1>
      <div class="next-grid">
        <section class="rise"><h3>Τι συζητήσαμε</h3>${list(s.topics)}</section>
        <section class="rise"><h3>Ποιες ανάγκες εντοπίσαμε</h3>${list(s.priorities)}</section>
        <section class="rise"><h3>Τι χρειάζεται να διερευνήσουμε</h3>${list(s.information_needed)}</section>
      </div>
      <h3 class="display" style="font-size:22px;margin:0 0 40px">Πώς προχωράμε</h3>
      <div class="process">${n.process.map((p, i) => `<div class="${i === 0 ? "now" : ""}"><b>${esc(p.number)}</b><strong>${esc(p.title)}</strong><span>${esc(p.text)}</span></div>`).join("")}</div>
      <div class="closing"><div><h2>${n.closing.map(esc).join("<br>")}</h2><p>${esc(a.phone)} · ${esc(a.email)}</p></div>
        <div class="acts"><button class="btn" data-act="summary">Προβολή περίληψης</button>
        <button class="btn dark" data-act="export">Εξαγωγή PDF</button></div></div>`;
  }

  const SCREENS = [sWelcome, sAbout, sHelp, sKeyPeople, sStaff, sOperations, sQuestions, sFindings, sSolutions, sNext];

  /* ----- overlays ----------------------------------------------------------------------------- */

  function overlayHtml() {
    if (overlay === "summary") {
      const s = S.summary.content;
      const list = (items, tag = "ul") => (items && items.length ? `<${tag}>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</${tag}>` : `<p class="muted">—</p>`);
      return `<div class="overlay" data-act="close-overlay"><div class="sheet" role="dialog" aria-modal="true" aria-label="Περίληψη συνάντησης">
        <p class="eyebrow">Περίληψη συνάντησης</p><h2>${esc(s.business_name || "Η επιχείρησή σας")}</h2><p class="muted">${greekDate(s.meeting_date)}</p>
        <h4>Τι συζητήσαμε</h4>${list(s.topics)}
        <h4>Οι προτεραιότητες που αναδείχθηκαν</h4>${list(s.priorities)}
        <h4>Προτεινόμενες κατευθύνσεις</h4>${(s.directions || []).map((d) => `<div class="dir"><b>${esc(d.title)}</b>${d.need ? `<br><span class="muted">${esc(d.need)}</span>` : ""}<br>${esc(d.why)}${d.solution ? `<br><i class="muted">${esc(d.solution)}</i>` : ""}</div>`).join("") || '<p class="muted">—</p>'}
        <h4>Τι χρειάζεται να συγκεντρώσουμε</h4>${list(s.information_needed)}
        <h4>Τα επόμενα βήματα</h4>${list(s.next_steps, "ol")}
        <div class="acts"><button class="btn quiet" data-act="close-overlay">Κλείσιμο</button><button class="btn dark" data-act="export">Εξαγωγή PDF</button></div>
      </div></div>`;
    }
    if (overlay === "approve") {
      return `<div class="overlay" data-act="close-overlay"><div class="sheet" role="dialog" aria-modal="true" aria-label="Έγκριση περίληψης">
        <p class="eyebrow">Έλεγχος από τον σύμβουλο</p><h2>Έγκριση πριν από την εξαγωγή</h2>
        <p>Η περίληψη εξάγεται σε PDF μόνο αφού ο σύμβουλος ελέγξει το περιεχόμενό της. Για αλλαγές στο κείμενο χρησιμοποιήστε την επεξεργασία περίληψης στο περιβάλλον του συμβούλου.</p>
        <label><input type="checkbox" id="approve-check"> Έχω ελέγξει το περιεχόμενο της περίληψης και εγκρίνω την εξαγωγή.</label>
        <div class="acts"><button class="btn quiet" data-act="close-overlay">Άκυρο</button><button class="btn primary" data-act="approve" id="approve-btn" disabled>Έγκριση & εξαγωγή PDF</button></div>
      </div></div>`;
    }
    if (overlay === "exit") {
      return `<div class="overlay" data-act="close-overlay"><div class="sheet" role="dialog" aria-modal="true" aria-label="Έξοδος">
        <h2>Έξοδος από την παρουσίαση;</h2><p class="muted">Η πρόοδος και οι απαντήσεις έχουν αποθηκευτεί.</p>
        <div class="acts"><button class="btn quiet" data-act="close-overlay">Συνέχεια παρουσίασης</button><button class="btn dark" data-act="end">Έξοδος</button></div>
      </div></div>`;
    }
    return "";
  }

  function openOverlay(name) { overlay = name; render(false); }
  function closeOverlay() { overlay = null; render(false); }

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
      overlay = null;
      render(false);
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
    const label = document.getElementById("plabel");
    if (label) label.textContent = `Συζητήσαμε ${S.flow.handled} από ${S.flow.total}`;
    focusQuestion();
  }

  function focusQuestion() {
    const card = document.querySelector(".qcard");
    if (!card) return;
    const first = card.querySelector("#num, .opt.on, .opt, .btn.primary");
    if (first && window.matchMedia("(pointer: fine)").matches) first.focus({ preventScroll: true });
  }

  function currentQuestion() { return questions()[qIndex]; }

  async function submitCurrent() {
    const q = currentQuestion();
    if (!q) return;
    if (q.type === "multi") {
      const value = ui.draft[q.id] || [];
      if (!value.length) { saved("Επιλέξτε τουλάχιστον μία απάντηση", true); return; }
      if (await answer(q.id, "answered", value)) next();
    } else if (q.type === "number") {
      const raw = (document.getElementById("num") || {}).value || "";
      const digits = raw.replace(/[^\d]/g, "");
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
      case "start": toggleFullscreen(true); go(1, "next"); break;
      case "fullscreen": toggleFullscreen(); break;
      case "exit": openOverlay("exit"); break;
      case "end":
        overlay = null;
        window.close();
        setTimeout(() => { ended = true; render(false); }, 150);
        break;
      case "resume": ended = false; render(true); break;
      case "help":
        ui.help[el.dataset.i] = !ui.help[el.dataset.i];
        el.classList.toggle("open", ui.help[el.dataset.i]);
        el.setAttribute("aria-expanded", String(ui.help[el.dataset.i]));
        break;
      case "topic": {
        const key = el.dataset.key;
        ui[key] = Number(el.dataset.i);
        document.querySelectorAll(".topic").forEach((t) => t.classList.toggle("active", t === el));
        const section = key === "key" ? S.content.key_people : S.content.staff;
        patch("detail", topicDetail(section.topics[ui[key]], key));
        break;
      }
      case "diagram":
        ui.diagram = el.dataset.mode;
        el.closest(".diagram").outerHTML = partnerDiagram();
        break;
      case "ops": {
        const i = el.dataset.i;
        ui.ops[i] = !ui.ops[i];
        el.classList.toggle("open", ui.ops[i]);
        el.setAttribute("aria-expanded", String(ui.ops[i]));
        el.querySelector(".tap").textContent = ui.ops[i] ? "Πίσω στην περιγραφή" : "Δείτε ένα παράδειγμα";
        break;
      }
      case "axis": {
        const ax = el.dataset.axis;
        const qs = questions();
        let i = qs.findIndex((x) => x.axis === ax && !answerOf(x.id));
        if (i < 0) i = qs.findIndex((x) => x.axis === ax);
        if (i >= 0) { qIndex = i; patchQuestions(); savePosition(); }
        break;
      }
      case "first-open": qIndex = firstOpen(); patchQuestions(); savePosition(); break;
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
        const big = q && /€/.test(q.unit || "");
        const now = Number((input.value || "0").replace(/[^\d]/g, "")) || 0;
        const val = Math.max(0, now + Number(el.dataset.d) * (big ? 500 : 1));
        input.value = String(val);
        ui.draft[q.id] = val;
        if (q.chart === "closure") patch("chart", closureChart(val));
        break;
      }
      case "unknown": if (q && await answer(q.id, "unknown", null)) setTimeout(next, 200); break;
      case "skip": if (q && await answer(q.id, "skipped", null)) setTimeout(next, 200); break;
      case "clear": if (q) clearAnswer(q.id); break;
      case "note":
        if (!q) break;
        ui.noteOpen = ui.noteOpen === q.id ? null : q.id;
        patch("qzone", qZone());
        document.getElementById("note")?.focus();
        break;
      case "need":
        ui.need = ui.need === el.dataset.id ? null : el.dataset.id;
        document.querySelectorAll(".tile").forEach((t) => t.classList.toggle("sel", t.dataset.id === ui.need));
        patch("need-detail", needDetail());
        break;
      case "soltab": {
        const i = Number(el.dataset.i);
        ui.solTab[i] = el.dataset.tab;
        el.parentElement.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === el));
        patch(`sol-${i}`, solTab(S.recommendations[i], ui.solTab[i]));
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
      if (q.chart === "closure") {
        const chart = document.getElementById("chart");
        if (chart) chart.innerHTML = closureChart(ui.draft[q.id]);
      }
    } else if (t.id === "note" && q) {
      ui.note[q.id] = t.value;
      clearTimeout(noteTimer);
      const a = answerOf(q.id);
      if (a) noteTimer = setTimeout(() => answer(q.id, a.status, a.value).then(() => {}), 700);
    } else if (t.dataset.range === "months") {
      ui.months = Number(t.value);
      const host = t.closest("#chart");
      const amount = screen === QUESTIONS ? ui.draft["ops.monthly_fixed"] ?? (answerOf("ops.monthly_fixed") || {}).value
        : (answerOf("ops.monthly_fixed") || {}).value;
      if (host) {
        host.innerHTML = closureChart(amount, screen !== QUESTIONS);
        host.querySelector("input[type=range]")?.focus();
      }
    } else if (t.id === "approve-check") {
      document.getElementById("approve-btn").disabled = !t.checked;
    }
  });

  document.addEventListener("keydown", (ev) => {
    if (!S || ended) return;
    const tag = (ev.target.tagName || "").toLowerCase();
    const typing = tag === "input" || tag === "textarea";
    if (ev.key === "Escape" && overlay) { closeOverlay(); return; }
    if (overlay) return;
    if (ev.key === "Enter" && ev.target.id === "num") { ev.preventDefault(); submitCurrent(); return; }
    if (typing) return;
    if (ev.key === "ArrowRight" || ev.key === "PageDown") { ev.preventDefault(); next(); }
    if (ev.key === "ArrowLeft" || ev.key === "PageUp") { ev.preventDefault(); prev(); }
    if (ev.key === "f" || ev.key === "F") toggleFullscreen();
  });

  let touch = null;
  app.addEventListener("touchstart", (ev) => {
    const t = ev.touches[0];
    touch = ev.target.closest("input, textarea, .bars, .topics") ? null : { x: t.clientX, y: t.clientY };
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
      if (screen === QUESTIONS) {
        const i = questions().findIndex((q) => q.id === S.position.question);
        qIndex = i >= 0 ? i : firstOpen();
      }
    }
    document.title = S.business.business_name ? `${S.business.business_name} · Παρουσίαση` : "Παρουσίαση";
    render(true);
  })();
})();
