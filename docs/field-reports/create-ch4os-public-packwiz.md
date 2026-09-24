# Packwiz ZIP to disposable server capture

The public Create: Ch4oS Prism import ZIP was used to test the new capture
command end to end. The ZIP SHA-256 was
`e455515294ba1f27a5ea688344045bad520cee668d1a2b0c90b84e446001d14c`.
The command read its Packwiz link, installed the pack with Packwiz's `server`
side selection, installed NeoForge 21.1.248 for Minecraft 1.21.1, and ran the
exporter in a disposable loopback-only server. No executable from the ZIP was
launched. The user-supplied ZIP and all generated files stayed outside this
repository.

The server completed the exporter and shut down successfully. All 19
manifest-listed evidence files passed byte-count and SHA-256 checks. The
local capture ZIP SHA-256 is
`7d209f45012d4e7f0ec2e2e91537f331c29f310aa8abfcefbc39c4e52b592803`;
its manifest SHA-256 is
`e4584b266c3cd22ca9e82b27a96b82bc23c254d93d8bce5152321618cf4681b2`.

| Record | Count |
| --- | ---: |
| Loaded mods | 279 |
| Items | 10,980 |
| Blocks | 9,124 |
| Effective loaded recipe headers | 17,725 |
| Registry identities | 32,934 |
| Installed artifacts | 213 |
| Artifact diagnostics | 0 |

Create stress and server/common configuration introspection reported `ok`.
The server logged 39 recipe parsing errors in the pack's resources. Those
rejected definitions are not among the 17,725 effective loaded recipes; the
current exporter collects loaded recipes only. Capturing rejected recipe
diagnostics is a later improvement. The counts describe this public Packwiz
snapshot, which differs from the owner's earlier R0 server archive.

A second end-to-end run used a minimal bundled Packwiz ZIP with no Create mod.
The same command served its `pack.toml` and `index.toml` on loopback, installed
NeoForge, and completed a verified 19-file export with 1,333 items and 1,290
effective recipe headers. Create introspection correctly reported
`not_applicable`. This confirms that Create is optional for the pack-wide
inventory. The fixture ZIP SHA-256 was
`124bbf831efe405897a3a7351e20e2a41182f733df0f86f96cbb075575edb907`;
the resulting capture ZIP SHA-256 was
`4204818bbfea9c259f86956f1d3ff9ce5fcd0d99a3715f4a89690a2f8b282cea`.
