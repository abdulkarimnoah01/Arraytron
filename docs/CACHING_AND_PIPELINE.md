# Caching strategy and pipeline use (v1.17.0)

Arraytron is **procedural and deterministic**: the same settings, scene and Houdini version give bit-identical instances (tested across two separate processes). That makes caching a choice, not a necessity. This page says what is stored where and which cache to use when.

## What is stored on the node

| Data | Where | Notes |
| --- | --- | --- |
| Painted points | the hidden parameter `paint_data` (compressed, at most 20,000 points) | Part of the node: it saves and loads with the hip and travels with a copied node. Ids are kept. |
| Instance overrides | the multiparm `overrides` | Part of the node. Keyed on stable ids. |
| Physics Settle result | a cache file in the *Cache Folder* (default `dist/arraytron_cache`, named by node and a fingerprint of the setup) | Written by **Simulate & Cache**. Everything else in the stack runs on top of the cached positions, so Grow, camera and overrides never re-simulate. A changed setup makes the cache *stale* (the status says so; *Error If Not Simulated* makes it a hard error). |
| Everything else | nothing | Cooked on demand. |

The **Stored On This Node** read-out (Finish tab) summarises these.

## Choosing a cache

1. **Interactive work:** nothing to do. Cooks are quick up to tens of thousands of instances (the production suite measures a 20,000 point cook with variation, mask, field, separation and primvars in a few seconds).
2. **Physics:** always Simulate & Cache before a render farm job; ship the cache folder with the hip (the demos use a path relative to the hip).
3. **Hand-over or farm:** **Export USD** (Export tab) writes the final instances (positions, orientations, scales, ids, prototype indices, hidden ids, primvars and the prototypes) to a self-contained layer. Reference or sublayer it in a downstream stage; the debug guides are not exported. It exports the current frame's data, including time samples that exist (Grow, animated camera culling: export per frame or use a USD ROP over a frame range for animation).
4. **Whole stage:** a regular USD ROP / Karma render ROP on the stage works as for any LOP; the Arraytron output is plain USD.
5. **Shot consistency:** keep the seeds, the scene and the Houdini version fixed, and check the `production_<version>.json` determinism result. The stable ids make downstream FX and overrides survive edits.

## Version and migration

Each release is its own node type (`arraytron::instancer::<version>`), so a scene keeps working with the version it was built with; older HDAs live in `dist/archive/`. To move a scene to a newer version, create the new node and copy the parameters (names and defaults are unchanged between releases; new parameters only add behaviour that is off by default). Every release is tested to reproduce the previous one exactly with the new features off.

## Pipeline notes

* **Prototype sources:** Prim Path, Input Connection, USD File and SOP Geometry are supported. File and SOP prototypes are staged under `<output>_Sources` (hidden).
* **Purposes:** guides (bounds, curve, surface box, grow arrow, debug) are `guide` purpose and never render.
* **Camera:** a Camera LOP before the node (default prim `/cameras/camera1`).
* **Units and up axis:** the node follows the stage; the tools and demos assume Y up.
* **Karma:** use the PointInstancer as is; XPU and CPU both render it natively.
