const $ = (selector) => document.querySelector(selector);
const state = {view: "mods", query: "", mod: "", type: "", coverage: "all", offset: 0, total: 0, showEmptyMods: false,
  selected: null, database: null, filters: null, jobId: null, detailRequest: 0, renderRequest: 0};
const PAGE_SIZE = 50;

function node(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== "") element.textContent = String(text);
  return element;
}
function append(parent, ...children) { parent.append(...children); return parent; }
function fmt(value) { return value == null ? "Unknown" : String(value); }
function count(value) { return Number(value || 0).toLocaleString(); }
function pretty(value) { return JSON.stringify(value, null, 2); }
function safeValue(value) { return value === null || value === undefined ? "Unknown" :
  typeof value === "object" ? JSON.stringify(value) : String(value); }
async function request(path, options = {}) {
  const response = await fetch(path, options);
  const kind = response.headers.get("content-type") || "";
  const data = kind.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
async function post(path, value) {
  return request(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(value)});
}
function toast(message) {
  const element = $("#toast"); element.textContent = message; element.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => { element.hidden = true; }, 5500);
}
function modalError(message) { const element = $("#modal-error"); element.textContent = message; element.hidden = false; }
function clearModalError() { $("#modal-error").hidden = true; }
function setModal(open) { $("#source-modal").hidden = !open; if (open) clearModalError(); }

async function loadStatus() {
  const data = await request("/api/status");
  state.database = data.database;
  const capture = data.capture;
  $("#snapshot-label").textContent = capture ? `${capture.minecraft_version || "Minecraft"} · NeoForge ${capture.neoforge_version || "?"} · ${capture.scope || "capture"} scope` : "No database open";
  $("#mod-count").textContent = capture ? count(capture.counts.mods) : "—";
  $("#item-count").textContent = capture ? count(capture.counts.items) : "—";
  $("#recipe-count").textContent = capture ? count(capture.counts.recipes) : "—";
  const card = $("#dataset-card"); card.replaceChildren();
  if (capture) {
    append(card, node("strong", "", `${count(capture.counts.items)} items · ${count(capture.counts.recipes)} recipes`),
      node("span", "", data.database), node("span", "", `Captured ${capture.generated_at_utc || "at an unknown time"}`));
  } else append(card, node("strong", "", "No capture loaded"), node("span", "", "Import a capture ZIP or open a database to begin."));
  for (const button of [$("#export-csv"), $("#export-json")]) button.disabled = !capture || !["items", "recipes"].includes(state.view);
  if (data.running_job && !state.jobId) { state.jobId = data.running_job; pollJob(); }
}
async function loadFilters() {
  if (!state.database) return;
  state.filters = await request("/api/filters");
  populateModFilter();
  const typeSelect = $("#type-filter"); typeSelect.replaceChildren(new Option("All recipe types", ""));
  for (const type of state.filters.recipe_types) typeSelect.add(new Option(`${type.type || "Unknown"} (${count(type.recipe_count)})`, type.type || ""));
  typeSelect.value = state.type;
}
function populateModFilter() {
  if (!state.filters) return;
  const modSelect = $("#mod-filter"); modSelect.replaceChildren(new Option("All mods", ""));
  for (const mod of state.filters.mods) {
    const amount = state.view === "recipes" ? mod.recipe_count : mod.item_count;
    if (amount || mod.id === state.mod) modSelect.add(new Option(`${mod.name} (${count(amount)})`, mod.id));
  }
  if (![...modSelect.options].some(option => option.value === state.mod)) state.mod = "";
  modSelect.value = state.mod;
}
function setView(view, preserveQuery = false) {
  state.view = view; state.offset = 0; state.selected = null;
  if (!preserveQuery) { state.query = ""; $("#search").value = ""; }
  populateModFilter();
  document.querySelectorAll("[data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  $("#type-filter-wrap").hidden = view !== "recipes";
  $("#filters-box").hidden = view === "coverage" || view === "mods";
  $(".heading-actions").hidden = view === "coverage" || view === "mods";
  $("#search-wrap").hidden = view === "coverage";
  $("#mod-scope").hidden = view !== "mods";
  $("#pagination").hidden = true;
  $("#view-eyebrow").textContent = view === "coverage" ? "COLLECTION HEALTH" : view === "mods" ? "MOD DIRECTORY" : "REGISTRY BROWSER";
  $("#view-title").textContent = ({mods: "Mods", items: "Items", recipes: "Recipes", coverage: "Coverage"})[view];
  $("#view-description").textContent = ({mods: "Choose a loaded mod to browse its items.",
    items: "Every item registered by the captured server.",
    recipes: "Effective loaded recipes, with their known inputs and outputs.",
    coverage: "See what the exporter collected and where facts are incomplete."})[view];
  $("#search").placeholder = view === "mods" ? "Search mod name or ID" :
    view === "recipes" ? "Search recipe ID or result item" : "Search item name or registry ID";
  for (const button of [$("#export-csv"), $("#export-json")]) button.disabled = !state.database || !["items", "recipes"].includes(view);
  renderModContext();
  render();
}
function renderModContext() {
  const active = !!state.mod && ["items", "recipes"].includes(state.view);
  $("#mod-context").hidden = !active;
  if (!active) return;
  const mod = state.filters?.mods.find(entry => entry.id === state.mod);
  $("#context-name").textContent = mod ? `${mod.name} · ${mod.version || "version unknown"}` : state.mod;
  $("#context-switch").textContent = state.view === "items" ? "View mod recipes →" : "View mod items →";
}
function filterParams() {
  const params = new URLSearchParams({q: state.query, mod: state.mod, coverage: state.coverage});
  if (state.view === "recipes") params.set("type", state.type);
  return params;
}
async function render() {
  const renderId = ++state.renderRequest;
  const target = $("#results"); target.replaceChildren();
  if (!state.database) {
    $("#result-count").textContent = "Choose a capture to explore";
    $("#page-label").textContent = "";
    $("#detail-panel").replaceChildren(emptyDetail());
    target.append(emptyState("No database open", "Capture a Packwiz pack or import a saved capture ZIP to start browsing."));
    return;
  }
  try {
    if (state.view === "coverage") return renderCoverage(renderId);
    const params = filterParams(); params.set("limit", PAGE_SIZE); params.set("offset", state.offset);
    if (state.view === "mods") params.set("all", state.showEmptyMods ? "1" : "0");
    const data = await request(`/api/${state.view}?${params}`);
    if (renderId !== state.renderRequest) return;
    state.total = data.total;
    const rows = data[state.view];
    $("#result-count").textContent = `${count(data.total)} ${state.view} found`;
    $("#page-label").textContent = data.total ? `${count(state.offset + 1)}–${count(state.offset + rows.length)} of ${count(data.total)}` : "";
    if (!rows.length) {
      target.append(emptyState("No matches", "Try another search or adjust the filters."));
      $("#detail-panel").replaceChildren(emptyDetail());
    } else {
      for (const row of rows) target.append(state.view === "mods" ? modCard(row) : state.view === "items" ? itemCard(row) : recipeCard(row));
      if (state.view === "mods") $("#detail-panel").replaceChildren(modsPlaceholder());
      else if (!state.selected || !rows.some(row => row.id === state.selected.id)) selectRecord(state.view, rows[0].id);
      else markSelected();
    }
    $("#pagination").hidden = data.total <= PAGE_SIZE;
    $("#prev-page").disabled = state.offset === 0;
    $("#next-page").disabled = state.offset + PAGE_SIZE >= data.total;
    $("#pagination-label").textContent = `Page ${Math.floor(state.offset / PAGE_SIZE) + 1} of ${Math.ceil(data.total / PAGE_SIZE)}`;
  } catch (error) { toast(error.message); }
}
function emptyState(title, message) { return append(node("div", "empty"), node("strong", "", title), node("span", "", message)); }
function emptyDetail() { return append(node("div", "detail-placeholder"), node("span", "", "◇"),
  node("h2", "", "Inspect the data"), node("p", "", "Select an item or recipe to see what the server reported and what remains unknown.")); }
function modsPlaceholder() { return append(node("div", "detail-placeholder"), node("span", "", "▦"),
  node("h2", "", "Browse by mod"), node("p", "", "Select a mod to open its item collection. From there, switch to the same mod’s recipes.")); }
function chip(text, kind = "") { return node("span", `mini-chip ${kind}`, text); }
function modCard(mod) {
  const card = node("button", "result-card mod-card"); card.type = "button"; card.dataset.id = mod.id;
  append(card, append(node("div", "result-title-row"), node("span", "result-title", mod.name),
    node("span", "result-aside", mod.version || "Version unknown")),
    node("div", "result-id", mod.id), append(node("div", "result-foot"),
      chip(`${count(mod.item_count)} items`, "teal"), chip(`${count(mod.recipe_count)} recipes`)));
  card.addEventListener("click", () => { state.mod = mod.id; state.coverage = "all"; $("#coverage-filter").value = "all"; setView("items"); });
  return card;
}
function itemCard(item) {
  const card = node("button", "result-card"); card.type = "button"; card.dataset.id = item.id;
  const title = append(node("div", "result-title-row"), node("span", "result-title", item.display_name || item.id),
    node("span", "result-aside", item.max_stack_size == null ? "" : `Stack ${item.max_stack_size}`));
  const foot = append(node("div", "result-foot"), chip(item.mod_name || item.mod_id || "Unknown mod", "teal"));
  if (item.rarity) foot.append(chip(item.rarity));
  if (item.detail_status !== "collected" || item.component_status !== "collected" || item.block_entity_type_status === "unavailable") foot.append(chip("Incomplete", "warn"));
  append(card, title, node("div", "result-id", item.id), foot);
  card.addEventListener("click", () => selectRecord("items", item.id));
  return card;
}
function recipeCard(recipe) {
  const card = node("button", "result-card"); card.type = "button"; card.dataset.id = recipe.id;
  const title = node("div", "result-title", recipe.id);
  const foot = append(node("div", "result-foot"), chip(recipe.type || "Unknown type", "teal"));
  if (recipe.source_pack_id) foot.append(chip(recipe.source_pack_id));
  if (recipe.input_status !== "collected" || recipe.output_status !== "collected" || recipe.semantic_status !== "core_fields") foot.append(chip("Partial", "warn"));
  append(card, title, node("div", "result-id", recipe.result_item_id ? `→ ${recipe.result_item_id}` : "Dynamic result"),
    node("div", "result-id", recipe.serializer || "No serializer ID"), foot);
  card.addEventListener("click", () => selectRecord("recipes", recipe.id));
  return card;
}
function markSelected() {
  document.querySelectorAll(".result-card").forEach(card => card.classList.toggle("selected", !!state.selected && card.dataset.id === state.selected.id));
}
async function selectRecord(kind, id) {
  state.selected = {kind, id}; markSelected();
  const serial = ++state.detailRequest;
  try {
    const record = await request(`/api/${kind}/${encodeURIComponent(id)}`);
    if (serial !== state.detailRequest) return;
    $("#detail-panel").replaceChildren(kind === "items" ? itemDetail(record) : recipeDetail(record));
  } catch (error) { toast(error.message); }
}
function section(title, content) { return append(node("section", "detail-section"), node("h3", "", title), content); }
function fact(label, value) { return append(node("div", "fact"), node("small", "", label), node("strong", "", safeValue(value))); }
function row(label, value) { return append(node("div", "line-item"), node("strong", "", `${label}: `), node("span", "", safeValue(value))); }
function linkList(ids, kind) {
  const list = node("div", "link-list");
  for (const id of ids) {
    const button = node("button", "", id); button.type = "button";
    button.addEventListener("click", () => jump(kind, id)); list.append(button);
  }
  return list;
}
function jump(kind, id) {
  state.query = id; state.mod = ""; state.type = ""; state.coverage = "all";
  $("#search").value = id; $("#mod-filter").value = ""; $("#type-filter").value = ""; $("#coverage-filter").value = "all";
  setView(kind, true);
}
function itemDetail(item) {
  const root = node("div");
  const head = append(node("div", "detail-head"), node("div", "eyebrow", "ITEM RECORD"),
    node("h2", "", item.display_name || item.id), node("div", "detail-id", item.id),
    node("p", "detail-subtitle", `${item.mod_name || item.mod_id || "Source mod not identified"}${item.mod_version ? ` · ${item.mod_version}` : ""} · ${item.implementation_class || "Unknown implementation"}`));
  root.append(head);
  root.append(section("Core facts", append(node("div", "fact-grid"), fact("Max stack", item.max_stack_size),
    fact("Max damage", item.max_damage), fact("Rarity", item.rarity), fact("Associated block", item.block_id))));
  if (item.detail_status !== "collected" || item.component_status !== "collected" || item.block_entity_type_status === "unavailable") {
    root.append(section("Collection limits", append(node("div", "line-list"), row("Item detail", item.detail_status),
      row("Components", item.component_status), row("Block entity type", item.block_entity_type_status))));
  }
  root.append(section(`Recipes making this item · ${count(item.makes.length)}`, item.makes.length ? linkList(item.makes, "recipes") : node("p", "detail-subtitle", "No exposed final output found.")));
  root.append(section(`Recipes using this item · ${count(item.uses.length)}`, item.uses.length ? linkList(item.uses, "recipes") : node("p", "detail-subtitle", "No exposed direct or tag-based input found.")));
  const tags = append(node("div", "chip-list"), ...item.item_tags.map(tag => chip(tag)));
  root.append(section(`Item tags · ${count(item.item_tags.length)}`, item.item_tags.length ? tags : node("p", "detail-subtitle", "No captured item tags.")));
  if (item.block) {
    const block = append(node("div", "line-list"), row("Block", item.block.id), row("Implementation", item.block.implementation_class),
      row("Block entity types", item.block_entity_types.length ? item.block_entity_types.join(", ") : item.block_entity_type_status));
    for (const property of item.block_state_properties) block.append(row(property.name, property.allowed_values.join(", ")));
    if (item.block_tags.length) block.append(row("Block tags", item.block_tags.join(", ")));
    root.append(section("Associated block", block));
  }
  const components = node("div", "line-list");
  for (const component of item.components) components.append(row(component.component_id,
    component.status === "captured" ? component.value : component.status));
  root.append(section(`Default components · ${count(item.components.length)}`, components));
  const properties = node("div", "line-list");
  for (const property of item.properties) properties.append(row(property.property_key,
    property.status === "captured_directly" || property.status === "derived" ?
      `${safeValue(property.value)}${property.unit ? ` ${property.unit}` : ""}` : property.status));
  root.append(section(`Mechanics & properties · ${count(item.properties.length)}`,
    item.properties.length ? properties : node("p", "detail-subtitle", "No item-specific mechanic facts were collected.")));
  return root;
}
function termLine(term) {
  const line = node("div", "line-item");
  const prefix = term.sequence_step == null ? "" : `Step ${term.sequence_step + 1} · `;
  line.append(node("strong", "", `${prefix}${term.kind.replaceAll("_", " ")} `));
  if (term.kind === "item" && term.target_id) {
    const link = node("a", "", term.target_id); link.href = "#";
    link.addEventListener("click", event => { event.preventDefault(); jump("items", term.target_id); });
    line.append(link);
  } else line.append(node("span", "", term.target_id || "Unknown target"));
  const meta = [term.quantity == null ? null : `×${term.quantity}`, term.chance == null ? null : `${term.chance} chance`, term.path].filter(Boolean);
  if (meta.length) line.append(node("span", "", ` · ${meta.join(" · ")}`));
  return line;
}
function jsonDisclosure(title, value) {
  const details = node("details"); details.append(node("summary", "", title), node("pre", "", pretty(value))); return details;
}
function recipeDetail(recipe) {
  const root = node("div");
  root.append(append(node("div", "detail-head"), node("div", "eyebrow", "LOADED RECIPE"),
    node("h2", "", recipe.id), node("div", "detail-id", recipe.type || "Unknown type"),
    node("p", "detail-subtitle", recipe.source_pack_id ? `Active source: ${recipe.source_pack_id}` : "No source resource identified")));
  root.append(section("Identity", append(node("div", "line-list"), row("Serializer", recipe.serializer),
    row("Implementation", recipe.implementation_class), row("Source resource", recipe.source_resource_id))));
  root.append(section("Collection status", append(node("div", "line-list"), row("Detail", recipe.detail_status),
    row("Inputs", recipe.input_status), row("Outputs", recipe.output_status), row("Semantics", recipe.semantic_status))));
  const groups = [["Inputs", ["input", "catalyst"]], ["Final outputs", ["output"]], ["Intermediate outputs", ["intermediate_output"]]];
  for (const [title, roles] of groups) {
    const terms = recipe.terms.filter(term => roles.includes(term.role));
    if (terms.length || title !== "Intermediate outputs") root.append(section(`${title} · ${count(terms.length)}`,
      terms.length ? append(node("div", "line-list"), ...terms.map(termLine)) : node("p", "detail-subtitle", "No normalized facts exposed.")));
  }
  if (recipe.detail) {
    const raw = node("div");
    if (recipe.detail.source_json != null) raw.append(jsonDisclosure("Active source JSON", recipe.detail.source_json));
    if (recipe.detail.codec_json != null) raw.append(jsonDisclosure("Serializer representation", recipe.detail.codec_json));
    raw.append(jsonDisclosure("Complete detail record", recipe.detail));
    root.append(section("Evidence & custom fields", raw));
  }
  return root;
}
async function renderCoverage(renderId) {
  try {
    const data = await request("/api/coverage");
    if (renderId !== state.renderRequest) return;
    const labels = [["item_details", "Item detail"], ["item_components", "Default components"],
      ["block_entity_types", "Block entity types"], ["recipe_inputs", "Recipe inputs"],
      ["recipe_outputs", "Recipe outputs"], ["recipe_semantics", "Recipe semantics"], ["properties", "Mechanic properties"]];
    const grid = node("div", "coverage-grid");
    for (const [key, title] of labels) {
      const card = append(node("div", "coverage-card"), node("h3", "", title));
      for (const item of data[key]) card.append(append(node("div", `coverage-line ${/failed|unavailable|partial|unsupported|legacy/.test(item.status) ? "bad" : ""}`),
        node("span", "", item.status.replaceAll("_", " ")), node("strong", "", count(item.count))));
      grid.append(card);
    }
    const target = $("#results"); target.replaceChildren(grid);
    const types = append(node("div", "line-list"));
    for (const entry of data.incomplete_recipe_types) {
      const button = node("button", "result-card"); button.type = "button";
      append(button, node("div", "result-title", entry.type), node("div", "result-id", `${count(entry.count)} recipes with incomplete semantics`));
      button.addEventListener("click", () => { state.type = entry.type === "<unknown>" ? "" : entry.type; $("#type-filter").value = state.type; state.coverage = "incomplete"; $("#coverage-filter").value = "incomplete"; setView("recipes"); });
      types.append(button);
    }
    target.append(section("Recipe types needing interpretation", types));
    $("#result-count").textContent = "Collection coverage by area";
    $("#page-label").textContent = "";
    $("#detail-panel").replaceChildren(append(node("div", "detail-placeholder"), node("span", "", "◌"),
      node("h2", "", "Unknown stays unknown"), node("p", "", "A missing or unsupported fact is shown with its collection status. It is never treated as zero or proof that no recipe exists.")));
  } catch (error) { toast(error.message); }
}
async function pollJob() {
  if (!state.jobId) return;
  try {
    const job = await request(`/api/jobs/${state.jobId}`);
    $("#job-box").hidden = false;
    $("#job-title").textContent = job.kind === "capture" ? "Pack capture" : "Capture import";
    $("#job-status").textContent = job.status;
    $("#job-status").classList.toggle("warn", job.status === "failed");
    const log = $("#job-log"); log.textContent = job.log.join("\n"); log.scrollTop = log.scrollHeight;
    if (job.status === "running") return setTimeout(pollJob, 1800);
    state.jobId = null;
    if (job.status === "failed") return modalError(job.error || "Job failed");
    toast("Database ready to browse");
    await loadStatus(); await loadFilters(); setView("mods");
  } catch (error) { modalError(error.message); state.jobId = null; }
}
async function handleCapture() {
  clearModalError();
  try {
    let source = $("#pack-source").value.trim();
    const file = $("#pack-file").files[0];
    if (file) {
      const uploaded = await request("/api/upload-pack", {method: "POST", headers: {"Content-Type": "application/zip"}, body: file});
      source = uploaded.path;
    }
    const result = await post("/api/capture", {source, java: $("#java-path").value.trim(), memory: $("#memory").value.trim(), eula: $("#eula").checked});
    state.jobId = result.job_id; pollJob();
  } catch (error) { modalError(error.message); }
}
async function handleImport() {
  clearModalError();
  try {
    const file = $("#capture-file").files[0];
    const result = file ? await request("/api/import", {method: "POST", headers: {"Content-Type": "application/zip"}, body: file}) :
      await post("/api/import-path", {path: $("#capture-path").value.trim()});
    state.jobId = result.job_id; pollJob();
  } catch (error) { modalError(error.message); }
}
function exportCurrent(format) {
  if (!state.database || !["items", "recipes"].includes(state.view)) return;
  const params = filterParams(); params.set("kind", state.view); params.set("format", format);
  window.location.href = `/api/export?${params}`;
}
function bindEvents() {
  document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => setView(button.dataset.view)));
  for (const id of ["#open-source", "#open-source-side"]) $(id).addEventListener("click", () => setModal(true));
  $("#close-source").addEventListener("click", () => setModal(false));
  $("#source-modal").addEventListener("click", event => { if (event.target === $("#source-modal")) setModal(false); });
  document.querySelectorAll("[data-source-tab]").forEach(button => button.addEventListener("click", () => {
    document.querySelectorAll("[data-source-tab]").forEach(tab => tab.classList.toggle("active", tab === button));
    for (const tab of ["capture", "import", "open"]) $(`#${tab}-form`).hidden = tab !== button.dataset.sourceTab;
    clearModalError();
  }));
  let searchTimer;
  $("#search").addEventListener("input", event => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.query = event.target.value.trim(); state.offset = 0; render(); }, 220); });
  $("#mod-filter").addEventListener("change", event => { state.mod = event.target.value; state.offset = 0; render(); });
  $("#type-filter").addEventListener("change", event => { state.type = event.target.value; state.offset = 0; render(); });
  $("#coverage-filter").addEventListener("change", event => { state.coverage = event.target.value; state.offset = 0; render(); });
  $("#show-empty-mods").addEventListener("change", event => { state.showEmptyMods = event.target.checked; state.offset = 0; render(); });
  $("#back-mods").addEventListener("click", () => { state.mod = ""; setView("mods"); });
  $("#context-switch").addEventListener("click", () => setView(state.view === "items" ? "recipes" : "items"));
  $("#prev-page").addEventListener("click", () => { state.offset = Math.max(0, state.offset - PAGE_SIZE); render(); window.scrollTo(0, 0); });
  $("#next-page").addEventListener("click", () => { state.offset += PAGE_SIZE; render(); window.scrollTo(0, 0); });
  $("#export-csv").addEventListener("click", () => exportCurrent("csv"));
  $("#export-json").addEventListener("click", () => exportCurrent("json"));
  $("#start-capture").addEventListener("click", handleCapture);
  $("#start-import").addEventListener("click", handleImport);
  $("#open-database").addEventListener("click", async () => {
    clearModalError();
    try { await post("/api/open-database", {path: $("#database-path").value.trim()}); await loadStatus(); await loadFilters(); setView("mods"); setModal(false); }
    catch (error) { modalError(error.message); }
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") setModal(false);
    if (event.key === "/" && !$("#source-modal").hidden) return;
    if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) { event.preventDefault(); $("#search").focus(); }
  });
}
bindEvents();
loadStatus().then(loadFilters).then(() => setView("mods")).catch(error => toast(error.message));
