"use strict";

// English is the key; Turkish texts live in tr.js-style table below. {name} placeholders are filled in.
const TR = window.LEADS_TR || {};
window.__i18nMisses = new Set();
let lang = (() => {
  const q = new URLSearchParams(location.search).get("lang");
  if (q === "tr" || q === "en") {
    try {
      localStorage.setItem("leads:lang", q);
    } catch {}
    return q;
  }
  try {
    const saved = localStorage.getItem("leads:lang");
    if (saved === "tr" || saved === "en") return saved;
  } catch {}
  return /^tr\b/i.test(navigator.language) ? "tr" : "en";
})();
function t(s, vars) {
  let out = s;
  if (lang === "tr") {
    if (TR[s] !== undefined) out = TR[s];
    else if (/\p{L}/u.test(s)) window.__i18nMisses.add(s);
  }
  if (vars) for (const [k, v] of Object.entries(vars)) out = out.split(`{${k}}`).join(String(v));
  return out;
}
/** "rating 4.3 → 4.2; phone … → …" with the field names in the interface language. */
const changesText = (s) =>
  String(s)
    .split("; ")
    .map((d) => d.replace(/^(\w+)/, (w) => t(w)))
    .join("; ");
const num = (n) => Number(n).toLocaleString(lang === "tr" ? "tr-TR" : "en-US");
const dec1 = (n) => Number(n).toLocaleString(lang === "tr" ? "tr-TR" : "en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** The page's own HTML text, swapped for the chosen language. The English original is kept on the element. */
function applyStatic() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.dataset.en ??= el.textContent;
    el.textContent = t(el.dataset.en);
  });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    el.dataset.en ??= el.innerHTML.trim();
    el.innerHTML = lang === "tr" && TR[el.dataset.en] ? TR[el.dataset.en] : el.dataset.en;
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.dataset.enPlaceholder ??= el.placeholder;
    el.placeholder = t(el.dataset.enPlaceholder);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.dataset.enAria ??= el.getAttribute("aria-label");
    if (el.id !== "lang") el.setAttribute("aria-label", t(el.dataset.enAria));
  });
  $("lang-code").textContent = lang === "tr" ? "EN" : "TR";
  $("lang").setAttribute("aria-label", lang === "tr" ? "Switch to English" : "Türkçeye geç");
  $("lang").title = $("lang").getAttribute("aria-label");
}

const LABELS = {
  name: "Business", category: "Category", phone: "Phone (E.164)", phone_display: "Phone", street: "Street", city: "City", state: "State", zip: "ZIP",
  website: "Website", domain: "Domain", email: "Email", rating: "Rating", reviews: "Reviews", source_url: "Source page",
  score: "Lead score", email_status: "Email status", other_emails: "Other emails", linkedin: "LinkedIn", facebook: "Facebook", instagram: "Instagram", x: "X",
  other_phones: "Other phones", site_status: "Website check", change: "Since last run", changes: "What changed", first_seen: "First seen",
  title: "Title", price_gbp: "Price (£)", in_stock: "In stock", url: "Link",
};

// Per dataset: table columns, the two filters and the breakdown shown on the side.
const SETS = {
  directory: {
    columns: ["name", "category", "phone_display", "email", "score"],
    filters: [
      { label: "Category", all: "All categories", values: (rows) => [...new Set(rows.flatMap(categories))].sort(), match: (r, v) => categories(r).includes(v) },
      { label: "City", all: "All cities", values: (rows) => [...new Set(rows.map((r) => r.city))].sort(), match: (r, v) => r.city === v },
      {
        label: "Leads", all: "All leads",
        values: () => ["personal", "email", "social", "score70", "new", "changed"],
        text: (v) => t({ personal: "Named person's email", email: "Has an email", social: "Has social profiles", score70: "Score 70+", new: "New since last run", changed: "Changed since last run" }[v]),
        match: (r, v) => ({ personal: r.email_status === "personal", email: !!r.email, social: SOCIALS.some((n) => r[n]), score70: r.score >= 70, new: r.change === "new", changed: r.change === "changed" })[v],
      },
    ],
    sorts: [["score", "Best leads first"], ["name", "Name A–Z"], ["rating", "Highest rated"], ["first_seen", "Newest first"]],
    breakdown: { title: "By category", key: (r) => categories(r), filter: 0 },
    search: ["name", "category", "city", "street", "phone_display", "website", "email", "other_emails"],
    pipeline: (m, rows) => [
      ["Crawl", m.pages_fetched, t("pages, robots.txt respected")],
      ["Clean", rows.filter((r) => r.phone).length, t("phones in E.164")],
      ["Merge", m.duplicates_removed, t("duplicates merged")],
      ["Enrich", rows.filter((r) => r.email).length, t("emails from {n} websites", { n: m.sites_visited ?? 0 })],
      ["Score", rows.filter((r) => r.score >= 70).length, t("leads scored 70+")],
    ],
  },
  books: {
    sorts: [],
    columns: ["title", "price_gbp", "rating", "in_stock", "url"],
    filters: [
      { label: "Rating", all: "Any rating", values: () => ["5", "4", "3", "2", "1"], text: (v) => t("{n} stars", { n: v }), match: (r, v) => String(r.rating) === v },
      { label: "Stock", all: "Any stock", values: () => ["yes", "no"], text: (v) => (v === "yes" ? t("In stock") : t("Out of stock")), match: (r, v) => r.in_stock === (v === "yes") },
    ],
    breakdown: { title: "By rating", key: (r) => [t("{n} stars", { n: r.rating })], filter: null },
    search: ["title"],
    pipeline: (m, rows) => [
      ["Crawl", m.pages_fetched, t("pages, 1 request per second")],
      ["Parse", m.records + m.duplicates_removed, t("books found")],
      ["Clean", rows.filter((r) => typeof r.price_gbp === "number").length, t("prices as numbers")],
      ["Merge", m.duplicates_removed, t("duplicates merged")],
      ["Export", m.records, t("records in {n}s", { n: m.duration_s })],
    ],
  },
};

const ICONS = {
  Crawl: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  Parse: '<path d="M4 6h16M4 12h10M4 18h7"/>',
  Clean: '<path d="m5 13 4 4L19 7"/>',
  Merge: '<path d="M7 4v6a5 5 0 0 0 5 5h5M17 11l3 4-3 4M7 20v-4"/>',
  Export: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  Enrich: '<path d="M4 6h16v12H4z"/><path d="m4 7 8 6 8-6"/>',
  Score: '<path d="M12 3 14.6 8.6 20.5 9.2 16 13.2 17.3 19 12 16 6.7 19 8 13.2 3.5 9.2 9.4 8.6z"/>',
};

const SOCIALS = ["linkedin", "facebook", "instagram", "x"];
const STATUS = { personal: "Named person", role: "Shared inbox", "free-mail": "Free mail", disposable: "Disposable", invalid: "Invalid" };
// HubSpot's company import columns; Salesforce and Pipedrive map the same names. Same as scraper/export.py.
const CRM = [["Company name", "name"], ["Company Domain Name", "domain"], ["Phone Number", "phone"], ["Email", "email"], ["Street Address", "street"], ["City", "city"], ["State/Region", "state"], ["Postal Code", "zip"], ["Website URL", "website"], ["LinkedIn Company Page", "linkedin"], ["Facebook Company Page", "facebook"], ["Category", "category"], ["Lead Score", "score"], ["Email Status", "email_status"]];

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
  if (s < 90) return t("just now");
  if (s < 5400) return t("{n} min ago", { n: Math.round(s / 60) });
  if (s < 129600) return t("{n} h ago", { n: Math.round(s / 3600) });
  return t("{n} days ago", { n: Math.round(s / 86400) });
}

/** The workflow runs daily at 06:17 UTC. */
function nextRun() {
  const now = new Date();
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 6, 17));
  if (next <= now) next.setUTCDate(next.getUTCDate() + 1);
  const h = Math.round((next - now) / 3_600_000);
  return h < 1 ? t("next run within the hour") : t("next run in {n} h", { n: h });
}

async function load(set) {
  if (!cache[set]) {
    const r = await fetch(`data/${set}.json`, { cache: "no-cache" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    cache[set] = await r.json();
  }
  return cache[set];
}

const stars = (n) => `<span class="stars" aria-label="${t("{n} out of 5", { n })}">${"★".repeat(Math.round(n))}<i>${"★".repeat(5 - Math.round(n))}</i></span>`;

function cell(field, r) {
  const v = r[field];
  if (field === "email" && !v && SOCIALS.some((n) => r[n])) return cell("email", { ...r, email: " " });
  if (v === "" || v === null || v === undefined) return '<span class="empty">—</span>';
  switch (field) {
    case "name":
      return `${esc(v)}<span class="sub">${esc(r.street)}, ${esc(r.city)}</span>`;
    case "category": {
      const c = categories(r);
      return `<span class="tags">${c.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}${c.length > 1 ? `<span class="tag merged" title="${t("Listed under several categories, merged into one record")}">${t("merged")}</span>` : ""}</span>`;
    }
    case "phone_display":
      return `${esc(v)}<span class="sub">${esc(r.phone)}</span>`;
    case "website":
      return `<a href="${esc(v)}" rel="nofollow noopener" target="_blank">${esc(host(v))}</a>${r.email ? `<span class="sub">${esc(r.email)}</span>` : ""}`;
    case "email": {
      const nets = SOCIALS.filter((n) => r[n]).map((n) => `<a class="net" href="${esc(r[n])}" rel="nofollow noopener" target="_blank">${t(LABELS[n])}</a>`).join("");
      const status = r.email_status ? `<span class="tag st-${esc(r.email_status)}">${esc(t(STATUS[r.email_status] || r.email_status))}</span>` : "";
      return `<span class="mail">${esc(v)}</span><span class="sub">${status}${nets}</span>`;
    }
    case "score": {
      const level = v >= 70 ? "hi" : v >= 45 ? "mid" : "lo";
      const news = r.change ? `<span class="tag ch-${esc(r.change)}" title="${esc(r.changes ? changesText(r.changes) : t("First seen in this run"))}">${r.change === "new" ? t("new") : t("changed")}</span>` : "";
      return `<span class="score ${level}">${esc(v)}</span>${news}<span class="sub">${stars(r.rating)} ${dec1(r.rating || 0)} · ${t("{n} reviews", { n: esc(r.reviews) })}</span>`;
    }
    case "url":
      return `<a href="${esc(v)}" rel="nofollow noopener" target="_blank">${t("Open")}</a>`;
    case "rating":
      return current === "books" ? stars(v) : `${stars(v)} ${dec1(v)}<span class="sub">${t("{n} reviews", { n: r.reviews })}</span>`;
    case "in_stock":
      return v ? t("Yes") : t("No");
    case "price_gbp":
      return Number(v).toLocaleString(lang === "tr" ? "tr-TR" : "en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    default:
      return esc(v);
  }
}

function render() {
  const m = data.meta;
  const set = SETS[current];
  $("title").textContent = t(m.dataset);
  $("meta").innerHTML = `${t("Source")} <a href="${esc(m.source)}">${esc(host(m.source))}</a> · ${t("last run {time}", { time: ago(m.run_at) })} · ${nextRun()}`;
  $("pipeline").innerHTML = set
    .pipeline(m, data.rows)
    .map(([step, n, label]) => `<li><span class="step"><svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[step]}</svg>${t(step)}</span><b>${num(n)}</b><small>${esc(label)}</small></li>`)
    .join("");
  $("downloads").innerHTML =
    ["xlsx", "csv", "json"].map((ext, i) => `<a class="btn${i === 0 ? " primary" : ""}" href="data/${current}.${ext}" download>${ext === "xlsx" ? "Excel" : ext.toUpperCase()}</a>`).join("") +
    (current === "directory" ? `<button type="button" class="btn" id="crm">${t("CRM import (filtered)")}</button>` : "");
  $("crm-note").hidden = current !== "directory";

  // What changed since the last run.
  const ch = m.changes;
  $("changes-card").hidden = !ch;
  if (ch) {
    const closed = (ch.closed_names || []).map((n) => `<li>${esc(n)}</li>`).join("");
    $("changes").innerHTML = ch.compared
      ? `<p class="deltas"><button type="button" data-lead="new"><b>${ch.new}</b> ${t("new")}</button><button type="button" data-lead="changed"><b>${ch.changed}</b> ${t("changed")}</button><span><b>${ch.closed}</b> ${t("closed")}</span></p>` +
        (closed ? `<p class="faint">${t("No longer listed:")}</p><ul class="closed">${closed}</ul>` : "")
      : `<p class="faint">${t("This is the first run with change tracking; tomorrow's run will list what opened, closed or changed.")}</p>`;
  }

  $("sort").hidden = !set.sorts.length;
  $("sort").innerHTML = set.sorts.map(([k, label]) => `<option value="${k}">${t(label)}</option>`).join("");

  ["f1", "f2", "f3"].forEach((id, i) => {
    const f = set.filters[i], el = $(id);
    el.hidden = !f;
    if (!f) return;
    el.setAttribute("aria-label", t(f.label));
    el.innerHTML = `<option value="">${t(f.all)}</option>` + f.values(data.rows).map((v) => `<option value="${esc(v)}">${esc(f.text ? f.text(v) : v)}</option>`).join("");
  });

  const rows = data.rows;
  // Gaps first: fields that are filled in every record are listed in one line.
  // Fields a buyer of the list cares about; derived ones (status, score, change notes) are left out.
  const shownFields = data.fields.filter((f) => !["score", "email_status", "other_emails", "other_phones", "site_status", "change", "changes", "first_seen", "phone_display", "source_url", "domain"].includes(f));
  const filled = shownFields.map((f) => [f, Math.round((rows.filter((r) => r[f] !== "" && r[f] !== null && r[f] !== undefined).length / Math.max(1, rows.length)) * 100)]);
  const complete = filled.filter(([, pct]) => pct === 100).map(([f]) => t(LABELS[f] || f));
  $("coverage").innerHTML =
    filled
      .filter(([, pct]) => pct < 100)
      .sort((a, b) => a[1] - b[1])
      .map(([f, pct]) => `<li><span>${esc(t(LABELS[f] || f))}</span><em>${lang === "tr" ? "%" + pct : pct + "%"}</em><span class="bar" aria-hidden="true"><i style="width:${pct}%"></i></span></li>`)
      .join("") + (complete.length ? `<li class="complete"><span>${t("Complete in every record: {fields}", { fields: esc(complete.join(", ")) })}</span></li>` : "");

  const counts = {};
  rows.forEach((r) => set.breakdown.key(r).forEach((k) => (counts[k] = (counts[k] || 0) + 1)));
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const max = Math.max(1, ...top.map(([, n]) => n));
  $("breakdown-title").textContent = t(set.breakdown.title);
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
  const picked = ["f1", "f2", "f3"].map((id) => $(id).value);
  visible = data.rows.filter(
    (r) => (!q || set.search.some((f) => String(r[f] ?? "").toLowerCase().includes(q))) && set.filters.every((f, i) => !picked[i] || f.match(r, picked[i])),
  );
  const by = $("sort").value;
  if (by === "score" || by === "rating") visible.sort((a, b) => (Number(b[by]) || 0) - (Number(a[by]) || 0) || String(a.name).localeCompare(b.name));
  else if (by === "name") visible.sort((a, b) => String(a.name).localeCompare(b.name));
  else if (by === "first_seen") visible.sort((a, b) => String(b.first_seen).localeCompare(String(a.first_seen)) || (b.change === "new") - (a.change === "new"));
  const shown = visible.slice(0, 200);
  const numCls = (f) => (f === "price_gbp" ? ' class="num"' : "");
  $("table").innerHTML =
    `<thead><tr>${set.columns.map((f) => `<th scope="col"${numCls(f)}>${t(LABELS[f] || f)}</th>`).join("")}</tr></thead>` +
    `<tbody>${shown.map((r, i) => `<tr data-i="${i}" tabindex="0">${set.columns.map((f) => `<td${f === "category" ? ' class="cat"' : numCls(f)}>${cell(f, r)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  $("count").textContent = t("{n} of {total} records", { n: num(visible.length), total: num(data.rows.length) });
  $("note").textContent = visible.length === 0 ? t("No records match these filters.") : visible.length > shown.length ? t("Showing {n} of {total}. The downloads contain every record.", { n: shown.length, total: visible.length }) : t("Click a record to see every field.");
  saveHash();
}

function openRecord(r) {
  const fields = data.fields;
  $("record-title").textContent = r.name || r.title;
  $("record-body").innerHTML = fields
    .map((f) => {
      let v = r[f];
      if (v === "" || v === null || v === undefined) v = `<span class="empty">${t("Not listed")}</span>`;
      else if (/url|website|linkedin|facebook|instagram|^x$/.test(f)) v = `<a href="${esc(v)}" rel="nofollow noopener" target="_blank">${esc(host(v))}</a>`;
      else if (f === "email_status") v = esc(t(STATUS[v] || v));
      else if (f === "phone") v = `<code>${esc(v)}</code>`;
      else if (f === "in_stock") v = v ? t("Yes") : t("No");
      else v = esc(v);
      return `<dt>${esc(t(LABELS[f] || f))}</dt><dd>${v}</dd>`;
    })
    .join("");
  $("record").showModal();
}

async function show(set, restore) {
  current = set;
  document.querySelectorAll("[role=tab]").forEach((tab) => tab.setAttribute("aria-selected", String(tab.dataset.set === set)));
  $("q").value = "";
  try {
    data = await load(set);
    render();
    if (restore) {
      for (const id of ["q", "f1", "f2", "f3", "sort"]) if (restore.has(id)) $(id).value = restore.get(id);
      draw();
    }
  } catch {
    $("table").innerHTML = "";
    $("note").textContent = t("Could not load the latest results. Please refresh in a moment.");
  }
}

document.querySelectorAll("[role=tab]").forEach((tab) => tab.addEventListener("click", () => show(tab.dataset.set)));
$("q").addEventListener("input", draw);
$("f1").addEventListener("change", draw);
$("f2").addEventListener("change", draw);
$("f3").addEventListener("change", draw);
$("sort").addEventListener("change", draw);

/** The filtered leads as a CSV a CRM imports without column mapping; unreachable leads are left out. */
function crmCsv(rows) {
  const q = (v) => (/[",\n]/.test(String(v ?? "")) ? `"${String(v).replace(/"/g, '""')}"` : String(v ?? ""));
  const lines = [CRM.map(([c]) => c).join(",")].concat(rows.filter((r) => r.phone || r.email).map((r) => CRM.map(([, k]) => q(r[k])).join(",")));
  return "\ufeff" + lines.join("\r\n");
}
$("downloads").addEventListener("click", (e) => {
  if (!e.target.closest("#crm")) return;
  const url = URL.createObjectURL(new Blob([crmCsv(visible)], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: "leads-crm-import.csv" });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("changes").addEventListener("click", (e) => {
  const b = e.target.closest("[data-lead]");
  if (!b) return;
  $("f3").value = b.dataset.lead;
  draw();
});
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

/** The view lives in the address, so a copied link opens the same dataset and filters. */
function saveHash() {
  const p = new URLSearchParams();
  if (current !== "directory") p.set("set", current);
  for (const id of ["q", "f1", "f2", "f3"]) if ($(id).value) p.set(id, $(id).value);
  if ($("sort").value && $("sort").selectedIndex > 0) p.set("sort", $("sort").value);
  const hash = p.toString();
  try {
    history.replaceState(null, "", `${location.pathname}${location.search}${hash ? `#${hash}` : ""}`);
  } catch {}
}

$("lang").addEventListener("click", () => {
  lang = lang === "tr" ? "en" : "tr";
  try {
    localStorage.setItem("leads:lang", lang);
  } catch {}
  applyStatic();
  if (data) {
    const keep = Object.fromEntries(["q", "f1", "f2", "f3", "sort"].map((id) => [id, $(id).value]));
    render();
    for (const [id, v] of Object.entries(keep)) $(id).value = v;
    draw();
  }
});

// ⌘K: jump to a business, apply a filter, download, or switch theme and language.
let palItems = [];
let palIndex = 0;
function paletteCommands() {
  const cmds = [];
  const act = t("Actions");
  cmds.push({ group: t("Datasets"), label: t("Business leads"), run: () => show("directory") });
  cmds.push({ group: t("Datasets"), label: t("Books (sandbox)"), run: () => show("books") });
  if (data && current === "directory") {
    const lead = (v) => () => {
      $("f3").value = v;
      draw();
    };
    for (const v of SETS.directory.filters[2].values()) cmds.push({ group: t("Filters"), label: SETS.directory.filters[2].text(v), run: lead(v) });
    for (const c of SETS.directory.filters[0].values(data.rows))
      cmds.push({ group: t("Categories"), label: c, run: () => {
        $("f1").value = c;
        draw();
      } });
    for (const r of data.rows) cmds.push({ group: t("Businesses"), label: r.name, hint: `${r.city} · ${r.phone_display || ""}`, keywords: `${r.category} ${r.email || ""} ${r.website || ""}`, run: () => openRecord(r) });
  }
  for (const ext of ["xlsx", "csv", "json"]) cmds.push({ group: act, label: t("Download {format}", { format: ext === "xlsx" ? "Excel" : ext.toUpperCase() }), run: () => document.querySelector(`#downloads a[href$=".${ext}"]`)?.click() });
  if (current === "directory") cmds.push({ group: act, label: t("CRM import (filtered)"), run: () => $("crm")?.click() });
  cmds.push({ group: act, label: t("Clear filters"), run: () => {
    for (const id of ["q", "f1", "f2", "f3"]) $(id).value = "";
    draw();
  } });
  cmds.push({ group: act, label: t("Switch theme"), run: () => $("theme").click() });
  cmds.push({ group: act, label: lang === "tr" ? "Switch to English" : "Türkçeye geç", run: () => $("lang").click() });
  cmds.push({ group: act, label: t("Source code on GitHub"), run: () => window.open("https://github.com/ozenyunus35/lead-scraper", "_blank", "noopener") });
  return cmds;
}
const fold = (s) => String(s).toLocaleLowerCase("tr").normalize("NFD").replace(/\p{M}/gu, "").replace(/ı/g, "i");
function drawPalette() {
  const words = fold($("pal-q").value.trim()).split(/\s+/).filter(Boolean);
  const all = paletteCommands();
  palItems = (words.length ? all.filter((c) => words.every((w) => fold(`${c.label} ${c.group} ${c.hint || ""} ${c.keywords || ""}`).includes(w))) : all.filter((c) => c.group !== t("Businesses") && c.group !== t("Categories"))).slice(0, 60);
  palIndex = Math.min(palIndex, Math.max(0, palItems.length - 1));
  let last = "";
  $("pal-list").innerHTML = palItems.length
    ? palItems
        .map((c, i) => {
          const head = c.group !== last ? `<li class="pal-group" role="presentation">${esc(c.group)}</li>` : "";
          last = c.group;
          return `${head}<li role="option" id="pal-${i}" data-i="${i}" aria-selected="${i === palIndex}"><span>${esc(c.label)}</span>${c.hint ? `<small>${esc(c.hint)}</small>` : ""}</li>`;
        })
        .join("")
    : `<li class="pal-empty">${t("No results")}</li>`;
  $("pal-q").setAttribute("aria-activedescendant", `pal-${palIndex}`);
  document.getElementById(`pal-${palIndex}`)?.scrollIntoView({ block: "nearest" });
}
function openPalette() {
  $("pal-q").value = "";
  palIndex = 0;
  drawPalette();
  if (!$("palette").open) $("palette").showModal();
  $("pal-q").focus();
}
function runPalette(i) {
  const c = palItems[i];
  if (!c) return;
  $("palette").close();
  c.run();
}
$("open-palette").addEventListener("click", openPalette);
window.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    openPalette();
  }
});
$("pal-q").addEventListener("input", () => {
  palIndex = 0;
  drawPalette();
});
$("pal-q").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    palIndex = Math.max(0, Math.min(palItems.length - 1, palIndex + (e.key === "ArrowDown" ? 1 : -1)));
    drawPalette();
  } else if (e.key === "Enter") {
    e.preventDefault();
    runPalette(palIndex);
  }
});
$("pal-list").addEventListener("click", (e) => {
  const li = e.target.closest("[data-i]");
  if (li) runPalette(Number(li.dataset.i));
});
$("palette").addEventListener("click", (e) => e.target === $("palette") && $("palette").close());

applyStatic();

load("directory")
  .then((d) => {
    const hours = (Date.now() - new Date(d.meta.run_at).getTime()) / 3_600_000;
    $("run-text").textContent = t("Last run {time} · runs daily at 06:17 UTC", { time: ago(d.meta.run_at) });
    $("run").classList.add(hours > 36 ? "stale" : "ok");
  })
  .catch(() => ($("run-text").textContent = t("Latest run unavailable")));
// A pasted link with a different # opens that view without a reload.
window.addEventListener("hashchange", () => {
  const p = new URLSearchParams(location.hash.slice(1));
  show(p.get("set") === "books" ? "books" : "directory", p);
});
const shared = new URLSearchParams(location.hash.slice(1));
show(shared.get("set") === "books" ? "books" : "directory", shared.size ? shared : null);
