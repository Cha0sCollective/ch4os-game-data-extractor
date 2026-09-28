# Reviewed research in GDE

For ordinary web chats, use the [GitHub-based handoff exporter](web-research.md).
It selects one gameplay assignment and supplies readable effective pack context,
including reviewed knowledge. The original class-route queue below remains
available for local source-analysis work.

GDE keeps the imported capture database reproducible from its ZIP. The separate
`knowledge.sqlite` in the local app's data directory holds reviewed facts by
capture snapshot. Snapshot IDs hash the authenticated capture evidence and
loaded mod list. Importing the same capture again reuses the snapshot; another
capture gets a new snapshot and pending revalidation for previously researched
mods. Findings are never copied forward automatically.

In the viewer, choose **Research**, select a mod, and prepare jobs. A packet
directory contains `manifest.json`, one shared `context.json`, and small
read-only source-route packets. It includes installed artifact SHA-256 values,
mod version, items, blocks, effective recipes, current GDE facts and relation
leads, and class paths. It does not contain source bodies or JAR bytes. A
public source URL is a candidate, not proof of an exact installed-version
match. Assign packets to low-cost research agents or run them manually. The
agents must inspect the installed-version implementation and return findings;
they must not edit the capture, knowledge store, or handbook.

The CLI provides the same queue without the viewer:

```text
python research_queue.py --database capture.sqlite --knowledge knowledge.sqlite prepare --mod powergrid --source-url https://github.com/patryk3211/PowerGrid --output jobs/powergrid
python research_queue.py --database capture.sqlite --knowledge knowledge.sqlite submit findings.jsonl
python research_queue.py --database capture.sqlite --knowledge knowledge.sqlite list --mod powergrid
python research_queue.py --database capture.sqlite --knowledge knowledge.sqlite review powergrid:battery_capacity --decision accept
python research_queue.py --database capture.sqlite --knowledge knowledge.sqlite tasks --mod powergrid
python research_queue.py --database capture.sqlite --knowledge knowledge.sqlite resolve-task powergrid:battery_adapter --resolution "capture/stage29-powergrid.zip: battery specifications verified"
```

To view findings reviewed through the CLI in the browser, open the same
knowledge database explicitly:

```text
python local_app.py --database capture.sqlite --knowledge knowledge.sqlite
```

Jobs are grouped by device family (for example, `electricity-battery` and
`compat-cc`) and remain immutable. Changing the source candidate or capture
context creates new job IDs; it cannot rewrite an already reviewed packet.

Each JSONL finding uses `format: ch4os-research-finding-v1`, the exact
`snapshot_id` and `job_id` from its packet, a stable `finding_id`,
`record_type`, `subject_kind`, and `subject_id`. Supported record types are
`claim`, `relation`, `formula`, `coverage`, `gap`, and `adapter_request`.
Claims add `predicate`, `value`, optional `unit`, and `conditions`.
Relations add `predicate`, `object_kind`, `object_id`, and `conditions`.
Formulas add `result_predicate`, a structured `expression`, `unit`, and
`conditions`. Coverage adds `area`, `status` (`verified`, `not_applicable`, or
`unresolved`), and `explanation`. Gaps and adapter requests add `description`.

Consequential facts require typed `evidence` with `kind` and `locator`.
`installed_runtime` locators begin with `capture/`. `exact_source` requires
the installed artifact SHA-256, source revision, and
`match_basis: exact_installed_version`; the reviewer must check the matching
basis before acceptance. `installed_artifact` requires a matching artifact
hash. A `test` locator points to a retained test result. Accepted facts show
their evidence status on item pages. Source-derived facts are visibly
different from runtime-confirmed facts. Unknown values are gaps or unresolved
coverage, never a fabricated zero.

Acceptance is a deliberate review action in the viewer or CLI. A finding with
an absent item, block, recipe, or artifact is rejected by the importer. A
rejected recipe resource cannot become an active recipe reference because only
accepted loaded recipe IDs exist in the capture database. Accepted adapter
requests remain visible in the reviewed queue until an extractor change and
fresh capture address them.
Coverage decisions are replaceable within a snapshot: a reviewed `verified`
finding can close an earlier `unresolved` area, and the transition is retained
in `coverage_history`. A later capture starts a different snapshot and requires
fresh review. Accepted `adapter_request` findings create open adapter tasks.
Resolve a task only after recording the capture or test that demonstrates the
new adapter behavior; the task history stays in the knowledge database.

An accepted research gap can be answered through
`KnowledgeStore.resolve_gap(snapshot_id, finding_id, record_ids, note)`.
The references must be accepted claims, formulas or relationships with reviewed
evidence in that same snapshot. The immutable resolution is returned alongside
the gap by `list_findings`; its original proposal and review history remain
intact. A new capture does not inherit the resolution. Answering a source
question does not close an adapter task for data GDE still needs to collect.

## Offline platform and nested artifact review

Older captures can omit platform artifacts and jar-in-jar implementation mods.
`artifact_lineage.py` supplies a reviewed association without rewriting the
capture or pretending the outer bundle declares its children:

```text
python artifact_lineage.py --database capture.sqlite --knowledge knowledge.sqlite --artifact server/mods/bundle.jar --kind nested --note "Nested descriptors and hashes inspected"
python artifact_lineage.py --database capture.sqlite --knowledge knowledge.sqlite --artifact server/libraries/server.jar --kind platform --note "Minecraft version and bundle member inspected"
```

Nested child hashes must descend from a captured outer hash and their descriptor
versions must match the loaded mods. Minecraft platform associations compare
the offline server bundle's version with captured platform metadata and retain
the inner server hash. They establish a reviewed version association; they do
not claim that the capture recorded that binary hash. Associations are immutable,
snapshot scoped, and kept separately from `snapshot_artifacts`. A later capture
does not inherit them. Source selection still needs its own review.

Cross-mod evidence can name `evidence.mod_id` to identify the implementing mod.
Acceptance and guide validation check the hash against that owner; the research
job's mod remains the fallback for older records. This permits an Aeronautics
finding backed by Sable source, or a Minecraft explanation backed by an installed
addon. Preserve the original candidate and use a new reviewed ID when changing
its evidence owner or matching basis. Release-version metadata, relevant source
and offline artifact inspection can establish the installed-version source basis;
an embedded build commit or reproduced binary build is not a universal requirement.
Effective addon activation and pack configuration remain separate questions.
