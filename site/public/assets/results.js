// Renders the leaderboard tables from /leaderboard.json, which the deploy
// script copies from leaderboard/leaderboard.json in this repository.

const DATA_URL = "/leaderboard.json";
const SOURCE_URL = "https://github.com/13fragments/kurrent-pages/blob/main/leaderboard/LEADERBOARD.md";

const STRATA = [
  ["suetterlin", "Sütterlin"],
  ["ugly_kurrent", "Difficult Kurrent"],
  ["twentieth_century_kurrent", "20th-c. Kurrent"],
  ["nineteenth_c_civilian", "19th-c. civil records"],
  ["degraded_fraktur", "Degraded Fraktur"],
  ["mixed_print_handwriting", "Print and handwriting"],
  ["table_registry", "Tables and registers"],
  ["tidy_kurrent", "Tidy Kurrent"],
  ["marginalia", "Marginalia"],
  ["latin_cursive_1940s", "Latin cursive, 1940s"],
];

const GROUPS = {
  self: { mark: "†", label: "Not ranked: built by the benchmark maintainer", flagged: true },
  frontier: { mark: "‡", label: "Not ranked: general-purpose frontier models, single dated runs", flagged: false },
};

const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) if (value != null && value !== "") node.setAttribute(key, value);
  for (const kid of kids) if (kid != null) node.append(kid instanceof Node ? kid : document.createTextNode(kid));
  return node;
};
const fix3 = (x) => (x == null ? "–" : x.toFixed(3));
const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
const byCer = (a, b) => a.overall.cer_norm_median - b.overall.cer_norm_median;

// "Name (repo, revision), settings" -> name and detail.
function splitEngine(engine) {
  const cut = engine.indexOf(" (");
  return cut < 0 ? [engine, ""] : [engine.slice(0, cut), engine.slice(cut + 1)];
}

function engineCell(row, mark, withCategory) {
  const [name, detail] = splitEngine(row.engine);
  const extra = [detail, withCategory ? row.category : ""].filter(Boolean).join("; ");
  return el("td", { class: "l engine" }, name,
    mark ? el("span", { class: mark === "†" ? "mark flag" : "mark", "aria-hidden": "true" }, mark) : null,
    extra ? el("span", { class: "detail" }, extra) : null);
}

function best(rows, get, dir) {
  if (!dir) return undefined;
  const values = rows.map(get).filter((v) => v != null);
  return dir === "min" ? Math.min(...values) : Math.max(...values);
}

const SUMMARY_COLS = [
  ["CER", (r) => r.overall.cer_norm_median, fix3, "min"],
  ["Hard-strata CER", (r) => r.hard_strata?.cer_norm_median, fix3, "min"],
  ["Entity recall", (r) => r.overall.entity_recall_median, fix3, "max"],
];
const FULL_COLS = [
  ["CER median", (r) => r.overall.cer_norm_median, fix3, "min"],
  ["CER mean", (r) => r.overall.cer_norm_mean, fix3, "min"],
  ["Hard-strata CER", (r) => r.hard_strata?.cer_norm_median, fix3, "min"],
  ["Entity recall", (r) => r.overall.entity_recall_median, fix3, "max"],
  ["Seg-fail", (r) => r.overall.seg_fail_rate, pct, "min"],
  // No best value: zero flags can also mean an engine wrote almost nothing.
  ["Fabrication flags", (r) => r.fabrication_proxy_unadjudicated?.["pages_above_0.10"], String, null],
];

function renderMetricTable(table, data, cols, withCategory) {
  const ranked = [...data.rows].sort(byCer);
  const bests = cols.map(([, get, , dir]) => best(ranked, get, dir));
  const width = cols.length + 2;
  const head = el("thead", {}, el("tr", {},
    el("th", { class: "l", scope: "col" }, "#"),
    el("th", { class: "l", scope: "col" }, "Engine"),
    ...cols.map(([label]) => el("th", { scope: "col" }, label))));
  const row = (r, rank, mark, highlight) => el("tr", {},
    el("td", { class: "l rank" }, rank),
    engineCell(r, mark, withCategory),
    ...cols.map(([, get, fmt], c) => {
      const v = get(r);
      return el("td", { class: highlight && v === bests[c] ? "best" : "" }, v == null ? "–" : fmt(v));
    }));
  const bodies = [el("tbody", {}, ...ranked.map((r, i) => row(r, String(i + 1), "", true)))];
  for (const [key, list] of [["self", data.self_reported_rows], ["frontier", data.frontier_rows]]) {
    if (!list?.length) continue;
    const g = GROUPS[key];
    bodies.push(el("tbody", { class: g.flagged ? "flagged" : "" },
      el("tr", { class: "group" + (g.flagged ? " flagged" : "") }, el("th", { colspan: String(width), scope: "rowgroup" }, g.label)),
      ...[...list].sort(byCer).map((r) => row(r, "", g.mark, false))));
  }
  table.replaceChildren(table.querySelector("caption") ?? "", head, ...bodies);
}

function renderStrataTable(table, rows) {
  const sorted = [...rows].sort(byCer);
  const n = (id) => sorted[0]?.per_stratum?.[id]?.n ?? 0;
  const get = (id) => (r) => r.per_stratum?.[id]?.cer_norm_median;
  const bests = STRATA.map(([id]) => best(sorted, get(id), "min"));
  const head = el("thead", {}, el("tr", {},
    el("th", { class: "l", scope: "col" }, "Engine"),
    ...STRATA.map(([id, label]) => el("th", { scope: "col", class: n(id) <= 3 ? "indicative" : "" }, label, el("small", {}, `n = ${n(id)}`)))));
  const body = el("tbody", {}, ...sorted.map((r) => el("tr", {},
    engineCell(r, "", false),
    ...STRATA.map(([id], c) => {
      const v = get(id)(r);
      const cls = [n(id) <= 3 ? "indicative" : "", v === bests[c] ? "best" : ""].join(" ").trim();
      return el("td", { class: cls }, fix3(v));
    }))));
  table.replaceChildren(table.querySelector("caption") ?? "", head, body);
}

function showError(table, message) {
  const status = el("td", { class: "status" }, `The results did not load (${message}). `, el("a", { href: SOURCE_URL }, "Read them on GitHub."));
  table.replaceChildren(table.querySelector("caption") ?? "", el("tbody", {}, el("tr", {}, status)));
}

async function main() {
  const tables = [...document.querySelectorAll("table[data-results]")];
  if (!tables.length) return;
  try {
    const response = await fetch(DATA_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    for (const table of tables) {
      const kind = table.dataset.results;
      if (kind === "summary") renderMetricTable(table, data, SUMMARY_COLS, false);
      if (kind === "full") renderMetricTable(table, data, FULL_COLS, true);
      if (kind === "strata") renderStrataTable(table, data.rows);
      if (kind === "strata-unranked") renderStrataTable(table, [...(data.self_reported_rows ?? []), ...(data.frontier_rows ?? [])]);
    }
    for (const node of document.querySelectorAll("[data-field]")) {
      const value = { benchmark: data.benchmark, harness: data.harness_tag, ranked: String(data.rows.length),
        self_note: data.self_reported_note, frontier_note: data.frontier_note }[node.dataset.field];
      if (value) node.textContent = value;
    }
  } catch (error) {
    for (const table of tables) showError(table, error.message);
  }
}

main();

// Copy the BibTeX entry.
for (const button of document.querySelectorAll("button[data-copy]")) {
  button.addEventListener("click", async () => {
    const text = document.getElementById(button.dataset.copy).textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
    } catch {
      button.textContent = "Select and copy";
    }
    setTimeout(() => { button.textContent = "Copy BibTeX"; }, 2000);
  });
}
