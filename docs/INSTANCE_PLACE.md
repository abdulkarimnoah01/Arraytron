# Instance Place (v1.9.0)

Distribution Mode **Instance Place** (Layout tab) places instances **one at a time**, like the transforms of a Copy and Transform SOP: a table of individual instances, each with its own **Position**, **Rotate**, **Scale** and **Prototype Row**, filled by hand or by clicking a surface in the viewport. Use it for hero placement, set dressing, a pyramid of crates, an arc of rocks, anything where every instance matters.

## The table (Placed Instances)

| Column | Meaning |
| --- | --- |
| On | Switch the instance off without deleting its row. |
| Id | The stable id (Variation, Mask, Instance Overrides, primvars and Grow key on it). The viewport tool fills it in. A row with no id yet (0) or a repeated id gets a temporary one at cook time; press **Fix Ids** to write the real ones. Removing a row never renames the others. |
| Position | World position. |
| Rotate (deg) | Rotation about X, then Y, then Z (fixed axes), the same convention as the Instance Overrides. Applied before the Variation tab rotation. |
| Scale | Scale (x, y, z), multiplied by the Variation tab scale and the Prototype Bank scale. |
| Prototype Row | The Prototype Bank row this instance uses (0 lets the Selection Mode choose; a row that is not enabled is ignored). |

The Variation tab still applies on top (Randomize is off by default), and so do Mask, Field Stack, Separation, Physics Settle, Instance Overrides, Grow, camera optimisation and the primvars.

## The viewport tool

**Place Instances in Viewport** switches the node to Instance Place and starts the tool (selecting the node never starts it, and never changes a parameter). The prompt line shows the live settings; a green ring and a short line mark the surface point and its normal.

| Input | |
| --- | --- |
| Click, or press-drag-release | place one instance (one row, one undo step); the drag turns and scales it |
| Ctrl + click | delete the placed instance under the mouse |
| Wheel + Shift | New Scale |
| Wheel + Ctrl | New Rotation (15 degree steps) |
| `[` `]` | New Scale smaller / larger |
| `,` `.` | New Rotation -15 / +15 degrees |
| `0` to `9` | New Prototype Row (0 = Selection Mode) |
| `H` | hide / show the help line |
| Alt, middle mouse | camera navigation, as always |
| Esc, Enter | finish |

Settings of the tool: **Place On** (a Mesh, a basic shape or a hierarchy of the Scene Stream; empty = the ground plane Y = 0), **Align To Surface** (0 upright, 1 the up axis onto the surface normal), **Offset** along the normal, **New Scale**, **New Rotation**, **Random Rotation** (+/- degrees about the up axis, seeded by **Rotation Seed**) and **New Prototype Row**. A click can arrive as two viewer events; the tool places once.

## Tool extras (v1.11.0)

* **Press, drag, release.** With **Drag Sets Rotation And Scale** on (the default) the press only records the point: drag sideways to turn the new instance (half a degree per pixel) and up or down to scale it (up doubles its size every 150 pixels), release to place it. The prompt shows the drag and the marker shows the heading (+Z) of the new instance. A plain click places it on release; with the toggle off the press places at once.
* **Snap Position** puts new instances on a grid of that size (X and Z; the point is put back on the surface, so it also works on a slope). **Snap Rotation (deg)** rounds the rotation about the up axis to a multiple of that many degrees (15 gives 0, 15, 30 ...), also for the drag. 0 turns either off.
* **Place Along Curve:** pick a BasisCurves prim in **Along Curve Prim**, choose **Count** (ends included) or **Spacing**, and press **Place Along Curve**: one instance per curve sample is appended to the table (one undo step). **Follow Curve** turns every instance so that +Z points along the curve (New Rotation is added); **Project On Surface** drops them onto the Place On surface and aligns them with Align To Surface. Scale and Prototype Row come from the New settings; ids continue after the last row.
* The node is now called `arraytron1` when you create it (it was `instancer1`), and the Physics Settle switch on the Physics tab reads **Settle Instances**.

## Arrays (v1.10.0): Copies, like the Copy and Transform SOP

Any row can make an **array**: set **Copies** above 1 and the steps appear. Copy 0 is the row itself; every next copy is the previous one moved by one more step.

| Column | Meaning |
| --- | --- |
| Copies | How many copies (1 = a single instance, at most 9,999 per row). |
| Step Translate | How far each copy moves from the one before (X, Y, Z). |
| Step Rotate (deg) | How much each copy turns from the one before (degrees about X, then Y, then Z). |
| Step Scale | Each copy is this many times the size of the one before (1 keeps the size, 0.9 shrinks every copy by ten percent). |
| Step Space | **Local (follows the copy)**: every step is applied in the frame of the previous copy, M(k+1) = M(k) * Step, like the Copy and Transform SOP, so a rotation makes spirals and fans and the translation turns and shrinks with the copy. **World**: the translation is along the world axes and the rotation turns the copy about its own position in world axes (straight rows, stairs, grids of steps). |

Examples: a row of fence posts = Copies 10, Step Translate (2, 0, 0); a square = Copies 4, Step Translate (1, 0, 0), Step Rotate (0, 90, 0), Local; a spiral staircase = Copies 24, Step Translate (0.5, 0.2, 0), Step Rotate (0, 15, 0), Local; a shrinking spiral = Local with Step Scale 0.93. A non-uniform base Scale stays in the instance's own axes (no shear), and the Variation tab and the Prototype Bank scales multiply every copy.

**Ids.** Copy 0 keeps the row Id, so a row without copies is exactly what it was. Copy k of a row gets `1000000000 + Id * 10000 + k`: unique, and stable when other rows are added or removed. A row that makes copies needs an Id below 100000 (the cook says so otherwise). A copy is an ordinary instance for Instance Overrides, Pick Instance, Mask and the rest; in the viewport tool a Ctrl-click on a copy deletes its whole row. The **On** switch, the Prototype Row and the viewport settings (**New Copies**, **New Step Translate / Rotate / Scale / Space**: every click of the tool then places an array) work on the row.

## Evidence and limits

`tests/validate_place.py` (14 groups, 13 mutations; the arrays are checked against 4x4 matrix products, spirals and rows on the node and the copy ids; snap, drag, along-curve samples and the node name on the real node and the stand-in viewport): the rotation convention against rotation matrices, the Euler round trip, id resolution, the table on the node (ids, positions, rotations, scales, disabled and removed rows, Variation tab scale), the Prototype Row per instance, other modes and the previous release unchanged, the tool functions (alignment on a slope, random yaw, nearest, remove, clear, undo), the viewer tool through a stand-in viewport, Instance Overrides and Variation, and the interface. How the tool feels in a real viewport (the click events, the marker) is for the user to judge. Positions are world space, so a Bounds Transform does not move placed instances. The table holds at most 100,000 instances.

Demo: `dist/Arraytron_v1.9.0_place_demo.hip` (render `renders/arraytron_v1.9.0_place_demo_xpu.png`): a pyramid of crates, an arc of rocks growing in size and three single rocks and two arrays (a spiral of 14 rocks and a fence of 5 crates) and a path of stepping stones made with Place Along Curve, made by the same functions the tool calls.
