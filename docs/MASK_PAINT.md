# Painting the mask (v1.26.0 to v1.28.0)

Arraytron has two ways to paint the Mask by hand. Both write a 0 to 1 map over X and Z that the scatter reads like any other Mask Source, so **Invert, Low / High, Gamma, the Remap Curve and the Output Range** (Variation tab > Mask) shape it, and Mask Effect (Density, Scale) decides what it does to the points. Where the mask is high the scatter is dense, where it is low it is empty.

| | Mask Source **Painted** (v1.26.0, v1.27.0) | Mask Source **Houdini Paint** (v1.28.0) |
| --- | --- | --- |
| Brush | Arraytron's own viewport brush | Houdini's Attribute Paint SOP with its heat map |
| Updates | live, about ten times a second while you drag (the Smooth / Multiply / Maximum / Minimum operations are applied when you release the mouse) | not realtime: nothing scatters while you paint, **Finish And Scatter** does it |
| Button | Paint Mask | Paint Mask With Houdini Brush, Finish And Scatter |

## The live brush (Painted)

Press **Paint Mask**, drag on the surface. The brush paints on the Surface Prim, the Paint Target or the Biome terrain of the Distribution Mode, on the **Paint Surface** you name, or on a ground plane at Y 0. Esc or Enter finishes; one drag is one undo step.

* **Brush Operation** (menu, keys 1 to 8): Paint (towards the Foreground value), Erase, Add, Subtract, Smooth, Multiply, Maximum, Minimum, Paint Background (towards the Background value), Sample Foreground and Sample Background (read the mask under the brush into the value instead of painting). **Shift Operation** (default Smooth) and **Ctrl Operation** (default Opposite: Paint becomes Erase, Add becomes Subtract) have their own menus.
* **Brush Radius**, **Strength** (a weak brush builds up like an airbrush), **Feather** (0 hard disc, 1 soft from the middle) with a **Feather Curve** (Linear, Smooth, Gaussian). The white inner ring in the viewport is the hard core.
* **Foreground Value** and **Background Value**; X swaps them. **Symmetry X / Z** about a Symmetry Center repeats every dab mirrored. **Fill Mask** forgets the paint and makes the mask the Foreground everywhere.
* **Unpainted Value** (0: empty until painted; 1: full until you erase), **Map Feather** (blurs the whole map, in scene units), **Map Resolution**, **Live Update**, **Show Mask While Painting** (turns Mask > Visualize on while the brush is active).
* Shortcuts: LMB paint, Ctrl+LMB and Shift+LMB the Ctrl and Shift operations, Ctrl+Shift+LMB drag resizes, wheel with Shift / Ctrl / Ctrl+Shift = radius / strength / feather, `[` `]` radius, `-` `=` strength, `,` `.` feather, `9` `0` foreground, `X` swap, `F` curve, `H` help, Esc / Enter finish. The prompt line shows the mask value under the brush.

The paint is stored as stamps in the hidden parameter `mask_paint_data` (JSON) and turned into a grid at cook time (`src/arraytron_maskpaint.py`). It lives in the space the points are generated in, like the Image mask: a Bounds Transform moves the scatter, not the paint.

## The remap (every Mask Source)

After Invert and Low / High: **Gamma** (above 1 lifts the middle values), **Use Remap Curve** with the **Remap Curve** ramp (horizontal = weight in, vertical = weight out), **Output Range** (squeeze or flip the final weight). At their defaults they change nothing.

## Houdini's own brush (Houdini Paint)

**Paint Mask With Houdini Brush** builds a helper geometry object in `/obj` named `<node>_mask_paint`: the scattering surface as a dense mesh with a float point attribute `mask`, an Attribute Paint SOP and OUT, and enters Houdini's Attribute Paint viewport state. Paint with everything that brush has. **Finish And Scatter** reads the painted attribute back into a compressed map (`mask_hpaint_data`), leaves the brush and shows the node again; the scatter follows. **Clear Houdini Paint** forgets the map and deletes the helper. The next press of the first button continues the same strokes. **Paint Detail** sets the number of points along the longer side of the surface (cap about 200000 triangles); **Plane Size** is the flat square used when the mode has no surface.

## What is not verified

Everything above is tested in hython with a stand-in viewport (the Attribute Paint strokes are replaced by a wrangle after the Attribute Paint SOP). Not verified at a real interface (GUI): the feel of the live brush, that one stroke is one undo step, that the button enters Attribute Paint on the helper and that Finish And Scatter returns the viewer to the node. Not done: tablet pressure, Attribute Paint's shape / Connected Only / Visible Only options, the middle mouse operations (the middle button navigates).
