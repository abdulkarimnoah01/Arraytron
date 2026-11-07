# Blast: an overall selection of instances (v1.33.0)

**Scatter tab > BLAST** (after the Falloff). An overall selection that picks many instances at once and either **deletes** them or **transforms them all together**, with an **Invert Selection** option. It is off by default: Blast off is the previous release.

## Where it runs
After the scatter is finished (Mask, Field Stack, Falloff, Variation, prototype assignment, Separation, Physics Settle) and just before the Override Database, so it selects the instances that are really there. Instance ids never change.

## Select By
| Select By | Picks | Settings |
|---|---|---|
| **Id Pattern** | the ids you type: `7`, `10-20`, `0-100:5` (every fifth of 0 to 100), `*` (all), separated by spaces or commas | Ids |
| **Random** | a share of all instances, keyed on the id: the same ones every cook, and adding points never reshuffles the earlier choices | Percent, Seed |
| **Region** | the instances inside a shape, in the space the instances are generated in (before the Bounds Transform) | Region and its controls (below) |
| **Prototype** | the instances of one Prototype Bank row (the same row number as the Override Database) | Prototype Row |
| **Custom (Houdini selection)** | the instances you picked by hand with Houdini's own selection tools | Select In Houdini, Operation, Selected Ids |

**Invert Selection** acts on every instance that is not selected.

## Region shapes
| Region | Controls |
|---|---|
| **Sphere** | Center, Radius |
| **Box** | Center, Size, Rotate (about the vertical axis) |
| **Triangle**, **Hexagon** | Center, Radius (centre to corners), Rotate, Height |
| **Polygon** | the same, with **Sides**: your own number of corners from 3 (a triangle) to 64 |
| **Star** | Center, Radius (outer tips), **Points** (number of tips), **Inner Radius** (how deep it is cut), Rotate, Height |
| **Metaballs** | Center, **Blobs** (number of balls, the first on the centre), Radius (of the balls), **Spread** (how far the others sit from the centre), **Threshold** (lower: a fatter blob that joins more balls), Blob Seed |

Triangle, Hexagon, Polygon and Star are flat shapes in the XZ plane that stand **Height** tall around the Center (the default 100 covers any scatter); the first corner points along +X at Rotate 0, and Rotate turns them in degrees. Metaballs is a real 3D blob: the balls melt into each other where they overlap (the field is the sum of (1 - (d / r)^2)^3 of every ball).

## Select By Custom: select by hand with Houdini's own selection tools
Press **Select In Houdini** (it switches Blast on and Select By to Custom). Like the Houdini Paint mask, the work is done by a native Houdini operation on a helper:

* A helper geometry object appears in the network view (`/obj/<node name>_blast_select`, removed again afterwards) with **one point per instance**, in world space exactly where the instances are (the Bounds Transform included). The points are grey, red where they are picked already. It shows every instance that reaches Blast, also the ones Blast deletes now, so a selection can always be changed.
* Houdini's own **point selection** starts in the viewport: the **Box, Lasso, Brush and Laser** tools of the select toolbar (and its Select Visible / Through options, Shift to add, Ctrl to remove, the Select All and Invert keys ...), exactly as everywhere else in Houdini. Press **Enter** to finish; **Esc** cancels and changes nothing.
* The selected points become instance ids, and the **Operation** menu says how they join the list: **Replace** (the default: the new selection is the list), **Add**, **Remove** or **Toggle**. The ids are stored in **Selected Ids** (`3 7-10 15`): you can edit that by hand, use **Select All** and **Clear Selection**, and copy it to another node. Every selection is one undo step.
* The viewer is put back where it was and Blast acts on the list with your Action and Invert.

## Action
* **Delete**: the selected instances are removed.
* **Transform**: the selected instances are moved, rotated and scaled **all together**, as one group. **Rotate** is in degrees about X, then Y, then Z (fixed axes) and **Scale** is uniform; both work about the **Pivot**: *Selection Center* (the group turns and grows as one body; the spaces between the instances grow with it), *Each Instance* (every instance turns and scales about its own position; only the Move is shared), *World Origin* or *Custom* (Pivot Position). **Move** is applied last. Every instance also turns and scales by the rotation and scale itself, so the group stays a rigid body.

The read-out under the section says how many instances were selected and what was done.

## Tested
`tests/validate_blast.py` (7 groups; the mutations `bl_invert`, `bl_pivot`, `bl_step`, `bl_region` make it fail) and `tests/validate_blastpick.py` (4 groups; the mutations `bp_map`, `bp_world`, `bp_op`, `bp_star` make it fail) in Houdini 22 and 20.5. The first: the pattern, region and transform functions against numpy; Delete and Invert by id; the random share, repeatability and stability when points are added; sphere and inverted box; Prototype; the transform with every pivot against an independent computation from the same scatter with Blast off; Blast off equals the previous release; the place of the section. The second: every Region shape against an independent point-in-shape test (cross products for the convex polygons, a winding number for the star, a summed field for the metaballs, the height, the turned box); Select By Custom: the helper has one point per instance exactly where the USD instance is (with a layout transform), a stand-in for Houdini's selection (box and lasso rules) returns point numbers that come back as the right ids, the Operation menu (Replace, Add, Remove, Toggle), Esc, an empty selection, the picked ones in red, the deleted ones still shown, Delete, Invert and Transform of the picked instances, the real `selectGeometry` call with the Points type and the viewer put back; and the buttons and the parameters. Demo: `tools/build_demo_blast_v1330.py` (`dist/Arraytron_v1.33.0_blast_demo.hip`: a sphere clearing, a random third kept, a group transformed together, every second id, a hexagon, a star, metaballs and a picked group).

## Not verified
The look of the section in the real parameter pane, and the real Houdini selection session (`hou.SceneViewer.selectGeometry` is called as documented and tested with a stand-in; how the toolbar and the prompt read in the viewer is not seen). Houdini's selection works on the instance centres (points), so a Lasso or Brush selects the instances whose centre is inside it.
