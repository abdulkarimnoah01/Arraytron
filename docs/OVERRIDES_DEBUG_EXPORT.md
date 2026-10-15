# Overrides, refined Paint, debug views, export and production testing (v1.0.0)

v1.0.0 is the production-polish release of the master plan: stable ids made explicit and tested, manual instance overrides, a refined Paint workflow, a debug system, a caching / export strategy, production tests and documentation. The interface gets one more tab, **Finish**.

## Stable ids

A formal audit (`tests/validate_polish.py`, last group) checks every Distribution Mode (Line, Area, Grid, Circle where applicable, Surface, Cluster, Paint): ids are unique and identical in two builds; rotation, scale, selection weights, selection seed, base scale, the number of prototypes and a Scale mask change neither the ids nor the positions; a Density mask only removes ids. (Earlier suites already prove adding points or clusters never renames the existing ones.)

## Instance overrides

*Generated Instance + Override Database = Final Instance.* The database is the multiparm **Instance Overrides** (Finish tab); one row per instance id with **Delete**, **Move** (offset in point space), **Rotate** (degrees about the instance's own X, then Y, then Z), **Scale** (multiplier) and **Prototype Row** (a Prototype Bank row number). They are applied by the Python SOP `OVERRIDES` after generation, variation, selection, separation, avoidance and physics, just before Grow. Rows are keyed on the stable id: they keep editing the same instance when other settings change, rows whose id or prototype row does not exist are ignored (and counted in the read-out), a deleted instance stays deleted, and removing the rows brings the generated instances back. Python helpers: `override_set(node, id, delete=, move=, rot=, scale=, proto=)`, `override_delete_ids(node, ids)`, `override_clear(node)` (each one undo step).

## Paint: Replace and Relax

The Operation menu gains **Replace** (clear the points under the brush by Strength x falloff, then paint new ones there; new ids) and **Relax** (spread the points under the brush towards an even spacing: Min Spacing, or their own average distance when it is 0; a few iterations; moved points are projected back onto the surface; ids and the points outside the brush are untouched; deterministic). Ctrl still inverts (Remove, or Add when the Operation is Remove).

## Debug views

**Debug Views** (Finish tab) author guide-purpose prims under `<output>/Debug` (viewport only, never rendered, never changes the instances): Generated Points, Rejected Points (generated but gone at the end), Final Points coloured by Prototype / Id / Weight, Axes (up green, forward blue), Collision Radius (the Separation spheres as rings) and Cluster Centres. Debug Size scales them.

## Export and cache

**Export USD** writes the final instancer, self-contained (prototypes included, debug guides left out), with ids, indices, primvars and the up axis. See `docs/CACHING_AND_PIPELINE.md`.

## Production testing

`tests/validate_production.py` measures what a pipeline relies on: a saved scene reloads to the identical result, two separate processes give bit-identical output, a 20,000 point cook with every stage on stays within its time budget, 160 random parameter walks never produce a Python traceback, an exported file passes `usdchecker`, no embedded script contains a dollar sign, the Help / version / icon sections exist, every demo cooks, the manifest hashes match the files and every document is indexed. The measured timings are written to `tests/production_v1.0.0.json`.

## Evidence

`tests/validate_polish.py` (9 groups): the interface and stage order (OVERRIDES between the physics and Grow, debug_guide last), v0.9.0 reproduced with the new features off, override maths against rotation matrices, overrides on the node (delete, move, rotate in the local frame, scale, prototype; untouched instances stay equal; ids stay stable when other settings change), the override functions, Replace and Relax (ids, surface, evenness, determinism) and the Operation menu in the viewer state, every debug view against independent values, the export (arrays, ids, prototypes, primvars, no debug prim, self-contained, overwrite, error) and the stable-id audit. Eight mutations (`ARRAYTRON_MUTATE=ovr_euler|ovr_qorder|ovr_delete|ovr_scale|ovr_proto|relax_push|replace_keep|export_ids`) fail it. All earlier suites pass on v1.0.0.

## Not verified / limits

The look of the Finish tab and the debug guides in the viewport (GUI), and the Paint tool in a real viewport (Replace and Relax run through the stand-in viewport only). Overrides are keyed by id typed or scripted (there is no viewport picking of instances yet). Move is in point space, so a Bounds Transform applies on top. Debug ring radii use the Separation size.
