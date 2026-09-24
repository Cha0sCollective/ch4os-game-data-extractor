PRAGMA foreign_keys = ON;

CREATE TABLE capture (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    format TEXT NOT NULL,
    generated_at_utc TEXT,
    minecraft_version TEXT,
    neoforge_version TEXT,
    declared_pack_version TEXT,
    scope TEXT,
    provenance_json TEXT NOT NULL
);
CREATE TABLE capture_files (
    name TEXT PRIMARY KEY,
    bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL
);
CREATE TABLE mods (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT
);
CREATE TABLE blocks (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    mod_id TEXT REFERENCES mods(id),
    item_id TEXT,
    description_id TEXT,
    implementation_class TEXT,
    has_block_entity INTEGER NOT NULL
);
CREATE TABLE block_properties (
    block_id TEXT NOT NULL REFERENCES blocks(id),
    name TEXT NOT NULL,
    allowed_values_json TEXT NOT NULL,
    PRIMARY KEY (block_id, name)
);
CREATE TABLE block_entity_types (
    block_id TEXT NOT NULL REFERENCES blocks(id),
    type_id TEXT NOT NULL,
    PRIMARY KEY (block_id, type_id)
);
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    mod_id TEXT REFERENCES mods(id),
    display_name TEXT,
    description_id TEXT,
    implementation_class TEXT,
    max_stack_size INTEGER,
    damageable INTEGER,
    max_damage INTEGER,
    rarity TEXT,
    block_id TEXT,
    detail_status TEXT NOT NULL,
    component_status TEXT NOT NULL,
    block_entity_type_status TEXT NOT NULL
);
CREATE TABLE item_components (
    item_id TEXT NOT NULL REFERENCES items(id),
    component_id TEXT NOT NULL,
    status TEXT NOT NULL,
    value_json TEXT,
    error TEXT,
    PRIMARY KEY (item_id, component_id)
);
CREATE TABLE item_tags (
    tag TEXT NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(id),
    PRIMARY KEY (tag, item_id)
);
CREATE INDEX item_tags_by_item ON item_tags(item_id, tag);
CREATE TABLE block_tags (
    tag TEXT NOT NULL,
    block_id TEXT NOT NULL REFERENCES blocks(id),
    PRIMARY KEY (tag, block_id)
);
CREATE INDEX block_tags_by_block ON block_tags(block_id, tag);
CREATE TABLE registry_entries (
    registry_id TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    namespace TEXT,
    implementation_class TEXT,
    access_sources_json TEXT,
    PRIMARY KEY (registry_id, entry_id)
);
CREATE INDEX registry_entries_by_entry ON registry_entries(entry_id);
CREATE TABLE registry_tags (
    registry_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    member TEXT NOT NULL,
    PRIMARY KEY (registry_id, tag, member)
);
CREATE TABLE recipes (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    type TEXT,
    serializer TEXT,
    implementation_class TEXT,
    result_item_id TEXT,
    result_count REAL,
    source_pack_id TEXT,
    source_resource_id TEXT,
    source_sha256 TEXT,
    detail_status TEXT NOT NULL,
    input_status TEXT NOT NULL,
    output_status TEXT NOT NULL,
    semantic_status TEXT NOT NULL,
    detail_json TEXT
);
CREATE INDEX recipes_by_type ON recipes(type);
CREATE TABLE recipe_terms (
    id INTEGER PRIMARY KEY,
    recipe_id TEXT NOT NULL REFERENCES recipes(id),
    role TEXT NOT NULL,
    sequence_step INTEGER,
    path TEXT,
    kind TEXT NOT NULL,
    target_id TEXT,
    quantity REAL,
    chance REAL,
    definition_json TEXT,
    origin TEXT
);
CREATE INDEX recipe_terms_by_target ON recipe_terms(kind, target_id, role);
CREATE INDEX recipe_terms_by_recipe ON recipe_terms(recipe_id, role);
CREATE TABLE properties (
    id INTEGER PRIMARY KEY,
    entity_kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    property_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN
        ('captured_directly', 'derived', 'unavailable', 'unsupported', 'not_applicable', 'failed_to_collect')),
    value_json TEXT,
    unit TEXT,
    conditions_json TEXT,
    source TEXT,
    source_record_json TEXT
);
CREATE INDEX properties_by_entity ON properties(entity_kind, entity_id, property_key);
CREATE TABLE config_values (
    id INTEGER PRIMARY KEY,
    mod_id TEXT,
    config_scope TEXT,
    config_path TEXT,
    field_name TEXT,
    effective_value_json TEXT,
    unit_hint TEXT,
    evidence_status TEXT,
    source_api TEXT
);
CREATE TABLE unloaded_recipe_resources (
    id TEXT PRIMARY KEY,
    source_pack_id TEXT,
    source_sha256 TEXT,
    reason_status TEXT,
    source_json TEXT
);
CREATE TABLE recipe_overrides (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    effective_loaded INTEGER NOT NULL,
    layers_json TEXT NOT NULL
);
