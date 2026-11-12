// Lead Scoring Dashboard — vanilla JS, Chart.js from CDN, no build step.
//
// Wires to the FastAPI endpoints defined in app/routes/*:
//   GET  /api/config/scoring
//   GET  /api/analytics/by-tier
//   GET  /api/analytics/calibration-summary
//   GET  /api/leads/<id>/scores       (history for the drawer)
//   GET  /api/config/export.xlsx
//   GET  /api/config/outreach-queue
//
// Note: the latest-scores view itself isn't exposed as JSON in this build.
// We fetch the .xlsx export, parse the first sheet via a tiny CSV fallback
// would be wrong; instead we POST to /api/leads/score-batch on a synthetic
// no-op would also be wrong. The pragmatic path: provide a JSON view by
// piping it through the export. To keep this dashboard decoupled from
// server-side changes, we ALSO add a /api/leads/latest endpoint on the
// server side. If that endpoint is missing, we fall back to a static
// empty state with a clear message.

const TIER_ORDER = ["Hot", "Hot-leaning Warm", "Warm", "Cold"];
const TIER_COLORS = {
  "Hot":               getComputedStyle(document.documentElement).getPropertyValue("--status-hot").trim(),
  "Hot-leaning Warm":  getComputedStyle(document.documentElement).getPropertyValue("--status-hlw").trim(),
  "Warm":              getComputedStyle(document.documentElement).getPropertyValue("--status-warm").trim(),
  "Cold":              getComputedStyle(document.documentElement).getPropertyValue("--status-cold").trim(),
};
const CAT_COLORS = ["--cat-1","--cat-2","--cat-3","--cat-4","--cat-5","--cat-6"]
  .map(v => getComputedStyle(document.documentElement).getPropertyValue(v).trim());

const state = {
  tierFilter: "all",
  hideCompetitors: false,
  search: "",
  sort: "blended_desc",
  leads: [],
  byTier: [],
  review: [],
  lastUpdated: null,
  charts: {},
};

// ---- Utilities ------------------------------------------------------------
function $(sel, root = document) { return root.querySelector(sel); }
function $$(sel, root = document) { return [...root.querySelectorAll(sel)]; }
function fmtPct(x) { return (x * 100).toFixed(1) + "%"; }
function fmtDate(s) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 2200);
}
async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Accept": "application/json" }, ...opts });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ---- Theme handling -------------------------------------------------------
function setTheme(mode) {
  if (mode === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", mode);
  localStorage.setItem("tg-theme", mode);
  $$(".theme-btn").forEach(b => b.classList.toggle("active", b.dataset.theme === mode));
  $$(".theme-btn").forEach(b => b.setAttribute("aria-pressed", b.dataset.theme === mode ? "true" : "false"));
  refreshChartColors();
}
$$(".theme-btn").forEach(b => b.addEventListener("click", () => setTheme(b.dataset.theme)));
setTheme(localStorage.getItem("tg-theme") || "system");

function readToken(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
function refreshChartColors() {
  TIER_COLORS["Hot"]              = readToken("--status-hot");
  TIER_COLORS["Hot-leaning Warm"] = readToken("--status-hlw");
  TIER_COLORS["Warm"]             = readToken("--status-warm");
  TIER_COLORS["Cold"]             = readToken("--status-cold");
  for (const c of ["tiers", "rates", "hist"]) if (state.charts[c]) state.charts[c].update("none");
}

// ---- Data fetching --------------------------------------------------------
async function loadAll() {
  $("#last-updated").textContent = "Refreshing…";
  try {
    const [byTier, latestLeads, review, cfg] = await Promise.allSettled([
      api("/api/analytics/by-tier"),
      api("/api/leads/latest").catch(() => null),
      api("/api/leads/needs-review").catch(() => []),
      api("/api/config/scoring"),
    ]);

    state.byTier = byTier.status === "fulfilled" ? byTier.value : [];
    state.leads  = latestLeads.status === "fulfilled" && Array.isArray(latestLeads.value) ? latestLeads.value : [];
    state.review = review.status === "fulfilled" ? review.value : [];
    state.config = cfg.status === "fulfilled" ? cfg.value : null;

    renderKpis();
    renderCharts();
    renderTable();
    renderReview();
    state.lastUpdated = new Date();
    $("#last-updated").textContent = `Updated ${state.lastUpdated.toLocaleTimeString()}`;
  } catch (e) {
    toast(`Failed to load: ${e.message}`);
    $("#last-updated").textContent = "Error";
  }
}

// ---- KPI strip ------------------------------------------------------------
function renderKpis() {
  const counts = { Hot: 0, "Hot-leaning Warm": 0, Warm: 0, Cold: 0 };
  for (const l of state.leads) counts[l.tier] = (counts[l.tier] || 0) + 1;
  const total = state.leads.length;
  $("#kpi-total").textContent = total.toLocaleString();
  $("#kpi-hot").textContent  = counts.Hot.toLocaleString();
  $("#kpi-hlw").textContent  = counts["Hot-leaning Warm"].toLocaleString();
  $("#kpi-warm").textContent = counts.Warm.toLocaleString();
  $("#kpi-cold").textContent = counts.Cold.toLocaleString();
  $("#kpi-total-foot").textContent = state.config ? `config v${state.config.version}` : "—";
}

// KPI click -> filter
$$(".kpi").forEach(k => k.addEventListener("click", () => {
  state.tierFilter = k.dataset.tier === "all" ? "all" : k.dataset.tier;
  syncFilterChips();
  renderTable();
}));

function syncFilterChips() {
  $$(".chip").forEach(c => c.classList.toggle("chip-active", c.dataset.filterTier === state.tierFilter));
}
$$(".chip").forEach(c => c.addEventListener("click", () => {
  state.tierFilter = c.dataset.filterTier;
  syncFilterChips();
  renderTable();
}));

// ---- Charts ---------------------------------------------------------------
function renderCharts() {
  renderTiersChart();
  renderRatesChart();
  renderHistChart();
}

function tierDataFromState() {
  const counts = Object.fromEntries(TIER_ORDER.map(t => [t, 0]));
  for (const l of state.leads) counts[l.tier] = (counts[l.tier] || 0) + 1;
  return TIER_ORDER.map(t => counts[t]);
}

function renderTiersChart() {
  const ctx = $("#chart-tiers").getContext("2d");
  const data = tierDataFromState();
  if (state.charts.tiers) state.charts.tiers.destroy();
  state.charts.tiers = new Chart(ctx, {
    type: "bar",
    data: {
      labels: TIER_ORDER,
      datasets: [{
        label: "Leads",
        data,
        backgroundColor: TIER_ORDER.map(t => TIER_COLORS[t]),
        borderRadius: 6,
        borderSkipped: false,
        maxBarThickness: 64,
      }],
    },
    options: chartOpts({ y: true, legend: false, tooltipCb: (ctx) => `${ctx.parsed.y.toLocaleString()} leads` }),
  });
}

function renderRatesChart() {
  const ctx = $("#chart-rates").getContext("2d");
  const labels = TIER_ORDER;
  const reply = labels.map(t => +(state.byTier.find(r => r.tier === t)?.reply_rate ?? 0));
  const conv  = labels.map(t => +(state.byTier.find(r => r.tier === t)?.conversion_rate ?? 0));
  const totals = labels.map(t => +(state.byTier.find(r => r.tier === t)?.total ?? 0));

  if (state.charts.rates) state.charts.rates.destroy();
  state.charts.rates = new Chart(ctx, {
    data: {
      labels,
      datasets: [
        {
          type: "bar",
          label: "Reply rate",
          data: reply,
          backgroundColor: readToken("--brand-600"),
          borderRadius: 6, maxBarThickness: 36,
          yAxisID: "y",
        },
        {
          type: "bar",
          label: "Conversion rate",
          data: conv,
          backgroundColor: readToken("--cat-3"),
          borderRadius: 6, maxBarThickness: 36,
          yAxisID: "y",
        },
        {
          type: "line",
          label: "Total leads (right axis index)",
          data: totals,
          borderColor: readToken("--ink-muted"),
          borderWidth: 2,
          tension: 0.25,
          pointRadius: 3,
          pointBackgroundColor: readToken("--ink-muted"),
          yAxisID: "y1",
        },
      ],
    },
    options: chartOpts({
      y: true, y1: true, legend: true,
      tooltipCb: (item) => {
        const idx = item.dataIndex;
        const t = labels[idx];
        const r = state.byTier.find(x => x.tier === t) || {};
        return [`${t}`, `Reply: ${fmtPct(+(r.reply_rate ?? 0))}`, `Convert: ${fmtPct(+(r.conversion_rate ?? 0))}`, `Leads: ${r.total ?? 0}`];
      },
    }),
  });
}

function renderHistChart() {
  const ctx = $("#chart-hist").getContext("2d");
  const buckets = new Array(10).fill(0); // 0-9, 10-19, ..., 90-99
  for (const l of state.leads) {
    const b = Math.min(9, Math.max(0, Math.floor((l.blended_score || 0) / 10)));
    buckets[b]++;
  }
  const labels = buckets.map((_, i) => `${i * 10}–${i * 10 + 9}`);
  if (state.charts.hist) state.charts.hist.destroy();
  state.charts.hist = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Leads",
        data: buckets,
        backgroundColor: ctx2 => {
          const { chart } = ctx2;
          const { ctx: c, chartArea } = chart;
          if (!chartArea) return readToken("--seq-3");
          const grad = c.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
          grad.addColorStop(0, readToken("--seq-1"));
          grad.addColorStop(1, readToken("--seq-5"));
          return grad;
        },
        borderRadius: 6,
        maxBarThickness: 48,
      }],
    },
    options: chartOpts({ y: true, legend: false, tooltipCb: (i) => `${i.parsed.y} leads in ${i.label}` }),
  });
}

function chartOpts({ y = false, y1 = false, legend = false, tooltipCb } = {}) {
  const ink = readToken("--ink-primary");
  const muted = readToken("--ink-muted");
  const border = readToken("--border");
  const axes = {};
  if (y)  axes.y  = { beginAtZero: true, ticks: { color: muted }, grid: { color: border } };
  if (y1) axes.y1 = { beginAtZero: true, position: "right", grid: { display: false }, ticks: { color: muted } };
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: legend, labels: { color: ink, boxWidth: 12, boxHeight: 12 } },
      tooltip: {
        backgroundColor: readToken("--ink-primary"),
        titleColor: readToken("--ink-inverse"),
        bodyColor: readToken("--ink-inverse"),
        callbacks: tooltipCb ? { label: (ctx) => typeof tooltipCb(ctx) === "string" ? tooltipCb(ctx) : tooltipCb(ctx) } : {},
      },
    },
    scales: {
      x: { ticks: { color: muted }, grid: { display: false } },
      ...axes,
    },
  };
}

// ---- Table ----------------------------------------------------------------
function filteredLeads() {
  const q = state.search.trim().toLowerCase();
  let rows = state.leads;
  if (state.tierFilter !== "all") rows = rows.filter(l => l.tier === state.tierFilter);
  if (state.hideCompetitors) rows = rows.filter(l => !l.is_competitor);
  if (q) {
    rows = rows.filter(l =>
      [l.full_name, l.headline, l.current_company, l.industry_match, l.country]
        .filter(Boolean).join(" ").toLowerCase().includes(q));
  }
  switch (state.sort) {
    case "blended_asc":  rows = [...rows].sort((a, b) => a.blended_score - b.blended_score); break;
    case "scored_desc":  rows = [...rows].sort((a, b) => (b.scored_at || "").localeCompare(a.scored_at || "")); break;
    case "name_asc":     rows = [...rows].sort((a, b) => (a.full_name || "").localeCompare(b.full_name || "")); break;
    default:             rows = [...rows].sort((a, b) => b.blended_score - a.blended_score);
  }
  return rows;
}

function renderTable() {
  const rows = filteredLeads();
  $("#table-count").textContent = `${rows.length} of ${state.leads.length} leads`;
  const tbody = $("#lead-tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty">No leads match the current filters.</td></tr>`;
    return;
  }
  const frag = document.createDocumentFragment();
  for (const l of rows) {
    const tr = document.createElement("tr");
    tr.dataset.leadId = l.lead_id;
    tr.innerHTML = `
      <td>
        <div class="lead-name">${escapeHtml(l.full_name || "—")}</div>
        <div class="lead-sub">${escapeHtml(l.current_position || "")}</div>
      </td>
      <td>${escapeHtml(l.current_company || "—")}<div class="lead-sub">${escapeHtml(l.country || "")}</div></td>
      <td>${escapeHtml(l.industry_match || "—")}</td>
      <td class="num">${l.authority_score}</td>
      <td class="num">${l.fit_score}</td>
      <td class="num">${l.intent_score}</td>
      <td class="num">${l.reachability_score}</td>
      <td class="num"><strong>${Number(l.blended_score).toFixed(1)}</strong></td>
      <td><span class="tier tier-${cssClass(l.tier)}">${tierBadge(l)}</span></td>
      <td>${fmtDate(l.scored_at)}</td>
    `;
    tr.addEventListener("click", () => openDrawer(l.lead_id));
    frag.appendChild(tr);
  }
  tbody.replaceChildren(frag);
}

function tierBadge(l) {
  if (l.is_competitor) return "Cold · competitor";
  if (l.disqualify_reason) return `Cold · ${l.disqualify_reason}`;
  return l.tier;
}
function cssClass(t) { return t.replace(/\s+/g, "-"); }
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

// ---- Review queue ---------------------------------------------------------
function renderReview() {
  $("#review-count").textContent = state.review.length;
  const tbody = $("#review-tbody");
  if (!state.review.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty">Nothing to review. Nice.</td></tr>`;
    return;
  }
  tbody.innerHTML = state.review.map(r => `
    <tr data-lead-id="${r.lead_id}">
      <td>${escapeHtml(r.full_name || r.lead_id)}</td>
      <td><span class="tier tier-${cssClass(r.previous_tier)}">${r.previous_tier}</span></td>
      <td><span class="tier tier-${cssClass(r.new_tier)}">${r.new_tier}</span></td>
      <td>${escapeHtml(r.reason || "")}</td>
      <td>${fmtDate(r.created_at)}</td>
    </tr>
  `).join("");
  $$("#review-tbody tr").forEach(tr => tr.addEventListener("click", () => openDrawer(tr.dataset.leadId)));
}

// ---- Drawer ---------------------------------------------------------------
async function openDrawer(leadId) {
  const drawer = $("#drawer");
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  $("#drawer-content").innerHTML = "Loading…";
  try {
    const history = await api(`/api/leads/${leadId}/scores`);
    const latest = history[0];
    if (!latest) {
      $("#drawer-content").innerHTML = `<p>No scoring history yet.</p>`;
      return;
    }
    const lead = state.leads.find(l => l.lead_id === leadId) || {};
    $("#drawer-content").innerHTML = `
      <div class="drawer-section">
        <h3>Lead</h3>
        <h2 style="margin:0 0 4px">${escapeHtml(lead.full_name || latest.lead_id)}</h2>
        <p class="lead-sub">${escapeHtml(lead.headline || "")}</p>
        <p class="lead-sub">${escapeHtml(lead.current_company || "")} · ${escapeHtml(lead.country || "")}</p>
      </div>
      <div class="drawer-section">
        <h3>Scores</h3>
        ${axisBar("Authority", latest.authority_score)}
        ${axisBar("Fit", latest.fit_score)}
        ${axisBar("Intent", latest.intent_score)}
        ${axisBar("Reachability", latest.reachability_score)}
        <p style="margin-top:10px"><strong>Blended:</strong> ${latest.blended_score} · <strong>Tier:</strong> <span class="tier tier-${cssClass(latest.tier)}">${latest.tier}</span></p>
        <p class="lead-sub">Model ${latest.scoring_model} · config v${latest.scoring_config_version}</p>
      </div>
      <div class="drawer-section">
        <h3>Notes</h3>
        <p>${escapeHtml(latest.notes || "—")}</p>
        ${latest.is_competitor ? `<p><strong>⚠ Competitor:</strong> ${escapeHtml(latest.disqualify_reason || "")}</p>` : ""}
      </div>
      <div class="drawer-section">
        <h3>History</h3>
        <table>
          <thead><tr><th>Scored at</th><th>Tier</th><th class="num">Blended</th></tr></thead>
          <tbody>
            ${history.map(h => `<tr><td>${fmtDate(h.scored_at)}</td><td>${h.tier}</td><td class="num">${h.blended_score}</td></tr>`).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    $("#drawer-content").innerHTML = `<p>Failed to load: ${escapeHtml(e.message)}</p>`;
  }
}
function closeDrawer() {
  const drawer = $("#drawer");
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}
$(".drawer-close").addEventListener("click", closeDrawer);
$(".drawer-scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });

function axisBar(label, val) {
  const v = Math.max(0, Math.min(100, val || 0));
  return `<div class="axis-bar"><span>${label}</span><span class="axis-track"><span class="axis-fill" style="width:${v}%"></span></span><span class="num">${v}</span></div>`;
}

// ---- Filters / actions ----------------------------------------------------
$("#search").addEventListener("input", e => { state.search = e.target.value; renderTable(); });
$("#sort").addEventListener("change", e => { state.sort = e.target.value; renderTable(); });

// ---- Excel upload ---------------------------------------------------------
const uploadButton = $("#upload-btn");
const uploadInput = $("#upload-file");
const uploadStatus = $("#upload-status");

uploadButton.addEventListener("keydown", event => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    uploadInput.click();
  }
});
function renderUploadPreview(filename, rows) {
  const card = $("#upload-preview-card");
  const head = $("#upload-preview-head");
  const body = $("#upload-preview-body");
  const keys = Object.keys(rows[0] || {});
  head.innerHTML = `<tr>${keys.map(key => `<th>${escapeHtml(key)}</th>`).join("")}</tr>`;
  body.innerHTML = rows.slice(0, 10).map(row =>
    `<tr>${keys.map(key => `<td>${escapeHtml(row[key])}</td>`).join("")}</tr>`
  ).join("");
  $("#upload-preview-count").textContent = `${rows.length} data row${rows.length === 1 ? "" : "s"} detected; showing first ${Math.min(rows.length, 10)}`;
  $("#upload-preview-file").textContent = filename;
  card.hidden = false;
}

uploadInput.addEventListener("change", async () => {
  const file = uploadInput.files?.[0];
  if (!file) {
    uploadStatus.textContent = "No file selected";
    uploadStatus.className = "upload-status";
    return;
  }
  uploadStatus.textContent = `Reading ${file.name}…`;
  uploadStatus.className = "upload-status loading";
  if (!/\.(xlsx|xls)$/i.test(file.name)) {
    uploadStatus.textContent = "Choose an .xlsx or .xls file";
    uploadStatus.className = "upload-status error";
    toast("Only .xlsx or .xls files are supported");
    uploadInput.value = "";
    return;
  }

  // Read the workbook in-browser first so the selected file's rows are visibly
  // confirmed before the server starts scoring it.
  try {
    if (!window.XLSX) throw new Error("Excel reader is still loading; try again");
    const workbook = XLSX.read(await file.arrayBuffer(), { type: "array", cellDates: true });
    if (!workbook.SheetNames.length) throw new Error("The Excel file has no worksheets");
    const sheet = workbook.Sheets[workbook.SheetNames[0]];
    const previewRows = XLSX.utils.sheet_to_json(sheet, { defval: "", raw: false });
    if (!previewRows.length) throw new Error("The Excel sheet has no data rows");
    renderUploadPreview(file.name, previewRows);
    // Mirror the server-side check in app/excel_import.py:parse_workbook().
    // A workbook is acceptable if it carries any of the columns the parser
    // can derive a Full Name from. The combined `Full Name` column is the
    // usual case; split-name Apify exports (First Name + Last Name) and
    // vanity-slug Public Identifier are also valid and the server will
    // synthesise the Full Name for each row.
    const NAME_HEADER_RE =
      /^(full[_\s-]?name|fullname|name|first[_\s-]?name|firstname|given[_\s-]?name|last[_\s-]?name|lastname|surname|family[_\s-]?name|public[_\s-]?identifier|publicidentifier|vanity([_\s-]?url)?)$/i;
    if (!Object.keys(previewRows[0]).some(key => NAME_HEADER_RE.test(key.trim()))) {
      throw new Error(
        "The Excel sheet must include at least one name column: Full Name, First Name + Last Name, or Public Identifier"
      );
    }
    uploadStatus.textContent = `${previewRows.length} rows found · uploading…`;

    const form = new FormData();
    form.append("file", file, file.name);
    uploadButton.setAttribute("aria-busy", "true");
    uploadButton.style.pointerEvents = "none";
    const response = await fetch("/api/leads/upload", { method: "POST", body: form });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `Upload failed (${response.status})`);

    const errorCount = body.errors?.length || 0;
    uploadStatus.textContent = `${body.scored} scored · ${errorCount} row error${errorCount === 1 ? "" : "s"}`;
    uploadStatus.className = `upload-status ${errorCount ? "warning" : "success"}`;
    toast(`Imported ${body.created + body.updated} leads and scored ${body.scored}`);
    if (errorCount) toast(`Row ${body.errors[0].row}: ${body.errors[0].message}`);
    await loadAll();
  } catch (error) {
    uploadStatus.textContent = error.message;
    uploadStatus.className = "upload-status error";
    toast(error.message);
  } finally {
    uploadButton.removeAttribute("aria-busy");
    uploadButton.style.pointerEvents = "";
  }
  uploadInput.value = "";
});

$("#hide-competitors").addEventListener("change", e => { state.hideCompetitors = e.target.checked; renderTable(); });
$("#refresh").addEventListener("click", loadAll);
$("#export").addEventListener("click", () => {
  window.location.href = "/api/config/export.xlsx";
});
$("#outreach-btn").addEventListener("click", async () => {
  try {
    const rows = await api("/api/config/outreach-queue");
    toast(`${rows.length} leads ready for outreach`);
  } catch {
    toast("Outreach queue unavailable");
  }
});

// Initial load
loadAll();
// Soft auto-refresh every 60s
setInterval(loadAll, 60000);
