const PIPE_COLS = [
  { key: "tesseract", label: "Tesseract", version: "classical OCR" },
  { key: "easyocr", label: "EasyOCR", version: "deep OCR" },
  { key: "vlm-gemini", label: "Gemini", version: "3.5 Flash-Lite" },
];

const FIELDS = ["merchant", "date", "total"];
const FIELD_LABEL = { merchant: "Merchant", date: "Date", total: "Total" };

const state = {
  receipts: [],
  selected: new Set(),
  currentId: null,
  summaries: [],
  live: {},
  running: false,
  view: "leaderboard",
};

const els = {
  form: document.getElementById("run-form"),
  runBtn: document.getElementById("run-btn"),
  sampleCount: document.getElementById("sample-count"),
  stageEmpty: document.getElementById("stage-empty"),
  stageFrame: document.getElementById("stage-frame"),
  photoWell: document.getElementById("photo-well"),
  methodsBody: document.getElementById("methods-body"),
  summary: document.getElementById("summary"),
  warnings: document.getElementById("warnings"),
  compareBody: document.getElementById("compare-body"),
  receiptTabs: document.getElementById("receipt-tabs"),
  metaCard: document.getElementById("meta-card"),
  scoreCard: document.getElementById("score-card"),
  status: document.getElementById("status"),
  pipeVlm: document.getElementById("pipe-vlm"),
  viewLeaderboard: document.getElementById("view-leaderboard"),
  viewGallery: document.getElementById("view-gallery"),
};

function pct(value) {
  if (value == null) return "";
  return `${(value * 100).toFixed(1)}%`;
}

function num(value, digits = 3) {
  if (value == null || Number.isNaN(value)) return "";
  return Number(value).toFixed(digits);
}

function setStatus(text, isError = false) {
  els.status.textContent = text;
  els.status.classList.toggle("is-error", isError);
}

function selectedPipes() {
  return [...document.querySelectorAll('input[name="pipe"]:checked')].map((el) => el.value);
}

function stageImage() {
  let img = document.getElementById("stage-image");
  if (!img) {
    img = document.createElement("img");
    img.id = "stage-image";
    img.alt = "";
    els.stageFrame.prepend(img);
  }
  return img;
}

function displayOf(pipeline) {
  return PIPE_COLS.find((col) => col.key === pipeline)?.label || pipeline;
}

async function boot() {
  const [receiptsRes, boardRes, healthRes] = await Promise.all([
    fetch("/api/receipts"),
    fetch("/api/leaderboard"),
    fetch("/api/health"),
  ]);
  const receiptsData = await receiptsRes.json();
  const board = await boardRes.json();
  const health = await healthRes.json();

  state.receipts = receiptsData.receipts || [];
  state.summaries = board.summaries || [];
  els.sampleCount.max = Math.max(1, state.receipts.filter((r) => r.has_image).length);
  const preset = Math.min(Number(els.sampleCount.value) || 8, els.sampleCount.max);
  els.sampleCount.value = String(preset);
  selectFirst(preset);
  if (!health.vlm_ready) {
    els.pipeVlm.disabled = true;
    els.pipeVlm.closest("label").title = "Set GEMINI_API_KEY in .env to enable Gemini.";
  }
  renderAll();
  const labeled = health.labeled ?? 0;
  const images = health.with_image ?? 0;
  if (images === 0) {
    setStatus("No receipt images on disk. Run: uv run python scripts/download_sroie.py --n 50");
  } else {
    setStatus(`${labeled} labeled, ${images} with images.`);
  }
}

function renderAll() {
  renderSummary();
  renderMethods();
  renderTabs();
  showCurrent(state.currentId);
  renderCompare();
  renderMeta();
}

function selectFirst(n) {
  state.selected = new Set(
    state.receipts.filter((r) => r.has_image).slice(0, n).map((r) => r.id)
  );
  state.currentId = [...state.selected][0] || state.receipts[0]?.id || null;
}

function rankedSummaries() {
  return [...state.summaries].sort(
    (a, b) => (b.macro_precision ?? -1) - (a.macro_precision ?? -1)
  );
}

function renderSummary() {
  const rows = rankedSummaries();
  if (!rows.length) {
    els.summary.innerHTML = "";
    return;
  }
  const bestAcc = rows[0];
  const fastest = [...rows].sort(
    (a, b) => (a.latency?.mean_s ?? 99) - (b.latency?.mean_s ?? 99)
  )[0];
  const cheapest = [...rows].sort(
    (a, b) => (a.cost_list_usd ?? 0) - (b.cost_list_usd ?? 0)
  )[0];
  const cells = [
    {
      label: "Best accuracy",
      value: pct(bestAcc.macro_precision),
      who: bestAcc.display || bestAcc.pipeline,
      rank: "1st",
      rankClass: "",
    },
    {
      label: "Fastest mean",
      value: `${num(fastest.latency?.mean_s, 2)}`,
      suffix: "s",
      who: fastest.display || fastest.pipeline,
      rank: rankLabel(rows, fastest.pipeline),
      rankClass: rankClass(rows, fastest.pipeline),
    },
    {
      label: "Docs in this readout",
      value: String(bestAcc.n_documents ?? ""),
      who: "Same labeled slice for every method",
      rank: "",
      rankClass: "",
    },
  ];
  els.summary.innerHTML = cells
    .map(
      (cell) => `
      <article class="stat">
        <p class="stat-label">${escapeHtml(cell.label)}</p>
        <div class="stat-value">${escapeHtml(cell.value)}${cell.suffix ? `<span>${escapeHtml(cell.suffix)}</span>` : ""}</div>
        <div class="stat-who">${cell.rank ? `<span class="badge ${cell.rankClass}">${escapeHtml(cell.rank)}</span>` : ""}<span>${escapeHtml(cell.who)}</span></div>
      </article>`
    )
    .join("");
}

function rankLabel(rows, pipeline) {
  const i = rows.findIndex((row) => row.pipeline === pipeline);
  return ["1st", "2nd", "3rd"][i] || "";
}

function rankClass(rows, pipeline) {
  const i = rows.findIndex((row) => row.pipeline === pipeline);
  return i === 1 ? "second" : i === 2 ? "third" : "";
}

function renderMethods() {
  const rows = rankedSummaries();
  if (!rows.length) return;
  const bestP = Math.max(...rows.map((row) => row.macro_precision ?? 0));
  const bestR = Math.max(...rows.map((row) => row.macro_recall ?? 0));
  const bestCer = Math.min(...rows.map((row) => row.macro_cer ?? 1));
  const bestLat = Math.min(...rows.map((row) => row.latency?.mean_s ?? 99));
  els.methodsBody.replaceChildren();
  const warnings = [];
  rows.forEach((summary, index) => {
    const tr = document.createElement("tr");
    const merchant = summary.fields?.merchant?.recall;
    const date = summary.fields?.date?.recall;
    const total = summary.fields?.total?.recall;
    tr.innerHTML = `
      <td>
        <div class="method-cell">
          <span class="badge ${index === 1 ? "second" : index === 2 ? "third" : ""}">${["1st", "2nd", "3rd"][index] || ""}</span>
          <div>
            <strong>${escapeHtml(summary.display || summary.pipeline)}</strong>
            <small>${escapeHtml(PIPE_COLS.find((c) => c.key === summary.pipeline)?.version || summary.pipeline)}</small>
          </div>
        </div>
      </td>
      ${metricCell(pct(summary.macro_precision), summary.macro_precision === bestP, summary.macro_precision)}
      ${metricCell(pct(summary.macro_recall), summary.macro_recall === bestR, summary.macro_recall)}
      ${metricCell(num(summary.macro_cer), summary.macro_cer === bestCer)}
      ${metricCell(`${num(summary.latency?.mean_s, 3)} s`, summary.latency?.mean_s === bestLat)}
      ${metricCell(pct(merchant), false, merchant)}
      ${metricCell(pct(date), false, date)}
      ${metricCell(pct(total), false, total)}
    `;
    els.methodsBody.append(tr);
    for (const warning of summary.perfect_metric_warnings || []) {
      warnings.push(`${summary.display || summary.pipeline}: ${warning.replaceAll("—", ":")}`);
    }
  });
  if (warnings.length) {
    els.warnings.hidden = false;
    els.warnings.textContent = warnings.join(" ");
  } else {
    els.warnings.hidden = true;
  }
}

function metricCell(text, isBest, barValue) {
  const bar =
    barValue != null
      ? `<div class="bar"><i class="${isBest ? "is-best" : ""}" style="width:${Math.max(0, Math.min(100, barValue * 100))}%"></i></div>`
      : "";
  return `<td class="${isBest ? "best" : ""}">${escapeHtml(text)}${bar}</td>`;
}

function renderTabs() {
  const ids = [...new Set([
    ...state.receipts.filter((r) => state.selected.has(r.id)).map((r) => r.id),
    ...missIds(),
  ])].slice(0, 12);
  const list = ids.length ? ids : state.receipts.slice(0, 8).map((r) => r.id);
  els.receiptTabs.replaceChildren();
  for (const id of list) {
    const receipt = state.receipts.find((item) => item.id === id);
    if (!receipt) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `receipt-tab${state.currentId === id ? " is-active" : ""}`;
    btn.innerHTML = `<span class="mono">${escapeHtml(id.replace("train_", "#"))}</span>${escapeHtml(receipt.fields.merchant || id)}`;
    btn.addEventListener("click", () => {
      state.currentId = id;
      if (!state.selected.has(id)) state.selected.add(id);
      showCurrent(id);
      renderTabs();
      renderCompare();
      renderMeta();
    });
    els.receiptTabs.append(btn);
  }
}

function missIds() {
  const ids = [];
  for (const summary of state.summaries) {
    for (const doc of summary.documents || []) {
      if (FIELDS.some((name) => doc.fields[name] && !doc.fields[name].match)) {
        ids.push(doc.receipt_id);
      }
    }
  }
  return ids;
}

function showCurrent(id) {
  const receipt = state.receipts.find((item) => item.id === id);
  if (!receipt || !receipt.image_url) {
    els.stageFrame.hidden = true;
    els.stageEmpty.hidden = false;
    return;
  }
  els.stageEmpty.hidden = true;
  els.stageFrame.hidden = false;
  const img = stageImage();
  img.src = receipt.image_url;
  img.alt = `Receipt ${receipt.id}`;
}

function renderMeta() {
  const receipt = state.receipts.find((item) => item.id === state.currentId);
  if (!receipt) {
    els.metaCard.innerHTML = "";
    els.scoreCard.innerHTML = "";
    return;
  }
  els.metaCard.innerHTML = `
    <strong>${escapeHtml(receipt.fields.merchant || receipt.id)}</strong>
    <div class="mono">${escapeHtml(receipt.id)} ${receipt.verified ? receipt.fields.date || "" : "unlabeled"}</div>
  `;
  const rows = PIPE_COLS.map((col) => {
    const counts = fieldCounts(col.key);
    const color = counts.ok === 3 ? "#166534" : counts.ok >= 2 ? "#92400e" : "#9f1239";
    const width = (counts.ok / 3) * 100;
    return `<div class="score-row"><span>${escapeHtml(col.label)}</span><div class="score-line"><div class="track"><i style="width:${width}%;background:${color}"></i></div><div class="n" style="color:${color}">${counts.ok}/3</div></div></div>`;
  }).join("");
  els.scoreCard.innerHTML = `<div class="stat-label">Fields correct</div>${rows}`;
}

function fieldCounts(pipeline) {
  let ok = 0;
  for (const field of FIELDS) {
    const cell = cellFor(pipeline, field);
    if (cell.match) ok += 1;
  }
  return { ok };
}

function cellFor(pipeline, field) {
  const live = state.live[state.currentId]?.[pipeline];
  if (live) {
    return {
      value: live.fields?.[field],
      match: live.scored ? live.comparison?.[field]?.match : null,
    };
  }
  const summary = state.summaries.find((item) => item.pipeline === pipeline);
  const doc = summary?.documents?.find((item) => item.receipt_id === state.currentId);
  if (!doc) return { value: null, match: null };
  const cell = doc.fields[field];
  return { value: cell?.pred, match: cell?.match };
}

function renderCompare() {
  const receipt = state.receipts.find((item) => item.id === state.currentId);
  if (!receipt) return;
  els.compareBody.replaceChildren();
  for (const field of FIELDS) {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.innerHTML = `${FIELD_LABEL[field]}<small>${escapeHtml(receipt.verified ? receipt.fields[field] || "" : "")}</small>`;
    tr.append(th);
    for (const col of PIPE_COLS) {
      const td = document.createElement("td");
      const cell = cellFor(col.key, field);
      if (cell.match === true) {
        td.innerHTML = `<div class="cell ok">${escapeHtml(cell.value ?? "")}</div>`;
      } else if (cell.match === false) {
        td.innerHTML = `<div class="cell miss">${escapeHtml(cell.value ?? "missing")}</div><div class="expected">expected <b>${escapeHtml(receipt.fields[field] || "")}</b></div>`;
      } else {
        td.innerHTML = `<div class="cell pending">${cell.value ? escapeHtml(cell.value) : "pending"}</div>`;
      }
      tr.append(td);
    }
    els.compareBody.append(tr);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function upsertSummary(summary) {
  if (!summary) return;
  const index = state.summaries.findIndex((item) => item.pipeline === summary.pipeline);
  if (index >= 0) state.summaries[index] = summary;
  else state.summaries.push(summary);
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    state.view = tab.dataset.view;
    document.querySelectorAll(".tab").forEach((el) => el.classList.toggle("is-active", el === tab));
    els.viewLeaderboard.hidden = state.view !== "leaderboard";
    els.viewGallery.hidden = state.view !== "gallery";
  });
});

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const pipelines = selectedPipes();
  const ids = [...state.selected];
  if (!pipelines.length) {
    setStatus("Choose a pipeline.", true);
    return;
  }
  if (!ids.length) {
    setStatus("Select at least one sample.", true);
    return;
  }
  state.running = true;
  els.runBtn.disabled = true;
  els.photoWell.classList.add("is-scanning");
  state.view = "gallery";
  document.querySelectorAll(".tab").forEach((el) => el.classList.toggle("is-active", el.dataset.view === "gallery"));
  els.viewLeaderboard.hidden = true;
  els.viewGallery.hidden = false;
  setStatus("Starting scan.");
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipelines, ids }),
    });
    if (response.status === 409) {
      setStatus("A scan is already running.", true);
      return;
    }
    if (!response.ok || !response.body) {
      setStatus((await response.text()) || "Scan failed to start.", true);
      return;
    }
    await readSse(response.body);
  } catch (err) {
    setStatus(String(err), true);
  } finally {
    state.running = false;
    els.runBtn.disabled = false;
    els.photoWell.classList.remove("is-scanning");
  }
});

async function readSse(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) handleSseChunk(chunk);
  }
  if (buffer.trim()) handleSseChunk(buffer);
}

function handleSseChunk(chunk) {
  let eventName = "message";
  const dataLines = [];
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return;
  onEvent(eventName, JSON.parse(dataLines.join("\n")));
}

function onEvent(name, payload) {
  if (name === "run_error") {
    setStatus(payload.detail || "Scan error.", true);
    return;
  }
  if (name === "pipeline_skipped") {
    setStatus(`${payload.pipeline} skipped. ${payload.reason}`, true);
    return;
  }
  if (name === "pipeline_started") {
    setStatus(`${payload.display} on ${payload.n} samples.`);
    return;
  }
  if (name === "document_started") {
    state.currentId = payload.receipt_id;
    els.photoWell.classList.add("is-scanning");
    showCurrent(payload.receipt_id);
    renderTabs();
    renderMeta();
    const label = displayOf(payload.pipeline);
    setStatus(`${label} ${payload.index + 1} of ${payload.n}: ${payload.receipt_id}`);
    return;
  }
  if (name === "document_done") {
    if (!state.live[payload.receipt_id]) state.live[payload.receipt_id] = {};
    state.live[payload.receipt_id][payload.pipeline] = payload;
    renderCompare();
    renderMeta();
    return;
  }
  if (name === "pipeline_done") {
    upsertSummary(payload.summary);
    renderSummary();
    renderMethods();
    renderTabs();
    return;
  }
  if (name === "run_complete") {
    if (payload.summaries?.length) state.summaries = payload.summaries;
    renderAll();
    setStatus("Scan finished.");
  }
}

document.getElementById("select-visible").addEventListener("click", () => {
  selectFirst(Number(els.sampleCount.value) || 8);
  renderAll();
});

document.getElementById("select-none").addEventListener("click", () => {
  state.selected.clear();
  renderTabs();
});

els.sampleCount.addEventListener("change", () => {
  selectFirst(Number(els.sampleCount.value) || 8);
  renderAll();
});

async function onUpload(file) {
  if (!file) return;
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/uploads", { method: "POST", body });
  if (!response.ok) {
    setStatus("Upload failed. Use JPEG, PNG, or WebP.", true);
    return;
  }
  const item = await response.json();
  state.receipts.push(item);
  state.selected.add(item.id);
  state.currentId = item.id;
  renderAll();
  setStatus(`${item.id} added. Unlabeled uploads extract only.`);
}

document.querySelectorAll('input[type="file"]').forEach((input) => {
  input.addEventListener("change", async () => {
    await onUpload(input.files?.[0]);
    input.value = "";
  });
});

boot().catch((err) => setStatus(String(err), true));
