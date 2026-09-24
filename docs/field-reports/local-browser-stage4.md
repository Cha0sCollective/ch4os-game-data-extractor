# Local browser stage validation

The loopback-only browser was tested against the public-pack SQLite database
from the item database stage. It reported 279 loaded mods, 10,980 items, and
17,725 effective recipes. The mod directory showed 94 mods with loaded items
by default and exposed the remaining loaded mods through its checkbox. In the
browser, selecting Aeronautics Claims opened its one item; the context control
then showed its one recipe. Item and recipe detail pages, a focused recipe
search, collection coverage, and the capture/import dialog were visually
inspected. The narrow layout was checked and the browser viewport reset.

The browser imported the 22-file minimal capture by local path and switched to
its 1,333-item database, then reopened the 10,980-item public-pack database.
Automated API tests cover mod directory queries, item and recipe searches,
tag-aware item uses, recipe detail, coverage, filtered CSV export, import, and
the capture-job handoff to the existing Packwiz runner. The handoff test uses a
stub process that supplies a real test capture ZIP; it does not claim a second
live Packwiz installation from the browser. The Packwiz runner and disposable
server were exercised end to end in earlier stages. The app rejects starting a
capture without explicit EULA acceptance.

The UI reads SQLite through read-only connections and binds to `127.0.0.1`.
Its capture and import jobs save new files under the selected app data
directory. Neither the handbook repository nor existing capture ZIPs were
modified.
