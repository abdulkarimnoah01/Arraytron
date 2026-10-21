# Arraytron documentation index (v1.22.0)

Start with the **User guide**. Everything is plain Markdown in `docs/`; the project status is the top section of `STATUS.md`, the user-facing overview is `README.md`, and the working rules for developers are in `CLAUDE.md`.

## For artists

* `USER_GUIDE.md` - a two-minute quick start, the nine tabs, recipes.
* `PHYSICS_FOR_ARTISTS.md` - Physics Settle explained simply (the railway ballast and the box demos).
* `TROUBLESHOOTING.md` - the common errors and what to do.
* `CACHING_AND_PIPELINE.md` - what is stored where, which cache to use, export, version migration.

## Features (reference)

* `PHYSICS_SETTLE.md` - Bullet rigid-body settle of a distribution, cache, quality, numbers.
* `CURVE_SURFACE.md` - Curve and Surface Scatter.
* `MASKS_AND_OVERLAP.md` - Mask (noise, image, mesh primvar) and the original No Overlap (v0.5.x).
* `INTERFACE_AND_GROW.md` - the tab interface and the Grow animation.
* `PAINT_BRUSH.md` - the viewport brush and the clearer input sockets.
* `FIELD_STACK.md` - Height, Slope, Noise, Image, Distance and Exclusion fields and how they combine.
* `CLUSTER_AND_SEPARATION.md` - Cluster mode, Separation priority, Avoid Geometry.
* `CAMERA_LOD_PRIMVARS.md` - camera optimisation, LOD / proxies, extended primvars.
* `IMPORTED_POINTS.md` - scatter on FX simulation points and any imported points (SOP or USD), percentages, scale, rotation, ids for AOVs (v1.5.0).
* `PORT_HOUDINI_205.md` - the Houdini 20.5 / 21 build (v1.1.0): how it works, differences, gotchas, evidence, commands (probes in `tools/probes/`).
* `OVERRIDES_DEBUG_EXPORT.md` - stable ids, instance overrides, Replace / Relax painting, debug views, export, production tests (v1.0.0).

## Project files in the root

* `CLAUDE.md` (rules and commands), `HANDOFF.md` (continue on another PC or with another Claude), `STATUS.md` (current state), `README.md`, `INSTALL.md` (installer and shipping), `CHANGELOG.md`, `Arraytron_Master_Solaris_Instancer_Prompt.md` (the master plan), `handoff/` (copy of the Claude memory and the user's global rules), `installer/` (the installer sources).

## Project records

* `VERSIONING.md` - the version scheme and the list of releases.
* `ROADMAP.md`, `MASTER_PLAN_MAP.md` - where each part of the master plan stands.
* `DECISIONS.md` - one line per non-obvious engineering decision or finding.

## History (earlier multi-agent runs, kept for reference)

* `CODER_RETRY.md`, `CONTROLS_COVERAGE.md`, `CONTROLS_FINAL_REVIEW.md`, `FINAL_REVIEW.md`, `INITIAL_TEAM_TASK.md`, `RESEARCH_RECHECK.md`, `RESEARCH_TASK.md` - artifacts of the first team runs (v0.1 to v0.3). The files `*_AUDIT.md` and `TEAM_*.md` are of the same kind.

## Tests and tools (developers)

`tests/validate_*.py` (one suite per feature, plus `validate_production.py`) and `tools/` (builders, demo builders, `render_demo.py`, `archive_release.py`, `make_manifest.py`); the commands are listed in `CLAUDE.md`.
- [Instance Place](INSTANCE_PLACE.md): placing instances one at a time (table and viewport tool).
- [Falloff](FALLOFF.md): scale and density fading towards the edge of any scatter.
- [Rows](ROWS.md): the Line, Circle and Curve modes in several rows, optionally random.
- [Noise and display](NOISE_AND_DISPLAY.md): position noise for every mode, the Points Only display, the cycling Stagger.
- [Biome](BIOME.md): rule based scatter by elevation, slope, moisture and temperature.
- [Mode Palette](MODE_PALETTE.md): the Distribution Mode as a row of icon cells in the Parameters pane.
- [Asset Library](ASSET_LIBRARY.md): a local catalogue of USD assets with your own categories, into the Prototype Bank.
