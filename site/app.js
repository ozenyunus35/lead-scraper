"use strict";

const LABELS = {
  name: "Business", category: "Category", phone: "Phone (E.164)", phone_display: "Phone", street: "Street", city: "City", state: "State", zip: "ZIP",
  website: "Website", email: "Email", rating: "Rating", reviews: "Reviews", source_url: "Source page",
  title: "Title", price_gbp: "Price (£)", in_stock: "In stock", url: "Link",
};

// Per dataset: table columns, the two filters and the breakdown shown on the side.
const SETS = {
  directory: {
    columns: ["name", "category", "phone_display", "website", "rating"],
    filters: [
      { label: "Category", all: "All categories", values: (rows) => [...new Set(rows.flatMap(categories))].sort(), match: (r, v) => categories(r).includes(v) },
      { label: "City", all: "All cities", values: (rows) => [...new Set(rows.map((r) => r.city))].sort(), match: (r, v) => r.city === v },
    ],
    breakdown: { title: "By category", key: (r) => categories(r), filter: 0 },
    search: ["name", "category", "city", "street", "phone_display", "website", "email"],
    pipeline: (m, rows) => [
      ["Crawl", m.pages_fetched, "pages, robots.txt respected"],
      ["Parse", m.records + m.duplicates_removed, "listings found"],
      ["Clean", rows.filter((r) => r.phone).length, "phones in E.164"],
      ["Merge", m.duplicates_removed, "duplicates merged"],
      ["Export", m.records, `records in ${m.duration_s}s`],
    ],
  },
  books: {
    columns: ["title", "price_gbp", "rating", "in_stock", "url"],
    filters: [
      { label: "Rating", all: "Any rating", values: () => ["5", "4", "3", "2", "1"], text: (v) => `${v} stars`, match: (r, v) => String(r.rating) === v },
      { label: "Stock", all: "Any stock", values: () => ["yes", "no"], text: (v) => (v === "yes" ? "In stock" : "Out of stock"), match: (r, v) => r.in_stock === (v === "yes") },
    ],
    breakdown: { title: "By rating", key: (r) => [`${r.rating} stars`], filter: null },
    search: ["title"],
    pipeline: (m, rows) => [
      ["Crawl", m.pages_fetched, "pages, 1 request per second"],
      ["Parse", m.records + m.duplicates_removed, "books found"],
      ["Clean", rows.filter((r) => typeof r.price_gbp === "number").length, "prices as numbers"],
      ["Merge", m.duplicates_removed, "duplicates merged"],
      ["Export", m.records, `records in ${m.duration_s}s`],
    ],
  },
};

const ICONS = {
  Crawl: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  Parse: '<path d="M4 6h16M4 12h10M4 18h7"/>',
  Clean: '<path d="m5 13 4 4L19 7"/>',
  Merge: '<path d="M7 4v6a5 5 0 0 0 5 5h5M17 11l3 4-3 4M7 20v-4"/>',
  Export: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
};

const cache = {};
let current = "directory";
let data = null;
let visible = [];

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const categories = (r) => String(r.category || "").split(/;\s*/).filter(Boolean);
const host = (u) => String(u).replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");

function ago(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 129600) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

/** The workflow runs daily at 06:17 UTC. */
function nextRun() {
  const now = new Date();
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 6, 17));
  if (next <= now) next.setUTCDate(next.getUTCDate() + 1);
  const h = Math.round((next - now) / 3_600_000);
  return h < 1 ? "next run within the hour" : `next run in ${h} h`;
}

async function load(set) {
  if (!cache[set]) {
    const r = await fetch(`data/${set}.json`, { cache: "no-cache" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    cache[set] = await r.json();
  }
  return cache[set];
}

const stars = (n) => `<span class="stars" aria-label="${n} out of 5">${"★".repeat(Math.round(n))}<i>${"★".repeat(5 - Math.round(n))}</i></span>`;

function cell(field, r) {
  const v = r[field];
  if (v === "" || v === null || v === undefined) return '<span class="empty">—</span>';
  switch (field) {
    case "name":
      return `${esc(v)}<span class="sub">${esc(r.street)}, ${esc(r.city)}</span>`;
    case "category": {
      const c = categories(r);
      return `<span class="tags">${c.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}${c.length > 1 ? '<span class="tag merged" title="Listed under several categories, merged into one record">merged</span>' : ""}</span>`;
    }
    case "phone_display":
      return `${esc(v)}<span class="sub">${esc(r.phone)}</span>`;
    case "website":
      return `<a href="${esc(v)}" rel="nofollow noopener" target="_blank">${esc(host(v))}</a>${r.email ? `<span class="sub">${esc(r.email)}</span>` : ""}`;
    case "url":
      return `<a href="${esc(v)}" rel="nofollow noopener" target="_blank">Open</a>`;
    case "rating":
      return current === "books" ? stars(v) : `${stars(v)} ${Number(v).toFixed(1)}<span class="sub">${r.reviews} reviews</span>`;
    case "in_stock":
      return v ? "Yes" : "No";
    case "price_gbp":
      return Number(v).toFixed(2);
    default:
      return esc(v);
  }
}

function render() {
  const m = data.meta;
  const set = SETS[current];
  $("title").textContent = m.dataset;
  $("meta").innerHTML = `Source <a href="${esc(m.source)}">${esc(host(m.source))}</a> · last run ${ago(m.run_at)} · ${nextRun()}`;
  $("pipeline").innerHTML = set
    .pipeline(m, data.rows)
    .map(([step, n, label]) => `<li><span class="step"><svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[step]}</svg>${step}</span><b>${n.toLocaleString("en-US")}</b><small>${esc(label)}</small></li>`)
    .join("");
  $("downloads").innerHTML = ["xlsx", "csv", "json"]
    .map((ext, i) => `<a class="btn${i === 0 ? " primary" : ""}" href="data/${current}.${ext}" download>${ext === "xlsx" ? "Excel" : ext.toUpperCase()}</a>`)
    .join("");

  ["f1", "f2"].forEach((id, i) => {
    const f = set.filters[i], el = $(id);
    el.hidden = !f;
    if (!f) return;
    el.setAttribute("aria-label", f.label);
    el.innerHTML = `<option value="">${f.all}</option>` + f.values(data.rows).map((v) => `<option value="${esc(v)}">${esc(f.text ? f.text(v) : v)}</option>`).join("");
  });

  const rows = data.rows;
  // Gaps first: fields that are filled in every record are listed in one line.
  const filled = data.fields.map((f) => [f, Math.round((rows.filter((r) => r[f] !== "" && r[f] !== null && r[f] !== undefined).length / Math.max(1, rows.length)) * 100)]);
  const complete = filled.filter(([, pct]) => pct === 100).map(([f]) => LABELS[f] || f);
  $("coverage").innerHTML =
    filled
      .filter(([, pct]) => pct < 100)
      .sort((a, b) => a[1] - b[1])
      .map(([f, pct]) => `<li><span>${esc(LABELS[f] || f)}</span><em>${pct}%</em><span class="bar" aria-hidden="true"><i style="width:${pct}%"></i></span></li>`)
      .join("") + (complete.length ? `<li class="complete"><span>Complete in every record: ${esc(complete.join(", "))}</span></li>` : "");

  const counts = {};
  rows.forEach((r) => set.breakdown.key(r).forEach((k) => (counts[k] = (counts[k] || 0) + 1)));
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const max = Math.max(1, ...top.map(([, n]) => n));
  $("breakdown-title").textContent = set.breakdown.title;
  $("breakdown").innerHTML = top
    .map(([k, n]) => {
      const label = set.breakdown.filter === null ? esc(k) : `<button type="button" data-filter="${esc(k)}">${esc(k)}</button>`;
      return `<li>${label}<em>${n}</em><span class="bar" aria-hidden="true"><i style="width:${(n / max) * 100}%"></i></span></li>`;
    })
    .join("");
  draw();
}

function draw() {
  const set = SETS[current];
  const q = $("q").value.trim().toLowerCase();
  const picked = ["f1", "f2"].map((id) => $(id).value);
  visible = data.rows.filter(
    (r) => (!q || set.search.some((f) => String(r[f] ?? "").toLowerCase().includes(q))) && set.filters.every((f, i) => !picked[i] || f.match(r, picked[i])),
  );
  const shown = visible.slice(0, 200);
  const num = (f) => (f === "price_gbp" ? ' class="num"' : "");
  $("table").innerHTML =
    `<thead><tr>${set.columns.map((f) => `<th scope="col"${num(f)}>${LABELS[f] || f}</th>`).join("")}</tr></thead>` +
    `<tbody>${shown.map((r, i) => `<tr data-i="${i}" tabindex="0">${set.columns.map((f) => `<td${f === "category" ? ' class="cat"' : num(f)}>${cell(f, r)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  $("count").textContent = `${visible.length} of ${data.rows.length} records`;
  $("note").textContent = visible.length === 0 ? "No records match these filters." : visible.length > shown.length ? `Showing ${shown.length} of ${visible.length}. The downloads contain every record.` : "Click a record to see every field.";
}

function openRecord(r) {
  const fields = data.fields;
  $("record-title").textContent = r.name || r.title;
  $("record-body").innerHTML = fields
    .map((f) => {
      let v = r[f];
      if (v === "" || v === null || v === undefined) v = '<span class="empty">Not listed</span>';
      else if (/url|website/.test(f)) v = `<a href="${esc(v)}" rel="nofollow noopener" target="_blank">${esc(host(v))}</a>`;
      else if (f === "phone") v = `<code>${esc(v)}</code>`;
      else if (f === "in_stock") v = v ? "Yes" : "No";
      else v = esc(v);
      return `<dt>${esc(LABELS[f] || f)}</dt><dd>${v}</dd>`;
    })
    .join("");
  $("record").showModal();
}

async function show(set) {
  current = set;
  document.querySelectorAll("[role=tab]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.set === set)));
  $("q").value = "";
  try {
    data = await load(set);
    render();
  } catch {
    $("table").innerHTML = "";
    $("note").textContent = "Could not load the latest results. Please refresh in a moment.";
  }
}

document.querySelectorAll("[role=tab]").forEach((t) => t.addEventListener("click", () => show(t.dataset.set)));
$("q").addEventListener("input", draw);
$("f1").addEventListener("change", draw);
$("f2").addEventListener("change", draw);
$("breakdown").addEventListener("click", (e) => {
  const b = e.target.closest("[data-filter]");
  if (!b) return;
  $("f1").value = $("f1").value === b.dataset.filter ? "" : b.dataset.filter;
  draw();
});
$("table").addEventListener("click", (e) => {
  const tr = e.target.closest("tbody tr");
  if (tr && !e.target.closest("a")) openRecord(visible[Number(tr.dataset.i)]);
});
$("table").addEventListener("keydown", (e) => {
  const tr = e.target.closest("tbody tr");
  if (tr && e.key === "Enter") openRecord(visible[Number(tr.dataset.i)]);
});
$("record-close").addEventListener("click", () => $("record").close());
$("record").addEventListener("click", (e) => e.target === $("record") && $("record").close());
$("theme").addEventListener("click", () => {
  const dark = document.documentElement.classList.toggle("dark");
  try {
    localStorage.setItem("leads:theme", dark ? "dark" : "light");
  } catch {}
});

load("directory")
  .then((d) => {
    const hours = (Date.now() - new Date(d.meta.run_at).getTime()) / 3_600_000;
    $("run-text").textContent = `Last run ${ago(d.meta.run_at)} · runs daily at 06:17 UTC`;
    $("run").classList.add(hours > 36 ? "stale" : "ok");
  })
  .catch(() => ($("run-text").textContent = "Latest run unavailable"));
show("directory");
