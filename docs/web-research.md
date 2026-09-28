# GitHub-based web research handoffs

`web_research.py` gives an ordinary web chat enough GDE context to research a
focused gameplay subsystem without SQLite access. The source code remains on
the mod's public GitHub. Exported packets contain captured data and source
routes, never JAR bytes, decompiled files, or database copies.

The task JSON uses `format: ch4os-web-research-task-v1`, `mod_id`, `subsystem`,
`title`, 1–80 selected `item_ids`, and focused `questions`. Optional
`config_fields`, `definition_kinds`, `fluid_ids`, and `recipe_ids` select useful
context. `source` contains a GitHub `repository`, full commit `revision`,
`declared_version`, `match_status` (`release_candidate` or
`exact_installed_version`), a `match_note`, and `routes` with file `path` and
`purpose`. A source version different from the installed mod is rejected at
preparation; a matching version string alone is not promoted into accepted
source evidence.

Use `related_config_fields` to include effective settings owned by another
installed mod, for example `{"create": ["fluidTankCapacity"]}` when researching
Diesel Generators oil barrels. The handoff retains each setting's owning mod,
capture record locator and effective value. Missing requested settings fail
preparation explicitly; the exporter does not substitute upstream defaults or
a same-named primary-mod setting. Tasks without this option retain their
existing packet shape and bytes. Add dependency settings in a new assignment
directory rather than rewriting an already issued handoff.

The [handbook's first task](https://github.com/Cha0sCollective/Ch4oS-Handbook/blob/main/research/assignments/diesel-engines-and-fuels/task.json)
is a concrete example. Source selection and questions are reviewer inputs;
the exporter does not guess the correct release from a moving branch.

```text
python web_research.py --database capture.sqlite --knowledge knowledge.sqlite prepare --task task.json --output jobs/diesel-engines
python web_research.py --database capture.sqlite --knowledge knowledge.sqlite inventory --output handbook-snapshot.json
python web_research.py --database capture.sqlite --knowledge knowledge.sqlite reviewed --mod powergrid --output powergrid-reviewed.json
```

Preparation registers one immutable source-analysis job and writes:

- `prompt.md`: ready-to-copy instructions, pinned GitHub/raw links, output contract.
- `context.json`: selected item properties, effective settings, loaded gameplay
  definitions, resolved fluid memberships, effective recipes, reviewed facts,
  pending findings, item inventory, and all installed mod identities.
- `context.md`: readable record-oriented version of that context.
- `handoff.md`: prompt and context combined into one attachable file.
- `job.json` and `manifest.json`: registered job metadata and file hashes.

Recipe summaries keep effective resource JSON, inputs/outputs, and process
parameters. Duplicate codec representations and expanded ingredient arrays are
omitted. Unknown properties remain null with their captured status. Rejected
recipe resources cannot become active recipe records. Older captures remain
usable with their existing unavailable-data labels.

Identical inputs produce identical bytes and job IDs. Changed capture or
reviewed knowledge produces a new job; differing output cannot overwrite an
issued packet directory. Use a new directory for a refreshed assignment.

The researcher reads the pinned source and returns a practical report plus a
JSON array of `ch4os-research-finding-v1` records. `research_queue.py submit`
imports those proposals as pending. When the source selection is still a
candidate, its evidence retains `match_basis: release_candidate`; acceptance
fails until local source-version review establishes its basis. The handbook
workflow describes normalization after that review. Source reading does not
become runtime confirmation. No live probes are part of these assignments.

Guide validation now supports any mod using `<!-- gde-ref: finding_id -->`
and a single `<!-- gde-snapshot: snapshot_id -->`. Existing Power Grid pilot
references are still recognized. The validator checks accepted records,
evidence, artifact ownership, and snapshot separation. By default it is read
only; `--record-refs` deliberately updates a guide's reference set.
