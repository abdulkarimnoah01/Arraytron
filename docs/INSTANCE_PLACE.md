# Instance Place (v1.9.0)

Distribution Mode **Instance Place** (Layout tab) places instances **one at a time**, like the transforms of a Copy and Transform SOP: a table of individual instances, each with its own **Position**, **Rotate**, **Scale** and **Prototype Row**, filled by hand or by clicking a surface in the viewport. Use it for hero placement, set dressing, a pyramid of crates, an arc of rocks, anything where every instance matters.

## The table (Placed Instances)

| Column | Meaning |
| --- | --- |
| On | Switch the instance off without deleting its row. |
| Id | The stable id (Variation, Mask, Instance Overrides, primvars and Grow key on it). The viewport tool fills it in. A row with no id yet (0) or a repeated id gets a temporary one at cook time; press **Fix Ids** to write the real ones. Removing a row never renames the others. |
| Position | World position. |
| Rotate (deg) | Rotation about X, then Y, then Z (fixed axes), the same convention as the Instance Overrides. Applied before the Look tab rotation. |
| Scale | Scale (x, y, z), multiplied by the Look tab scale and the Prototype Bank scale. |
| Prototype Row | The Prototype Bank row this instance uses (0 lets the Selection Mode choose; a row that is not enabled is ignored). |

The Look tab still applies on top (Randomize is off by default), and so do Mask, Field Stack, Separation, Physics Settle, Instance Overrides, Grow, camera optimisation and the primvars.

## The viewport tool

**Place Instances in Viewport** switches the node to Instance Place and starts the tool (selecting the node never starts it, and never changes a parameter). The prompt line shows the live settings; a green ring and a short line mark the surface point and its normal.

| Input | |
| --- | --- |
| Click | place one instance (one row, one undo step) |
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

## Evidence and limits

`tests/validate_place.py` (8 groups, 5 mutations): the rotation convention against rotation matrices, the Euler round trip, id resolution, the table on the node (ids, positions, rotations, scales, disabled and removed rows, Look tab scale), the Prototype Row per instance, other modes and the previous release unchanged, the tool functions (alignment on a slope, random yaw, nearest, remove, clear, undo), the viewer tool through a stand-in viewport, Instance Overrides and Variation, and the interface. How the tool feels in a real viewport (the click events, the marker) is for the user to judge. Positions are world space, so a Bounds Transform does not move placed instances. The table holds at most 100,000 instances.

Demo: `dist/Arraytron_v1.9.0_place_demo.hip` (render `renders/arraytron_v1.9.0_place_demo_xpu.png`): a pyramid of crates, an arc of rocks growing in size and three single rocks, made by the same functions the tool calls.
