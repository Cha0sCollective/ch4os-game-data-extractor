CREATE 6.0.10 HANDBOOK RUNTIME EXPORTER
=======================================

Purpose
-------
This bundle collects a small set of runtime facts from the stock All of
Create - Aeronautics v2.1 modpack. It creates a disposable local dedicated
server. It does not inspect or modify your CurseForge client or Bisect server.

Run it
------
1. Extract the entire downloaded artifact ZIP into a normal folder.
2. Double-click Run-CreateHandbookExport.cmd.
3. Review the Minecraft EULA link shown by the runner.
4. Type I ACCEPT only if you accept the EULA.
5. Wait. The first run downloads and verifies the official v2.1 server pack
   (about 300 MB), and the stock server scripts may install Java 21.
6. When Explorer opens, upload the selected create-6.0.10-sample-*.zip file
   in your ChatGPT conversation.

Expected locations
------------------
- Cached official server pack:
  %LOCALAPPDATA%\CreateHandbookExporter\cache
- Disposable server runs:
  %LOCALAPPDATA%\CreateHandbookExporter\runs
- Clean export ZIPs:
  %USERPROFILE%\Documents\Create-Handbook-Exports

Safety notes
------------
- The official server pack is locked to CurseForge project 1518930, file
  8478465, exact size 314,214,774 bytes, and an exact SHA-256 hash.
- The exporter jar is verified against the checksum included in this bundle.
- The disposable server binds only to 127.0.0.1 on an ephemeral port. Query
  and RCON are disabled.
- Output uses a new timestamped directory and never overwrites an old export.
- Successful disposable server runs are removed. A failed run is retained so
  its local log can be inspected.
- No textures, models, jars, worlds, player data, or credentials are placed
  in the clean output ZIP.

Advanced usage
--------------
The PowerShell script accepts:

  -Scope sample|full
  -ServerPackPath <path to an already-downloaded official server-pack ZIP>
  -OutputRoot <absolute output folder>
  -KeepWorkDirectory
  -ValidateOnly

The default sample scope is the review gate. Do not use full scope until the
sample export has been inspected.
