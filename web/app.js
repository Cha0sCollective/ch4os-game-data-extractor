const $ = (selector) => document.querySelector(selector);
const state = {view: "mods", query: "", mod: "", type: "", coverage: "all", offset: 0, total: 0, showEmptyMods: false,
  selected: null, database: null, filters: null, jobId: null, detailRequest: 0, renderRequest: 0, comparison: null};
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
  if (state.database !== data.database) state.comparison = null;
  state.database = data.database;
  const capture = data.capture;
  $("#snapshot-label").textContent = capture ? `${capture.minecraft_version || "Minecraft"} · NeoForge ${capture.neoforge_version || "?"} · ${capture.scope || "capture"} scope` : "No database open";
  $("#mod-count").textContent = capture ? count(capture.counts.mods) : "—";
  $("#item-count").textContent = capture ? count(capture.counts.items) : "—";
  $("#recipe-count").textContent = capture ? count(capture.counts.recipes) : "—";
  $("#definition-count").textContent = capture ? count(capture.counts.adapter_definitions) : "—";
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
  if (state.view === "adapter-definitions") {
    modSelect.replaceChildren(new Option("All adapters", ""));
    for (const adapter of state.filters.adapters || []) modSelect.add(new Option(`${adapter.adapter_id} (${count(adapter.definition_count)})`, adapter.adapter_id));
    if (![...modSelect.options].some(option => option.value === state.mod)) state.mod = "";
    modSelect.value = state.mod;
    return;
  }
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
  $("#coverage-filter-wrap").hidden = view === "adapter-definitions" || view === "research";
  $("#mod-filter-label").textContent = view === "adapter-definitions" ? "Adapter" : "Mod / namespace";
  $("#filters-box").hidden = ["coverage", "mods", "analysis"].includes(view);
  $(".heading-actions").hidden = ["coverage", "mods", "analysis", "adapter-definitions", "research"].includes(view);
  $("#search-wrap").hidden = view === "coverage" || view === "analysis" || view === "research";
  $("#mod-scope").hidden = view !== "mods";
  $("#analysis-controls").hidden = view !== "analysis";
  $("#research-controls").hidden = view !== "research";
  $("#pagination").hidden = true;
  $("#view-eyebrow").textContent = view === "research" ? "EVIDENCE REVIEW" : view === "analysis" ? "RECIPE VALIDATION" : view === "coverage" ? "COLLECTION HEALTH" : view === "mods" ? "MOD DIRECTORY" : "REGISTRY BROWSER";
  $("#view-title").textContent = ({mods: "Mods", items: "Items", recipes: "Recipes", "adapter-definitions": "Gameplay data", analysis: "Analysis", coverage: "Coverage", research: "Research"})[view];
  $("#view-description").textContent = ({mods: "Choose a loaded mod to browse its items.",
    items: "Every item registered by the captured server.",
    recipes: "Effective loaded recipes, with their known inputs and outputs.",
    "adapter-definitions": "Fuel tables, wire ratings, specialized processes, and peripheral APIs from installed mods.",
    analysis: "Exact-input conflicts, ingredient gaps, and changes between captures.",
    coverage: "See what the exporter collected and where facts are incomplete.",
    research: "Prepare source-analysis jobs, review findings, and track mod coverage."})[view];
  $("#search").placeholder = view === "mods" ? "Search mod name or ID" :
    view === "recipes" ? "Search recipe ID or result item" :
    view === "adapter-definitions" ? "Search gameplay ID or kind" : "Search item name or registry ID";
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
  if (state.view === "adapter-definitions") params.set("adapter", state.mod);
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
    if (state.view === "coverage") return await renderCoverage(renderId);
    if (state.view === "analysis") return await renderAnalysis(renderId);
    if (state.view === "research") return await renderResearch(renderId);
    const params = filterParams(); params.set("limit", PAGE_SIZE); params.set("offset", state.offset);
    if (state.view === "mods") params.set("all", state.showEmptyMods ? "1" : "0");
    const data = await request(`/api/${state.view}?${params}`);
    if (renderId !== state.renderRequest) return;
    state.total = data.total;
    const rows = data[state.view === "adapter-definitions" ? "adapter_definitions" : state.view];
    $("#result-count").textContent = `${count(data.total)} ${state.view === "adapter-definitions" ? "gameplay records" : state.view} found`;
    $("#page-label").textContent = data.total ? `${count(state.offset + 1)}–${count(state.offset + rows.length)} of ${count(data.total)}` : "";
    if (!rows.length) {
      target.append(emptyState("No matches", "Try another search or adjust the filters."));
      $("#detail-panel").replaceChildren(emptyDetail());
    } else {
      for (const row of rows) target.append(state.view === "mods" ? modCard(row) : state.view === "items" ? itemCard(row) :
        state.view === "recipes" ? recipeCard(row) : definitionCard(row));
      if (state.view === "mods") $("#detail-panel").replaceChildren(modsPlaceholder());
      else if (state.view === "adapter-definitions") {
        if (!state.selected || !rows.some(row => definitionKey(row) === state.selected.id)) selectDefinition(rows[0]);
        else markSelected();
      }
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
function definitionKey(entry) { return `${entry.adapter_id}|${entry.kind}|${entry.id}`; }
function definitionCard(entry) {
  const card = node("button", "result-card"); card.type = "button"; card.dataset.id = definitionKey(entry);
  append(card, node("div", "result-title", entry.id), node("div", "result-id", entry.kind.replaceAll("_", " ")),
    append(node("div", "result-foot"), chip(entry.adapter_id, "teal"), chip(entry.status)));
  card.addEventListener("click", () => selectDefinition(entry));
  return card;
}
async function selectDefinition(entry) {
  state.selected = {kind: "adapter-definitions", id: definitionKey(entry)}; markSelected();
  const serial = ++state.detailRequest;
  const params = new URLSearchParams({adapter: entry.adapter_id, kind: entry.kind, id: entry.id});
  try {
    const record = await request(`/api/adapter-definitions/detail?${params}`);
    if (serial !== state.detailRequest) return;
    $("#detail-panel").replaceChildren(definitionDetail(record));
  } catch (error) { toast(error.message); }
}
function definitionDetail(entry) {
  const root = node("div");
  root.append(append(node("div", "detail-head"), node("div", "eyebrow", "GAMEPLAY DEFINITION"),
    node("h2", "", entry.id), node("div", "detail-id", entry.kind.replaceAll("_", " ")),
    node("p", "detail-subtitle", `${entry.adapter_id} · ${entry.status}`)));
  const values = node("div", "line-list");
  for (const [key, value] of Object.entries(entry.attributes || {})) values.append(
    value && typeof value === "object" ? jsonDisclosure(key.replaceAll("_", " "), value) : row(key.replaceAll("_", " "), value));
  root.append(section("Captured values", values));
  if (entry.conditions) root.append(section("Conditions and limits", jsonDisclosure("Evidence conditions", entry.conditions)));
  if (entry.adapter_id === "create_display_links") {
    const items = [...new Set((entry.relations || [])
      .filter(link => link.subject_kind === "item" &&
        ["provides_display_source", "accepts_display_output"].includes(link.predicate))
      .map(link => link.subject_id))];
    root.append(section(`Registered item-backed blocks · ${count(items.length)}`,
      items.length ? linkList(items, "items") : node("p", "detail-subtitle", "No item-backed block was registered for this type.")));
  } else {
    const links = node("div", "line-list");
    for (const link of entry.relations || []) links.append(row(`${link.predicate.replaceAll("_", " ")} · ${link.subject_id}`,
      `${link.object_kind}: ${link.object_id}`));
    root.append(section(`Relationships · ${count((entry.relations || []).length)}`, links));
  }
  root.append(section("Provenance", append(node("div", "line-list"), row("Source API", entry.source_api),
    row("Resource", entry.source_resource_id), row("Source pack", entry.source_pack_id),
    row("Installed mod versions", entry.source_record?.required_mod_versions), row("SHA-256", entry.source_sha256))));
  return root;
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
function propertyRow(property) {
  const value = property.status === "captured_directly" || property.status === "derived" ?
    `${safeValue(property.value)}${property.unit ? ` ${property.unit}` : ""}` : property.status.replaceAll("_", " ");
  const line = append(node("div", "line-item"), node("strong", "", `${property.property_key}: `), node("span", "", value));
  const context = property.conditions ? Object.entries(property.conditions).map(([key, entry]) => `${key.replaceAll("_", " ")}: ${safeValue(entry)}`) : [];
  if (context.length) line.append(node("div", "property-meta", context.join(" · ")));
  if (property.source) line.append(node("div", "property-meta", `Installed runtime · ${property.source}`));
  return line;
}
function relationLine(link, reviewed = false) {
  const line = node("div", "line-item");
  const targetKind = link.direction === "incoming" ? link.subject_kind : link.object_kind;
  const targetId = link.direction === "incoming" ? link.subject_id : link.object_id;
  line.append(node("strong", "", `${link.predicate.replaceAll("_", " ")}: `));
  if (targetKind === "item" || targetKind === "recipe") {
    const button = node("button", "subtle-button", targetId + " →");
    button.type = "button"; button.addEventListener("click", () => jump(targetKind === "item" ? "items" : "recipes", targetId));
    line.append(button);
  } else line.append(node("span", "", `${targetKind}: ${targetId}`));
  line.append(node("div", "property-meta", `${link.direction || "outgoing"} · ${reviewed ? link.evidence_status.replaceAll("_", " ") : "installed runtime"}${link.adapter_id ? ` · ${link.adapter_id}` : ""}`));
  if (link.conditions && Object.keys(link.conditions).length) line.append(jsonDisclosure("Conditions", link.conditions));
  if (reviewed && link.evidence_locator) line.append(node("div", "property-meta", `Evidence: ${link.evidence_locator}`));
  else if (link.source_api) line.append(node("div", "property-meta", `Source: ${link.source_api}`));
  return line;
}
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
  for (const property of item.properties) properties.append(propertyRow(property));
  root.append(section(`Mechanics & properties · ${count(item.properties.length)}`,
    item.properties.length ? properties : node("p", "detail-subtitle", "No item-specific mechanic facts were collected.")));
  const reviewed = item.reviewed || {claims: [], relations: [], formulas: [], coverage: []};
  const claims = node("div", "line-list");
  for (const claim of reviewed.claims) {
    const line = row(claim.predicate.replaceAll("_", " "), `${safeValue(claim.value)}${claim.unit ? ` ${claim.unit}` : ""}`);
    line.append(node("div", "property-meta", `${claim.evidence_status.replaceAll("_", " ")} · ${claim.evidence_locator}`));
    if (claim.conditions && Object.keys(claim.conditions).length) line.append(jsonDisclosure("Conditions", claim.conditions));
    claims.append(line);
  }
  for (const formula of reviewed.formulas) {
    const line = row(formula.result_predicate.replaceAll("_", " "), `Formula · ${formula.unit || "unit unspecified"}`);
    line.append(node("div", "property-meta", `${formula.evidence_status.replaceAll("_", " ")} · ${formula.evidence_locator}`),
      jsonDisclosure("Expression and conditions", {expression: formula.expression, conditions: formula.conditions}));
    claims.append(line);
  }
  if (claims.childElementCount) root.append(section(`Reviewed specifications · ${count(claims.childElementCount)}`, claims));
  const links = [...(item.relations || []).map(link => relationLine(link)),
    ...reviewed.relations.map(link => relationLine(link, true))];
  root.append(section(`Relationships · ${count(links.length)}`, links.length ? append(node("div", "line-list"), ...links) :
    node("p", "detail-subtitle", "No relationships have been captured or reviewed for this item.")));
  if (reviewed.coverage.length) root.append(section("Research coverage", append(node("div", "line-list"),
    ...reviewed.coverage.map(entry => row(entry.area.replaceAll("_", " "), `${entry.status.replaceAll("_", " ")} · ${entry.explanation}`)))));
  const ccRegistered = item.properties.some(property =>
    property.property_key === "integration.computercraft.peripheral_registered" && property.value === true);
  if (ccRegistered || item.cc_peripherals?.length) {
    const peripheralList = node("div", "line-list");
    if (ccRegistered) peripheralList.append(row("Registration", "CC peripheral capability registered for the placed block"));
    for (const peripheral of item.cc_peripherals) {
      const attrs = peripheral.attributes || {};
      const methods = [...new Set((attrs.lua_methods || []).flatMap(method => method.lua_names || [method.java_name]))];
      const link = node("button", "subtle-button", `${peripheral.id} →`);
      link.type = "button";
      link.addEventListener("click", () => jump("adapter-definitions", peripheral.id));
      peripheralList.append(link, row("Provider", `${attrs.provider_mod || "Unknown"} ${attrs.provider_version || ""}`),
        row("Lua methods", methods.length ? methods.join(", ") : "No annotated methods collected"),
        row("Attachment", peripheral.link_conditions?.attachment || "Requires a placed block and computer"));
    }
    root.append(section("ComputerCraft integration", peripheralList));
  }
  if (item.display_link_roles?.length) {
    const isLink = item.id === "create:display_link";
    const roles = node("div", "line-list");
    roles.append(node("p", "detail-subtitle", isLink
      ? "Source and target types registered by the loaded pack. A placed Display Link needs a suitable block at each end."
      : "This placed block has the following Display Link roles; available options can depend on its world state."));
    const groups = isLink
      ? [["Registered source types", "supports_display_source"], ["Registered target types", "supports_display_target"]]
      : [["Displayable from this block", "provides_display_source"], ["Can receive display output", "accepts_display_output"]];
    for (const [label, predicate] of groups) {
      const entries = item.display_link_roles.filter(role => role.predicate === predicate);
      if (!entries.length) continue;
      const list = node("div", "line-list");
      for (const role of entries) {
        const link = node("button", "subtle-button", `${role.id} →`);
        link.type = "button";
        link.addEventListener("click", () => jump("adapter-definitions", role.id));
        list.append(link);
        if (!isLink && role.link_attributes?.registration_basis?.length)
          list.append(row("Registered through", role.link_attributes.registration_basis.join(", ")));
      }
      if (isLink) {
        const disclosure = node("details");
        disclosure.append(node("summary", "", `${label} · ${count(entries.length)}`), list);
        roles.append(disclosure);
      } else roles.append(node("h3", "", `${label} · ${count(entries.length)}`), list);
    }
    root.append(section("Display Link", roles));
  }
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
  if (recipe.cross_mod_relations?.length) {
    const links = node("div", "line-list");
    for (const relation of recipe.cross_mod_relations) {
      const target = node("button", "subtle-button", `${relation.predicate.replaceAll("_", " ")} · ${relation.object_id} →`);
      target.type = "button";
      target.addEventListener("click", () => jump(relation.object_kind === "recipe" ? "recipes" : "adapter-definitions", relation.object_id));
      links.append(target);
      if (relation.attributes?.target_recipe_type) links.append(row("Runs as", relation.attributes.target_recipe_type));
      if (relation.attributes?.source_recipe_id) links.append(row("Source recipe", relation.attributes.source_recipe_id));
    }
    root.append(section(`Cross-mod processes · ${count(recipe.cross_mod_relations.length)}`, links));
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
async function renderResearch(renderId) {
  try {
    const params = new URLSearchParams({mod: state.mod, status: "pending"});
    const data = await request(`/api/research?${params}`);
    if (renderId !== state.renderRequest) return;
    const target = $("#results"); target.replaceChildren();
    $("#pagination").hidden = true;
    $("#result-count").textContent = `${count(data.findings.length)} pending findings · ${count((data.adapter_tasks || []).filter(task => task.status === "open").length)} adapter tasks · ${count(data.jobs.length)} jobs`;
    $("#page-label").textContent = state.mod || "All mods";
    if (data.coverage) {
      const coverage = append(node("div", "coverage-grid"),
        analysisMetric("Mod items", data.coverage.item_count),
        analysisMetric("Items with any reviewed coverage", data.coverage.items_with_coverage),
        analysisMetric("Items awaiting coverage", data.coverage.items_without_coverage),
        analysisMetric("Unresolved systems", (data.coverage.system_areas || []).filter(entry => entry.status === "unresolved").length));
      target.append(coverage);
      const systems = node("div", "results");
      for (const entry of data.coverage.system_areas || []) systems.append(append(node("div", "result-card"),
        node("div", "result-title", `${entry.subject_id} · ${entry.area.replaceAll("_", " ")}`),
        node("div", "result-id", entry.explanation),
        append(node("div", "result-foot"), chip(entry.status, entry.status === "unresolved" ? "warn" : "teal"))));
      if (systems.childElementCount) target.append(section("Gameplay system coverage", systems));
      for (const entry of data.coverage.revalidation || []) target.append(node("p", "muted-note",
        `Revalidate ${state.mod}: ${entry.reason.replaceAll("_", " ")} · ${entry.status}`));
    }
    const findings = node("div", "results");
    for (const entry of data.findings) {
      const finding = entry.finding;
      const card = append(node("button", "result-card"),
        node("div", "result-title", `${finding.record_type.replaceAll("_", " ")} · ${finding.subject_id}`),
        node("div", "result-id", finding.predicate || finding.result_predicate || finding.area || finding.description || entry.id),
        append(node("div", "result-foot"), chip(entry.status, "warn"), chip(finding.evidence?.kind || "review needed")));
      card.type = "button";
      card.addEventListener("click", () => {
        const detail = append(node("div"), append(node("div", "detail-head"), node("div", "eyebrow", "PROPOSED FINDING"),
          node("h2", "", finding.subject_id), node("div", "detail-id", entry.id)),
          section("Agent evidence and conditions", jsonDisclosure("Complete finding", finding)));
        const actions = node("div", "review-actions");
        for (const decision of ["accept", "reject"]) {
          const button = node("button", decision === "accept" ? "primary-button" : "outline-button", decision === "accept" ? "Accept finding" : "Reject finding");
          button.type = "button";
          button.addEventListener("click", async () => {
            try {
              await post("/api/research/review", {finding_id: entry.id, decision});
              toast(`Finding ${decision === "accept" ? "accepted" : "rejected"}`);
              render();
            } catch (error) { toast(error.message); }
          });
          actions.append(button);
        }
        detail.append(actions);
        $("#detail-panel").replaceChildren(detail);
      });
      findings.append(card);
    }
    target.append(section(`Pending findings · ${count(data.findings.length)}`,
      data.findings.length ? findings : node("p", "detail-subtitle", "No agent findings await review.")));
    const tasks = node("div", "results");
    for (const task of data.adapter_tasks || []) {
      const card = append(node("button", "result-card"),
        node("div", "result-title", `${task.mod_id} · ${task.subject_id}`),
        node("div", "result-id", task.description),
        append(node("div", "result-foot"), chip(task.status, task.status === "open" ? "warn" : "teal")));
      card.type = "button";
      card.addEventListener("click", () => {
        const detail = append(node("div"), append(node("div", "detail-head"),
          node("div", "eyebrow", "REVIEWED ADAPTER TASK"), node("h2", "", task.subject_id),
          node("div", "detail-id", task.finding_id)),
          section("Capture gap", node("p", "detail-subtitle", task.description)));
        if (task.resolution) detail.append(section("Resolution", node("p", "detail-subtitle", task.resolution)));
        if (task.status === "open") {
          const button = node("button", "outline-button", "Record resolution");
          button.type = "button";
          button.addEventListener("click", async () => {
            const resolution = window.prompt("Capture or test evidence for this completed adapter change:");
            if (!resolution?.trim()) return;
            try {
              await post("/api/research/resolve-task", {finding_id: task.finding_id, resolution: resolution.trim()});
              toast("Adapter task resolved"); render();
            } catch (error) { toast(error.message); }
          });
          detail.append(button);
        }
        $("#detail-panel").replaceChildren(detail);
      });
      tasks.append(card);
    }
    target.append(section(`Adapter tasks · ${count((data.adapter_tasks || []).length)}`,
      tasks.childElementCount ? tasks : node("p", "detail-subtitle", "No reviewed adapter requests.")));
    const jobs = node("div", "results");
    for (const job of data.jobs) {
      const card = append(node("button", "result-card"), node("div", "result-title", `${job.mod_id} · ${job.subsystem}`),
        node("div", "result-id", job.id), append(node("div", "result-foot"), chip(job.status, "teal")));
      card.type = "button";
      card.addEventListener("click", async () => {
        try {
          const packet = await request(`/api/research/jobs/${encodeURIComponent(job.id)}`);
          $("#detail-panel").replaceChildren(append(node("div"),
            append(node("div", "detail-head"), node("div", "eyebrow", "READ-ONLY AGENT JOB"),
              node("h2", "", `${job.mod_id} · ${job.subsystem}`), node("div", "detail-id", job.id)),
            section("Packet", jsonDisclosure("Installed-pack context and source paths", packet))));
        } catch (error) { toast(error.message); }
      });
      jobs.append(card);
    }
    target.append(section(`Prepared jobs · ${count(data.jobs.length)}`,
      data.jobs.length ? jobs : node("p", "detail-subtitle", "Select a mod and prepare jobs to begin source analysis.")));
    if (!data.findings.length && !data.jobs.length) $("#detail-panel").replaceChildren(append(node("div", "detail-placeholder"),
      node("span", "", "◫"), node("h2", "", "Review before import"),
      node("p", "", "Agents supply evidence-backed proposals. Only accepted findings enter the knowledge database.")));
  } catch (error) { toast(error.message); }
}
function analysisMetric(label, value) {
  return append(node("div", "coverage-card"), node("h3", "", label), node("strong", "metric-number", count(value)));
}
function analysisEntry(title, subtitle, value) {
  const button = append(node("button", "result-card"), node("div", "result-title", title), node("div", "result-id", subtitle));
  button.type = "button";
  button.addEventListener("click", () => {
    const panel = $("#detail-panel");
    const head = append(node("div", "detail-head"), node("div", "eyebrow", "ANALYSIS EVIDENCE"), node("h2", "", title), node("p", "detail-subtitle", subtitle));
    const body = append(node("div", "detail-section"), node("h3", "", "Captured facts"), node("pre", "", pretty(value)));
    panel.replaceChildren(head, body);
  });
  return button;
}
function analysisGroup(title, entries, total, describe) {
  const group = append(node("section", "analysis-group"), node("h2", "", `${title} · ${count(total)}`));
  if (describe) group.append(node("p", "", describe));
  if (!entries.length) group.append(node("p", "muted-note", "None found in the supported evidence."));
  else {
    const list = node("div", "results");
    for (const entry of entries) list.append(entry);
    group.append(list);
  }
  if (entries.length < total) group.append(node("p", "muted-note", `Showing the first ${count(entries.length)} records. Use recipe_analysis.py for the complete JSON report.`));
  return group;
}
async function renderAnalysis(renderId) {
  const data = await request("/api/analysis");
  if (renderId !== state.renderRequest) return;
  const target = $("#results"); target.replaceChildren();
  $("#result-count").textContent = `${count(data.counts.recipes)} effective recipes analyzed`;
  $("#page-label").textContent = "";
  $("#detail-panel").replaceChildren(append(node("div", "detail-placeholder"), node("span", "", "◇"),
    node("h2", "", "Conservative findings"), node("p", "", "Select a finding to inspect its recipe IDs and evidence. Custom recipe matching stays inconclusive until an adapter understands its rules.")));
  const metrics = append(node("div", "coverage-grid"),
    analysisMetric("Exact-input analyzable", data.counts.analyzable),
    analysisMetric("Conflict / duplicate pairs", data.counts.findings),
    analysisMetric("Ingredient gaps", data.counts.missing_ingredients),
    analysisMetric("Inconclusive recipes", data.counts.inconclusive));
  target.append(metrics);
  const findings = data.findings.map(finding => analysisEntry(
    finding.kind === "competing_inputs" ? "Competing inputs" : "Equivalent recipes",
    `${finding.context} · ${finding.recipes.join(" ↔ ")}`, finding));
  target.append(analysisGroup("Input collisions", findings, data.counts.findings,
    "Only exact ingredient definitions in supported vanilla contexts are classified. Stonecutter choices with different outputs are expected."));
  const missing = data.missing_ingredients.map(issue => analysisEntry(
    issue.kind.replaceAll("_", " "),
    `${issue.recipe_id} · ${issue.target}`, issue));
  target.append(analysisGroup("Ingredient gaps", missing, data.counts.missing_ingredients,
    "An empty tag can be intentional. Inspect its recipe before treating it as broken."));
  const overrideEntries = data.overrides.map(entry => analysisEntry("Recipe resource override", entry.id, entry));
  target.append(analysisGroup("Resource overrides", overrideEntries, data.counts.overrides,
    data.override_evidence === "captured" ? "Multiple active packs supplied the same recipe ID; the resource stack is shown in load order." :
      "This capture predates resource-stack collection, so overrides cannot be determined from it."));
  const inconclusive = data.inconclusive_types.slice(0, 30).map(entry => analysisEntry(
    entry.type, `${count(entry.count)} recipes need context-specific matching`, entry));
  target.append(analysisGroup("Inconclusive contexts", inconclusive, data.inconclusive_types.length,
    "These recipes remain in the database and in snapshot diffs; their input collisions are not asserted."));
  if (state.comparison) renderComparison(target, state.comparison);
}
function renderComparison(target, comparison) {
  const counts = comparison.counts;
  const heading = append(node("section", "analysis-group comparison-group"), node("h2", "", "Snapshot comparison"),
    node("p", "", `${comparison.baseline.declared_pack_version || "Baseline"} → ${comparison.current.declared_pack_version || "Current"}`));
  heading.append(append(node("div", "coverage-grid"), analysisMetric("Added", counts.added),
    analysisMetric("Removed", counts.removed), analysisMetric("Changed", counts.changed),
    analysisMetric("New conflicts", counts.new_conflicts), analysisMetric("Resolved conflicts", counts.resolved_conflicts)));
  target.append(heading);
  for (const [key, title] of [["new_conflicts", "New conflict groups"], ["resolved_conflicts", "Resolved conflict groups"],
                              ["changed_recipes", "Changed recipes"], ["added_recipes", "Added recipes"],
                              ["removed_recipes", "Removed recipes"]]) {
    const entries = comparison[key].map(value => {
      if (typeof value === "string") return analysisEntry(value, key.replaceAll("_", " "), {recipe_id: value});
      return analysisEntry(value.id || value.recipes.join(" ↔ "),
        value.fields ? value.fields.join(", ") : value.context, value);
    });
    target.append(analysisGroup(title, entries, counts[key.replace("_recipes", "") ] ?? counts[key], ""));
  }
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
  $("#research-prepare").addEventListener("click", async () => {
    if (!state.mod) return toast("Choose a mod first");
    const button = $("#research-prepare"); button.disabled = true;
    try {
      const result = await post("/api/research/prepare", {mod_id: state.mod,
        source_url: $("#research-source-url").value.trim()});
      toast(`${count(result.job_count)} packets saved to ${result.output}`); render();
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; }
  });
  $("#research-import").addEventListener("click", async () => {
    try {
      const result = await post("/api/research/submit", {path: $("#research-findings-path").value.trim()});
      toast(`${count(result.submitted)} findings queued for review`); render();
    } catch (error) { toast(error.message); }
  });
  $("#run-comparison").addEventListener("click", async () => {
    const button = $("#run-comparison"), status = $("#comparison-status");
    button.disabled = true; status.textContent = "Comparing…";
    try {
      let baseline = $("#baseline-path").value.trim();
      const file = $("#baseline-file").files[0];
      if (file) {
        const uploaded = await request("/api/upload-baseline", {method: "POST", headers: {"Content-Type": "application/zip"}, body: file});
        baseline = uploaded.path;
      }
      state.comparison = await post("/api/compare", {baseline});
      status.textContent = `${count(state.comparison.counts.changed)} changed recipes`;
      render();
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
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
