// Poker AI Tournament Lab — local UI (stage B). No external resources; data written with textContent only.
(() => {
  "use strict";

  // ---------- access token: arrives in the URL fragment, kept only in this tab's session ----------
  const TKEY = "lab-token";
  const m = location.hash.match(/(?:^#|&)t=([A-Za-z0-9_-]{32,})/);
  if (m) {
    try { sessionStorage.setItem(TKEY, m[1]); } catch (_) { /* private mode: keep in memory */ }
    window.__labToken = m[1];
    history.replaceState(null, "", location.pathname + "#inicio");
  }
  const token = () => { try { return sessionStorage.getItem(TKEY) || window.__labToken || ""; } catch (_) { return window.__labToken || ""; } };

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const pct = (x, d = 1) => (x === null || x === undefined ? "—" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(d)}%`);
  const pct0 = (x) => (x === null || x === undefined ? "—" : `${(x * 100).toFixed(1)}%`);
  const num3 = (x) => (x === null || x === undefined ? "—" : `${x >= 0 ? "+" : ""}${x.toFixed(3)}`);
  const int = (x) => (x === null || x === undefined ? "—" : Number(x).toLocaleString("pt-BR"));

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      ...opts,
      headers: { "X-Lab-Token": token(), "Content-Type": "application/json", ...(opts.headers || {}) },
      cache: "no-store",
    });
    if (res.status === 401) { $("#auth-error").hidden = false; throw new Error("sem acesso"); }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || body.detail || `erro ${res.status}`);
    return body;
  }

  function cell(tr, text, cls) { const td = document.createElement("td"); td.textContent = text; if (cls) td.className = cls; tr.append(td); return td; }
  function kv(dl, pairs) {
    dl.replaceChildren();
    for (const [k, v, cls] of pairs) {
      const dt = document.createElement("dt"); dt.textContent = k;
      const dd = document.createElement("dd"); dd.textContent = v; if (cls) dd.className = cls;
      dl.append(dt, dd);
    }
  }

  // ---------- routing ----------
  const pages = ["inicio", "simulacao", "sessoes", "historico", "analise", "config", "verificar"];
  const loaded = new Set();
  function route() {
    const name = pages.includes(location.hash.slice(1)) ? location.hash.slice(1) : "inicio";
    $$("[data-page]").forEach((s) => { s.hidden = s.dataset.page !== name; });
    $$("[data-route]").forEach((a) => a.setAttribute("aria-current", a.dataset.route === name ? "page" : "false"));
    const loaders = { inicio: loadHome, simulacao: loadSim, sessoes: loadSessions, historico: loadHistory, analise: loadAnalysis, config: loadConfig, verificar: loadVerify };
    if (!loaded.has(name) || name === "verificar" || name === "sessoes") { loaded.add(name); loaders[name]().catch(showErr); }
  }
  function showErr(e) { console.warn(e); }
  window.addEventListener("hashchange", route);
  $$(".tile.disabled").forEach((t) => t.addEventListener("click", (ev) => ev.preventDefault()));

  // ---------- status polling ----------
  const STATE_LABEL = {
    desconectado: "Desconectado", conectado: "Conectado", aguardando: "Aguardando mão", jogando: "Jogando",
    pausado: "Pausado", encerrado: "Encerrado", erro: "Erro", ocioso: "Ocioso", autonomo: "Autônomo",
    pausando: "Pausando…", supervisionado: "Pausado (supervisionado)", sincronizando: "Sincronizando",
    parado_qualidade: "Parado por qualidade", saindo_apos_mao: "Encerrando após a mão", emergencia: "Emergência",
  };
  const LABEL = { adequada: "adequada", provavel_erro_estrategico: "provável erro", erro_tecnico: "erro técnico", inconclusiva: "inconclusiva" };
  async function pollStatus() {
    try {
      const s = await api("/api/status");
      const p = $("#agent-state");
      p.dataset.state = s.agent_state;
      p.textContent = STATE_LABEL[s.agent_state] || s.agent_state;
      $("#online-state").textContent = s.online.kill_switch_set ? "Online: desativada · kill switch ativo" : "Online: desativada na aplicação";
      $("#job-state").hidden = !s.active_job;
      $("#app-version").textContent = s.app_version;
    } catch (e) { showErr(e); }
  }


  // ---------- simulation (stage C) ----------
  const PROFILES = ["tag", "lag", "nit", "station", "random", "adaptive_tag", "adaptive_lag", "bluffer40", "bluffer60", "maniac"];
  const chosen = new Set(["tag", "lag", "nit", "station", "adaptive_tag"]);
  let simTimer = null;
  const ci = (c) => (c && c.low !== null && c.low !== undefined ? `${c.low.toFixed(1)} a ${c.high.toFixed(1)}` : "amostra pequena");
  const bb = (x) => (x === null || x === undefined ? "—" : `${x >= 0 ? "+" : ""}${Number(x).toFixed(1)}`);
  function actionText(a) { return a ? (a.amount ? `${a.kind} ${a.amount}` : a.kind) : "—"; }

  async function loadSim() {
    const box = $("#s-profiles");
    if (!box.childElementCount) {
      box.className = "chips";
      for (const p of PROFILES) {
        const b = document.createElement("button");
        b.type = "button"; b.className = "chip"; b.textContent = p; b.setAttribute("aria-pressed", chosen.has(p));
        b.addEventListener("click", () => {
          if (chosen.has(p)) chosen.delete(p); else if (chosen.size < 5) chosen.add(p);
          b.setAttribute("aria-pressed", chosen.has(p));
        });
        box.append(b);
      }
      $("#s-confirm").addEventListener("change", (e) => { $("#s-start").disabled = !e.target.checked; });
      $("#s-start").addEventListener("click", startSim);
      $("#b-pause").addEventListener("click", () => simCmd("pause"));
      $("#b-resume").addEventListener("click", () => simCmd("resume"));
      $("#b-finish").addEventListener("click", () => simCmd("finish", { mode: "after_hand" }));
      $("#b-emergency").addEventListener("click", () => simCmd("emergency"));
      $("#b-ack").addEventListener("click", () => simCmd("ack-quality", { confirm: $("#q-confirm").checked, note: $("#q-note").value }));
    }
    await refreshSim();
  }

  async function startSim() {
    const msg = $("#s-msg");
    if (!chosen.size) { msg.textContent = "Escolha ao menos um adversário."; return; }
    const body = {
      confirm: $("#s-confirm").checked, hands: Number($("#s-hands").value), seed: Number($("#s-seed").value),
      stack_bb: Number($("#s-stack").value), ante_bb: Number($("#s-ante").value), max_minutes: Number($("#s-min").value),
      opponents: [...chosen],
    };
    $("#s-start").disabled = true;
    try { await api("/api/simulation/start", { method: "POST", body: JSON.stringify(body) }); msg.textContent = "Sessão iniciada."; }
    catch (e) { msg.textContent = e.message; }
    $("#s-confirm").checked = false;
    await refreshSim();
  }

  async function simCmd(cmd, body) {
    try { await api(`/api/simulation/${cmd}`, { method: "POST", body: JSON.stringify(body || {}) }); }
    catch (e) { $("#s-msg").textContent = e.message; }
    await refreshSim();
    pollStatus();
  }

  async function refreshSim() {
    const { session: s } = await api("/api/simulation/current");
    const has = !!s;
    $("#sim-live").hidden = !has; $("#sim-metrics").hidden = !has; $("#sim-recent").hidden = !has;
    if (!has) return;
    const st = s.control.state;
    $("#l-id").textContent = s.session_id;
    const pill = $("#l-state"); pill.dataset.state = st; pill.textContent = STATE_LABEL[st] || st;
    const done = s.summary.hands_played;
    $("#l-bar").style.width = `${Math.min(100, (100 * done) / s.hands_target)}%`;
    kv($("#l-kv"), [
      ["Mãos", `${int(done)} de ${int(s.hands_target)}${s.summary.hands_aborted ? ` · ${s.summary.hands_aborted} interrompida` : ""}`],
      ["Tempo", `${Math.round(s.elapsed_s)} s`],
      ["Decisões", `${int(s.summary.decisions)} (${int(s.control.committed)} enviadas · ${int(s.control.discarded)} descartadas)`],
      ["Política", `${s.policy} · sha256 ${s.policy_sha256.slice(0, 12)}…`],
      ["Adversários", s.config.opponents.join(", ")],
      ["Motivo de parada", s.control.stop_reason || (s.error || "—")],
    ]);
    const running = s.running, terminal = ["encerrado", "emergencia", "erro"].includes(st);
    $("#b-pause").disabled = !running || !["autonomo", "saindo_apos_mao"].includes(st);
    $("#b-resume").disabled = !running || st !== "supervisionado";
    $("#b-finish").disabled = !running || terminal || st === "saindo_apos_mao";
    $("#b-emergency").disabled = !running || terminal;
    $("#l-quality-stop").hidden = st !== "parado_qualidade";
    $("#l-qs-reason").textContent = s.control.stop_reason || "";
    const q = s.quality;
    kv($("#q-kv"), [
      ["Avaliáveis na janela", `${q.evaluable}${q.sample_ok ? "" : " (abaixo do mínimo de 50)"}`],
      ["Adequadas", q.adequacy === null ? "—" : `${pct0(q.adequacy)} (IC 95% ${pct0(q.adequacy_ci[0])} a ${pct0(q.adequacy_ci[1])})`, q.target_reached ? "good" : ""],
      ["Prováveis erros", q.error_rate === null ? "—" : `${pct0(q.error_rate)} (limite inferior 99%: ${pct0(q.error_lower_99)})`],
      ["Inconclusivas (fora da janela)", int(q.inconclusive_total)],
      ["Erros técnicos", int(q.technical_total)],
      ["Perda de EV estimada", s.summary.ev_loss_bb.n ? `${s.summary.ev_loss_bb.total} bb em ${s.summary.ev_loss_bb.n} spots com referência` : "sem spots com referência ainda"],
    ]);
    const tb = $("#r-pos tbody"); tb.replaceChildren();
    const rows = [["Total", s.summary.bb_per_100]]
      .concat(Object.entries(s.summary.by_position).map(([k, v]) => [`Posição ${k}`, v]))
      .concat(Object.entries(s.summary.by_opponent).map(([k, v]) => [`vs ${k}`, v]));
    for (const [k, v] of rows) { const tr = document.createElement("tr"); cell(tr, k); cell(tr, int(v.n), "num"); cell(tr, bb(v.mean), "num"); cell(tr, ci(v), "num"); tb.append(tr); }
    const td = $("#r-dec tbody"); td.replaceChildren();
    for (const d of s.recent_decisions) {
      const tr = document.createElement("tr");
      cell(tr, d.hand, "num"); cell(tr, d.street); cell(tr, d.position); cell(tr, actionText(d.action));
      cell(tr, LABEL[d.label] || d.label, `lbl-${d.label}`); cell(tr, d.reason);
      td.append(tr);
    }
    clearTimeout(simTimer);
    if (running && location.hash === "#simulacao") simTimer = setTimeout(() => refreshSim().catch(showErr), 1000);
  }
  window.addEventListener("hashchange", () => { if (location.hash === "#simulacao") refreshSim().catch(showErr); });

  // ---------- sessions & hand viewer ----------
  let curSession = null, handOffset = 0;
  async function loadSessions() {
    const { sessions } = await api("/api/sessions");
    const tb = $("#ss-table tbody"); tb.replaceChildren();
    if (!sessions.length) { const tr = document.createElement("tr"); cell(tr, "Nenhuma sessão ainda. Inicie uma em Simulação.").colSpan = 7; tb.append(tr); }
    for (const s of sessions) {
      const tr = document.createElement("tr"); tr.className = "click"; tr.tabIndex = 0;
      cell(tr, (s.created_at || "").replace("T", " ").slice(0, 19)); cell(tr, s.session_id); cell(tr, STATE_LABEL[s.state] || s.state);
      cell(tr, `${int(s.hands_played)}/${int(s.hands_target)}`, "num");
      cell(tr, s.bb_per_100 ? `${bb(s.bb_per_100.mean)} (${ci(s.bb_per_100)})` : "—", "num");
      cell(tr, s.labels ? Object.entries(s.labels).map(([k, v]) => `${LABEL[k] || k}: ${v}`).join(" · ") : "—");
      cell(tr, s.stop_reason || "—");
      const open = () => { curSession = s.session_id; handOffset = 0; $("#ss-hands tbody").replaceChildren(); loadSessionAnalysis(s.session_id).catch(showErr); loadHands().catch(showErr); };
      tr.addEventListener("click", open); tr.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
      tb.append(tr);
    }
  }
  const rate = (r) => (r.rate === null ? "—" : `${pct0(r.rate)} (IC 95% ${pct0(r.ci95[0])} a ${pct0(r.ci95[1])}; n=${r.n})`);
  async function loadSessionAnalysis(id) {
    const a = await api(`/api/sessions/${encodeURIComponent(id)}/analysis`);
    $("#ss-analysis").hidden = false;
    $("#sa-note").textContent = a.notes.join(" ");
    kv($("#sa-kv"), [
      ["Decisões", `${int(a.decisions)} em ${int(a.hands_played)} mãos`],
      ["Cobertura com referência", rate(a.coverage)],
      ["Adequadas (avaliáveis)", rate(a.adequacy)],
      ["Prováveis erros (avaliáveis)", rate(a.error_rate)],
      ["Inconclusivas por motivo", Object.entries(a.inconclusive_reasons).map(([k, v]) => `${k}: ${v}`).join(" · ") || "—"],
      ["Falhas técnicas", int(a.technical.length)],
    ]);
    const tb = $("#sa-worst tbody"); tb.replaceChildren();
    if (!a.worst_decisions.length) { const tr = document.createElement("tr"); cell(tr, "Nenhuma decisão com perda de EV estimada.").colSpan = 6; tb.append(tr); }
    for (const w of a.worst_decisions) { const tr = document.createElement("tr"); cell(tr, w.hand_no, "num"); cell(tr, w.spot); cell(tr, w.class); cell(tr, w.chosen); cell(tr, w.best); cell(tr, w.ev_gap_bb, "num"); tb.append(tr); }
    const ul = $("#sa-rec"); ul.replaceChildren();
    const recs = a.recommendations.length ? a.recommendations.map((r) => `${r.pattern}: erros ${rate(r.evidence)}; ${r.status}. ${r.next_step}.`) : ["Nenhum padrão com amostra suficiente. A política da sessão nunca é alterada automaticamente."];
    for (const t of recs) { const li = document.createElement("li"); li.textContent = t; ul.append(li); }
  }
  async function loadHands() {
    $("#ss-hands-card").hidden = false; $("#ss-id").textContent = curSession;
    const { hands } = await api(`/api/sessions/${encodeURIComponent(curSession)}/hands?offset=${handOffset}&limit=100`);
    handOffset += hands.length;
    $("#ss-more").hidden = hands.length < 100;
    const tb = $("#ss-hands tbody");
    for (const h of hands) {
      const tr = document.createElement("tr"); tr.className = "click"; tr.tabIndex = 0;
      cell(tr, h.hand_no, "num"); cell(tr, h.hero_position || "—");
      cell(tr, h.aborted ? "interrompida" : bb(h.net_bb), "num"); cell(tr, h.final_street || "—");
      cell(tr, h.labels.length ? h.labels.map((l) => LABEL[l] || l).join(", ") : "sem decisão");
      const open = () => showHand(h.hand_id, h.hand_no).catch(showErr);
      tr.addEventListener("click", open); tr.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
      tb.append(tr);
    }
  }
  $("#ss-more").addEventListener("click", () => loadHands().catch(showErr));
  async function showHand(id, no) {
    const h = await api(`/api/hands/${encodeURIComponent(id)}`);
    $("#hand-card").hidden = false; $("#h-no").textContent = `#${no}`;
    const box = $("#h-dec"); box.replaceChildren();
    if (!h.decision_time.length) { const p = document.createElement("p"); p.className = "note"; p.textContent = "O agente não precisou decidir nesta mão."; box.append(p); }
    for (const d of h.decision_time) {
      const div = document.createElement("div"); div.className = "dec";
      const o = d.observation;
      const head = document.createElement("div");
      head.textContent = `${d.street} · ${d.position} · pote ${o.pot} · para pagar ${o.to_call} · stack ${o.stack} → ${actionText(d.applied)}`;
      const lab = document.createElement("div"); lab.className = `lbl-${d.label}`; lab.textContent = `${LABEL[d.label] || d.label}: ${d.assessment.reason}`;
      const meta = document.createElement("div"); meta.className = "meta";
      const a = d.assessment;
      meta.textContent = [a.ev_chosen_bb !== null && a.ev_chosen_bb !== undefined ? `EV escolhido ${a.ev_chosen_bb} bb · melhor ${a.ev_best_bb} bb (${a.best_action})` : null,
        a.confidence ? `confiança ${a.confidence}` : null, (a.limitations || []).join("; ") || null].filter(Boolean).join(" · ");
      div.append(head, lab, meta); box.append(div);
    }
    kv($("#h-rev"), h.revealed_after_hand.map((r) => [r.profile === "hero" ? "Agente" : `Assento ${r.seat} (${r.profile})`, r.cards]));
    kv($("#h-res"), [["Resultado do agente", h.hand.aborted ? "mão interrompida" : `${bb(h.hand.net_bb)} bb`], ["Rua final", h.hand.final_street || "—"], ["Showdown", h.hand.showdown ? "sim" : "não"]]);
    $("#hand-card").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------- home ----------
  async function loadHome() {
    const runs = await api("/api/runs");
    const p7c = runs.known.find((r) => r.key === "P7c");
    const detail = p7c && p7c.report_present ? await api("/api/runs/P7c") : null;
    $("#home-champion").textContent = detail ? `${detail.baseline} (P7c)` : "—";
    const pairs = [];
    for (const r of runs.known) {
      pairs.push([r.key, `${int(r.tournaments)} torneios no banco · esperado ${int(r.expected_tournaments)} · ${r.db_present ? "banco presente" : "banco ausente"}`]);
    }
    if (detail) pairs.push(["Champion, cenário principal P7c", `ROI ${pct(detail.baseline_roi)} [${pct(detail.baseline_roi_low)}; ${pct(detail.baseline_roi_high)}]`]);
    kv($("#home-summary"), pairs);
  }

  // ---------- history ----------
  async function loadHistory() {
    const runs = await api("/api/runs");
    const tb = $("#runs-table tbody"); tb.replaceChildren();
    for (const r of runs.known) {
      const tr = document.createElement("tr");
      cell(tr, r.key); cell(tr, r.question); cell(tr, String(r.seed), "num");
      cell(tr, int(r.tournaments), "num"); cell(tr, int(r.expected_tournaments), "num");
      cell(tr, r.db_present ? `${r.db} (${int(r.db_size_mb)} MB)` : "ausente nesta máquina", r.db_present ? "" : "warn");
      const d = Object.entries(r.decisions || {}).map(([k, v]) => `${k}: ${v}`).join(" · ");
      cell(tr, d || "—");
      tb.append(tr);
    }
    const db = $("#dbs-table tbody"); db.replaceChildren();
    for (const d of runs.databases) {
      const tr = document.createElement("tr");
      cell(tr, d.path); cell(tr, int(d.size_mb), "num"); cell(tr, d.schema_version ?? "—", "num"); cell(tr, d.frozen ? "sim" : "não");
      db.append(tr);
    }
  }

  // ---------- analysis ----------
  let anRun = null;
  async function loadAnalysis() {
    const runs = await api("/api/runs");
    const sel = $("#an-run"); sel.replaceChildren();
    for (const r of runs.known.filter((x) => x.report_present)) sel.append(new Option(r.title, r.key));
    sel.value = "P7c";
    sel.onchange = () => showRun(sel.value);
    await showRun(sel.value);
  }
  async function showRun(key) {
    anRun = await api(`/api/runs/${encodeURIComponent(key)}`);
    const sc = $("#an-scen"); sc.replaceChildren();
    for (const s of anRun.scenarios) sc.append(new Option(s === anRun.primary_scenario ? `${s} (principal)` : s, s));
    sc.value = anRun.primary_scenario;
    sc.onchange = () => showScenario(key, sc.value);
    await showScenario(key, sc.value);
  }
  async function showScenario(key, scen) {
    const d = await api(`/api/runs/${encodeURIComponent(key)}/scenario/${encodeURIComponent(scen)}`);
    $("#an-title").textContent = `${key} · ${scen}`;
    const dec = Object.entries(anRun.decisions || {}).map(([k, v]) => `${k}: ${v.decision}`).join(" · ");
    $("#an-note").textContent = `Champion nesta execução: ${anRun.baseline}. Seed raiz ${anRun.seed}. ${dec ? "Regra de promoção: " + dec + "." : ""} ROI esperado com habilidade igual: −9,1%. n < 200 = amostra insuficiente.`;
    const tb = $("#an-roi tbody"); tb.replaceChildren();
    for (const r of d.table) {
      const tr = document.createElement("tr");
      cell(tr, r.candidate); cell(tr, int(r.n), "num");
      cell(tr, pct(r.roi), r.roi_low > 0 ? "num good" : r.roi_high < 0 ? "num bad" : "num");
      cell(tr, `[${pct(r.roi_low)}; ${pct(r.roi_high)}]`, "num"); cell(tr, r.verdict); cell(tr, pct0(r.itm), "num");
      tb.append(tr);
    }
    drawForest($("#an-roi-chart"), d.table, anRun.baseline);
    const cb = $("#an-cmp tbody"); cb.replaceChildren();
    for (const r of d.compare) {
      const tr = document.createElement("tr");
      cell(tr, r.candidate);
      cell(tr, num3(r.diff), r.low > 0 ? "num good" : r.high < 0 ? "num bad" : "num");
      cell(tr, `[${num3(r.low)}; ${num3(r.high)}]`, "num"); cell(tr, int(r.n), "num");
      cell(tr, r.p_holm === null ? "—" : r.p_holm.toFixed(4), "num"); cell(tr, r.relevance); cell(tr, r.decision || "—");
      cb.append(tr);
    }
  }

  // forest plot (SVG, theme colors via CSS classes)
  function drawForest(el, rows, champ) {
    const NS = "http://www.w3.org/2000/svg";
    const W = 760, rowH = 28, left = 170, right = 70, top = 10, bottom = 30;
    const H = top + bottom + rowH * rows.length;
    const vals = rows.flatMap((r) => [r.roi_low, r.roi_high]).concat([-10 / 110, 0]);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.06; lo -= pad; hi += pad;
    const x = (v) => left + ((v - lo) / (hi - lo)) * (W - left - right);
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const mk = (tag, attrs, text) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (text !== undefined) e.textContent = text; svg.append(e); return e; };
    const step = (hi - lo) > 1.2 ? 0.5 : 0.25;
    for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) {
      mk("line", { x1: x(t), x2: x(t), y1: top, y2: H - bottom, class: "grid" });
      mk("text", { x: x(t), y: H - bottom + 18, "text-anchor": "middle" }, `${Math.round(t * 100)}%`);
    }
    mk("line", { x1: x(0), x2: x(0), y1: top, y2: H - bottom, class: "zero" });
    mk("line", { x1: x(-10 / 110), x2: x(-10 / 110), y1: top, y2: H - bottom, class: "ref" });
    rows.forEach((r, i) => {
      const y = top + rowH * i + rowH / 2;
      const c = r.candidate === champ ? " champ" : "";
      mk("text", { x: left - 10, y: y + 4, "text-anchor": "end" }, r.candidate);
      mk("line", { x1: x(r.roi_low), x2: x(r.roi_high), y1: y, y2: y, class: "ci" + c });
      mk("circle", { cx: x(r.roi), cy: y, r: 5, class: "pt" + c });
      mk("text", { x: x(r.roi_high) + 8, y: y + 4 }, pct(r.roi));
    });
    el.replaceChildren(svg);
  }

  // ---------- config ----------
  const FIELDS = [
    ["#c-tour", "simulation", "max_tournaments_per_job"], ["#c-hands", "simulation", "max_hands_per_session"],
    ["#c-min", "simulation", "max_job_minutes"], ["#o-hands", "online", "max_hands"], ["#o-min", "online", "max_minutes"],
    ["#o-buy", "online", "buy_in"], ["#o-margin", "online", "resume_safety_margin_s"],
  ];
  let cfgCache = null;
  async function loadConfig() {
    cfgCache = await api("/api/config");
    for (const [sel, grp, key] of FIELDS) $(sel).value = cfgCache[grp][key];
    $("#c-low").checked = !!cfgCache.simulation.low_priority;
  }
  $("#c-save").addEventListener("click", async () => {
    const msg = $("#c-msg");
    const body = structuredClone(cfgCache);
    for (const [sel, grp, key] of FIELDS) body[grp][key] = Number($(sel).value);
    body.simulation.low_priority = $("#c-low").checked;
    try {
      cfgCache = await api("/api/config", { method: "PUT", body: JSON.stringify(body) });
      msg.textContent = "Salvo."; msg.className = "msg good";
    } catch (e) { msg.textContent = `Não salvo: ${e.message}`; msg.className = "msg bad"; }
  });

  // ---------- verify ----------
  async function loadVerify() {
    const h = await api("/api/health");
    const env = h.environment;
    const deps = Object.entries(env.dependencies).map(([k, v]) => `${k} ${v || "AUSENTE"}`).join(", ");
    kv($("#v-env"), [
      ["Python", `${env.python} ${env.python_ok ? "(ok)" : "(precisa 3.12+)"}`, env.python_ok ? "good" : "bad"],
      ["Dependências", deps, env.dependencies_ok ? "" : "bad"],
      ["Disco livre", `${h.disk_free_gb} GB`],
      ["Integração online", "desativada (etapa E)"],
    ]);
    showFrozen(h.frozen);
    const tb = $("#v-runs tbody"); tb.replaceChildren();
    for (const r of h.runs) {
      const tr = document.createElement("tr");
      cell(tr, r.key); cell(tr, r.db_present ? r.db : "ausente", r.db_present ? "" : "warn");
      cell(tr, r.db_present ? `${int(r.tournaments)} / ${int(r.expected_tournaments)}` : "—", "num");
      cell(tr, r.count_ok === null ? "—" : r.count_ok ? "confere" : "diverge", r.count_ok ? "good" : r.count_ok === false ? "bad" : "");
      const td = cell(tr, "");
      if (r.db_present) {
        const b = document.createElement("button"); b.textContent = "Verificar integridade completa";
        b.addEventListener("click", () => startVerify(r.key, b)); td.append(b);
      }
      tb.append(tr);
    }
  }
  function showFrozen(f) {
    kv($("#v-frozen"), [
      ["Resultado", f.passed ? "íntegros" : "DIVERGÊNCIA", f.passed ? "good" : "bad"],
      ["Arquivos verificados", int(f.checked)],
      ["Alterados", (f.changed || []).join(", ") || "nenhum", (f.changed || []).length ? "bad" : ""],
      ["Ausentes", (f.missing || []).join(", ") || "nenhum", (f.missing || []).length ? "bad" : ""],
    ]);
  }
  $("#v-frozen-btn").addEventListener("click", async () => { try { showFrozen(await api("/api/verify/frozen", { method: "POST" })); } catch (e) { showErr(e); } });
  async function startVerify(key, btn) {
    const log = $("#v-job"); log.hidden = false;
    btn.disabled = true;
    try {
      let job = await api(`/api/verify/run/${encodeURIComponent(key)}`, { method: "POST" });
      while (job.status === "queued" || job.status === "running") {
        log.textContent = job.progress.join("\n");
        await new Promise((r) => setTimeout(r, 1500));
        job = await api(`/api/jobs/${job.id}`);
      }
      if (job.status === "done") {
        const lines = Object.entries(job.result.checks).map(([k, v]) => `${v.ok ? "OK  " : "FALHA"} ${k}`);
        log.textContent = `${key}: ${job.result.ok ? "INTEGRIDADE CONFIRMADA" : "PROBLEMAS ENCONTRADOS"}\n` + lines.join("\n");
      } else {
        log.textContent = `${key}: falhou — ${job.error}`;
      }
    } catch (e) { log.textContent = `Não iniciou: ${e.message}`; }
    btn.disabled = false;
  }

  // ---------- boot ----------
  if (!token()) $("#auth-error").hidden = false;
  route();
  pollStatus();
  setInterval(pollStatus, 3000);
})();
