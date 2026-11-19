# Saved masks (v1.38.0)

A mask that took a noise, a painted brush or an image to make can be saved in the stage and used by every Arraytron node below it, without evaluating it again. The same mask is also written as a named primvar on every instance.

Code: `src/arraytron_maskstage.py` (in the PythonModule), `src/arraytron_mask.py` (`_mask_values_raw` source 6, `sop_mask`), `src/guide_bounds_v1380.py` (authors the grid on the output prim). Test: `tests/validate_maskstage.py` (30 checks).

## Save Mask (Scatter tab > Mask > Save, Cache And Export)

* **Save Mask For Other Arraytron Nodes** (`mstage_on`): saves the **final** mask weight, the number the node's Density and Scale actually used (after Invert, Low / High, Gamma, the curve, Output Range and Edge Fade).
* **Mask Name** (`mstage_name`): the name of the saved mask and of its primvar. Empty: `<node name>_mask`. Letters, digits and underscores; other characters become underscores; a name that is a reserved attribute name (`id`, `P`, ...) gets `_mask` appended.
* **Cache Resolution** (`mstage_res`, 8 - 2048, default 256): cells along the longer side of the grid. The grid covers the Export Area (Automatic: the generated points plus a tenth of margin, or the custom area of the export section).
* **Saved Mask** (`mstage_info`): read only, says what is saved (name, size, area).

Where it lives:

* On the output PointInstancer prim, as customData `arraytron:mask`: `name`, `v`, `node`, `source`, `cx`, `cz`, `sx`, `sz`, `w`, `h` and `data` (base64 of zlib of float16 values; rows run from -Z to +Z, columns from -X to +X). A node with Save Mask off removes it.
* Per instance, as the point attribute and primvar `primvars:<name>` (float, the same value the mask gave that point), listed with the other primvars of the instancer.

The grid is cached by every `mask_*` parameter, the resolution, the name, the seed, the extent and the height, and decoded grids are cached by their hash, so a cook with unchanged settings does not rebuild it. A Mesh Primvar mask and an Upstream Mask are never cached (they follow the surface or the stage).

## Upstream Mask (Mask Source)

* **Mask Source > Upstream Mask** (`mask_source` = 6) reads the saved grids of Arraytron nodes above this one in the stage. Nothing is evaluated again; the values are looked up (bilinear) at each point.
* **Upstream Mask** (`mup_name`, a tick list of the names found above): tick one or several. **Combine** (`mup_combine`): Multiply (inside all), Maximum (inside any), Minimum. **Outside The Saved Area** (`mup_outside`): Black (0) or the Edge value.
* It works down a chain of any length, because each node's output keeps the masks of the nodes above it. Everything after the source is the same as for any mask (Invert, Low / High, Gamma, the curve, Output Range, Edge Fade, Mask Effect).
* A ticked name that is no longer found (the node above changed its name or switched Save Mask off) gives a clear error that names the mask and lists the ones that exist.

## The offer when nodes are wired

When the first input of an Arraytron node changes (or the node is created already wired) and an Arraytron node above saved a mask, a window offers it:

* **Use This Mask** sets the node's Mask Source to Upstream Mask with that name. Several masks above: a tick list.
* **Not Now** closes it. **Don't Ask Again** switches **Offer Masks When Wired** (`mup_ask`) off for this node.
* A mask is offered once per node per session. **Find Upstream Masks** (`mup_find`) offers every mask above again, also the declined ones, and lists them when there is nothing to offer.
* It only appears with a user interface; hython and scripts never open a window.

## Notes

* Saved masks are for Arraytron nodes in one stage. For another renderer or tool, use the primvar.
* The grid is only as fine as Cache Resolution; a sharp painted edge wants 512 or more.
* The previous release is reproduced exactly with Save Mask off and the Mask Source unchanged (tested).
