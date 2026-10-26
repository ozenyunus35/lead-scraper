"use strict";

const LABELS = {
  name: "Name", category: "Category", phone_display: "Phone", city: "City", website: "Website", email: "Email",
  rating: "Rating", title: "Title", price_gbp: "Price (£)", in_stock: "In stock", url: "Link",
};
// Columns shown in the table; the downloads contain every field.
const VIEW = {
  directory: ["name", "category", "phone_display", "city", "website", "email", "rating"],
  books: ["title", "price_gbp", "rating", "in_stock", "url"],
};
const cache = {};
let current = "directory";
let data = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

function ago(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} minutes ago`;
  if (s < 129600) return `${Math.round(s / 3600)} hours ago`;
  return `${Math.round(s / 86400)} days ago`;
}

async function load(set) {
  if (!cache[set]) {
    const r = await fetch(`data/${set}.json`, { cache: "no-cache" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    cache[set] = await r.json();
  }
  return cache[set];
}

function cell(field, v) {
  if (v === "" || v === null || v === undefined) return '<span class="empty">—</span>';
  if (field === "website" || field === "url") {
    const text = field === "url" ? "Open" : String(v).replace(/^https?:\/\/(www\.)?/, "");
    return `<a href="${esc(v)}" rel="nofollow noopener" target="_blank">${esc(text)}</a>`;
  }
  if (field === "in_stock") return v ? "Yes" : "No";
  if (field === "price_gbp") return Number(v).toFixed(2);
  if (field === "rating") return `${v}${current === "books" ? " / 5" : ""}`;
  return esc(v);
}

function render() {
  const m = data.meta;
  const stat = (v, l) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`;
  $("stats").innerHTML =
    stat(m.records, "records") +
    (current === "directory" ? stat(m.duplicates_removed, "duplicates merged") : "") +
    stat(m.pages_fetched, "pages crawled") +
    stat(`${m.duration_s}s`, "run time");
  $("source").innerHTML = `Source: <a href="${esc(m.source)}">${esc(m.source.replace(/^https?:\/\//, ""))}</a> · last run ${ago(m.run_at)}`;
  $("downloads").innerHTML = ["xlsx", "csv", "json"]
    .map((ext, i) => `<a class="btn${i === 0 ? " primary" : ""}" href="data/${current}.${ext}" download>${ext === "xlsx" ? "Excel" : ext.toUpperCase()}</a>`)
    .join("");
  draw();
}

function draw() {
  const fields = VIEW[current];
  const q = $("q").value.trim().toLowerCase();
  const rows = q ? data.rows.filter((r) => fields.some((f) => String(r[f] ?? "").toLowerCase().includes(q))) : data.rows;
  const shown = rows.slice(0, 200);
  $("table").innerHTML =
    `<thead><tr>${fields.map((f) => `<th scope="col">${LABELS[f] || f}</th>`).join("")}</tr></thead>` +
    `<tbody>${shown.map((r) => `<tr>${fields.map((f) => `<td>${cell(f, r[f])}</td>`).join("")}</tr>`).join("")}</tbody>`;
  $("note").textContent =
    rows.length === 0 ? "No rows match." : rows.length > shown.length ? `Showing ${shown.length} of ${rows.length} rows. Download the file for all of them.` : `${rows.length} rows.`;
}

async function show(set) {
  current = set;
  document.querySelectorAll("[role=tab]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.set === set)));
  try {
    data = await load(set);
    render();
  } catch (e) {
    $("table").innerHTML = "";
    $("note").textContent = "Could not load the latest results. Please refresh in a moment.";
  }
}

document.querySelectorAll("[role=tab]").forEach((t) => t.addEventListener("click", () => { $("q").value = ""; show(t.dataset.set); }));
$("q").addEventListener("input", draw);

load("directory")
  .then((d) => {
    $("run-text").textContent = `Last run ${ago(d.meta.run_at)} · runs daily`;
    $("run-badge").classList.add("ok");
  })
  .catch(() => { $("run-text").textContent = "Latest run unavailable"; });
show("directory");
