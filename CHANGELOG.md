# Arraytron changelog

Newest first. Versions are plain `vMAJOR.MINOR.PATCH`; every release is its own node type `arraytron::instancer::<version>`. Each release reproduces the previous one exactly with its new features off (tested). Details: `docs/VERSIONING.md`, `STATUS.md`, `docs/DECISIONS.md`.

## v1.34.0 - Mirror

* **A new Mirror tab (after Variation)** mirrors the finished scatter: every distribution mode, with the Mask, Field Stack, Falloff, variation, Separation, Physics, Blast and the Override Database done first, and before Grow (so Grow reveals the mirrored half too).
* **A list of mirror operations** (the multiparm Mirror Operations) works one after the other on everything the operations above made: one plane doubles the instances, two give 4, three give 8, five give 32. Types: **Plane X / Y / Z**, **Custom Plane** (any normal) and **Radial** (Count copies turned about the X, Y, Z or a custom axis, an Angle Span for a fan, **Mirror Each Slice** for a kaleidoscope with a Mirror Plane Angle). The **Center** is the point the plane or the axis goes through.
* **Mirror The Instances Too** (on: a true mirror image, a negative scale and a half turn; off: only the placement is mirrored and every instance keeps its handedness), **Keep Original** (off: the scatter is replaced by its mirror image, a flip), **Max Instances** (a safety limit).
* **Ids:** the originals keep theirs; a copy has `id + 2^20 * copy number` (more when a scatter has over a million ids), the same on every cook.
* Everything else is unchanged and Mirror is off by default. Houdini 22 and 20.5 / 21. `tests/validate_mirror.py` (8 groups, 7 mutations), demo `Arraytron_v1.34.0_mirror_demo.hip`, `docs/MIRROR.md`.

## v1.33.0 - The Field Stack reworked (Height, Distance, Exclusion, Mask) and Blast

* **The Field menu offers only Height, Distance, Exclusion and Mask.** Slope, Noise and Image are no longer offered (scenes that already use them keep working).
* **The Mask field** follows the shape of the node's Mask (any Mask Source, the painted and Houdini-painted masks included): **Keep Off The Mask** (the mask is a hole in the scatter, with a Margin around it), **Scatter On The Mask**, or **Scatter Around The Mask** (a ring of instances a Gap off the edge, Ring Width wide, never on the mask). Margin, Softness and Edge Level; with no Margin and no Softness the mask weight itself is used, soft where the mask is soft.
* **Mask Effect: None (shape only)**: the Mask only gives its shape, so a Field Stack Mask field (or the Falloff) can use it without the mask also removing points.
* **Blast** (Scatter tab, after the Falloff): an overall selection of instances with Invert Selection, that is deleted or moved, rotated and scaled all together about a pivot. Select By Id Pattern, Random, Prototype, **Region** (Sphere, Box, Triangle, Hexagon, Polygon with your own number of Sides, Star, Metaballs, each with its controls) or **Custom: select with Houdini's own selection tools** (Select In Houdini: a helper geometry with one point per instance and Houdini's point selection, Box, Lasso, Brush and Laser; Enter to finish) with an Operation menu (Replace, Add, Remove, Toggle). Off by default. `docs/BLAST.md`.
* Everything else is unchanged. Houdini 22 and 20.5 / 21. `tests/validate_fieldmask.py`, `tests/validate_blast.py`, demos `Arraytron_v1.33.0_fieldmask_demo.hip`, `Arraytron_v1.33.0_blast_demo.hip`. GUI: unverified.

## v1.32.0 - Falloff from the shape of any mask, mask export, the Scatter tab

* **Falloff follows any mask shape and boundary** (Shape: Mask Shape): a fade from the EDGE of the Mask, Inside, Outside or Both sides, with a **Fade Depth** (Whole shape: the scale and density grade smoothly from the deepest point of every piece of the shape to its edge; Fixed width: only the Fade Width next to the edge), a Fade Width and a Mask Level, and **Keep Points Beyond The Fade** (off: the points beyond the fade are removed, so Edge Density 100 keeps every point inside and only the scale falls, with no dust all over the layout). It works with every Mask Source, also the real-time painted mask and the Houdini paint (and noise, image, mesh primvar). Radial and Box are unchanged. `docs/MASK_SHAPE_AND_EXPORT.md`.
* **Edge Fade for any mask** (also the painted mask and the Houdini paint): re-fade the edge with a Fade Width, Grow / Shrink, Fade Curve and Fade Level of your own, whatever softness it was painted with; plus a **Scale Response Curve** so the scale can follow the mask differently from the density. With Mask Effect Density + Scale and Min Scale 0 the density and the scale ARE the mask value.
* **Save, Cache And Export the mask** (MASK, a collapsible section): Export Mask Image (16 bit PNG, EXR, TIF; the raw weight seen from above), **Bake To Image** (the mask becomes an Image source: a frozen, fast, shareable cache), Save Paint / Load Paint (the painted mask and the Houdini paint as `.json`).
* **The Layout tab is the Scatter tab** and holds the Mask, the Field Stack and the Falloff (in the order they work); the Variation tab no longer does. Parameter names are unchanged.
* Everything else is unchanged (the previous release is reproduced with Falloff on Radial or Box). Houdini 22 and 20.5 / 21. `tests/validate_maskshape.py`. GUI: unverified.

## v1.31.1 - A million instances as fast as the native Instancer

* **Checked against the native Instancer LOP** on the set `RnD_environment_kaspixjackie_setdress_v021.hip` (Houdini 20.5.445, an 8.4 million triangle mountain, the native Instancer scattering with its internal Scatter and Align SOP): Arraytron makes **exactly the requested number** of instances (1 000, 10 068, 100 000, 1 000 000), the native node lands within 0.003 percent of it (99 996, 999 991). Cook times (first / recook with a new seed): 10 068 instances 0.3 s / 0.3 s against 5.7 s / 0.6 s; 100 000 instances 0.6 s / 0.6 s against 7.0 s / 2.1 s; 1 000 000 instances 3.9 s / 4.0 s against 9.1 s / 4.0 s.
* **Faster for big scatters in Houdini 20.5 / 21:** the prototype path of every point is set with numpy (1.8 s down to about 0.3 s for a million points; `geo.points()` built a million point objects just to test for empty) and the points of Surface and Curve mode are created without a list of a million tuples (0.6 s). Nothing else changes; the points are the same.

## v1.31.0 - Big surfaces: the surface cache, Reduced Proxy, Place retired

* **Selecting the node was slow in a large scene** (the status bar said "Evaluating python" for 10 s): the Surface text and every cook read every triangle of the Surface Prim again. Measured on a set with a mountain of 8.4 million triangles (Houdini 20.5): the Surface text 9 s to 0.2 s, a recook 17 s to 0.5 s, the first cook 27 s to 13 s. The surface is now read once and kept (read only) until the incoming stage cooks again or the prim changes; the vertex normals are 20 times faster; the Surface text of a surface of more than 200 000 triangles that is not read yet shows its size only ("About N triangles ...") and the numbers come after the first cook.
* **Scatter On Reduced Proxy** (Surface mode, off by default): scatter on a poly reduced copy of the surface (vertex clustering, about 3 s for 8 million triangles, made once and kept). **Target Triangles** (default 100 000) and **Ghost Proxy** (Hidden / Viewport Only / Viewport And Render): the reduced surface drawn as a translucent mesh next to the instancer. The amount of points follows the area of the original surface; the points lie within about one cell of it. `docs/SURFACE_PROXY.md`.
* **Scattered counter** (read only, Layout tab, under the Distribution Mode): the number of instances, the points removed by Mask / Falloff / Thin / Separation / Avoid, and the instances per prototype; it never cooks the node and marks an out-of-date count as old.
* **Point Limit** (Surface mode, default 10 000 as before, up to 5 000 000): the cap on the number of points is a setting now, and the Scattered counter says "LIMITED: the settings ask for N, the Point Limit is M" when it cut the number (a Density of 1000 on a big surface asked for billions and stopped at 10 000 without a word).
* **The Place mode is retired** (use Arraytron Stamp): no button in the palette, no entry in the menu ("Place (retired)" keeps the slot, so Biome stays mode 10); a scene saved in the Place mode still loads and cooks.
* Everything else is unchanged: with the proxy off the previous release's points are reproduced (to float precision). Houdini 22 and 20.5 / 21. `tests/validate_surfproxy.py`. GUI: unverified.

## v1.30.1 - Show Gizmo

* The transform gizmo of **Move The Layout** (Position, Rotation, Scale) was bound on the node, so it was drawn whenever the node was selected, also while painting, placing or painting a mask. The viewer state owns it now: the new toggle **Show Gizmo** (Move The Layout, off by default) shows it, and Paint, Place, Mask Paint, Biome Paint and Pick hide it.
* The parameters Position, Rotation, Scale and Pivot are unchanged; nothing else changes. Houdini 22 and 20.5 / 21. `tests/validate_gizmo.py`. GUI: unverified.

## v1.30.0 - Surface mode: Keep By Direction
* **Scatter only on the faces that face a direction or a light, like Group Create > Keep By Normals.** New in the Surface settings: **Keep By Direction** (off by default), **Direction From** Vector or **Light Prim**, **Direction** (default 0 1 0), **Light Prim**, **Spread Angle** (default 45: the half angle of the cone), **Soft Edge** and **Include Opposite Direction**. The triangles whose normal lies within the Spread Angle of the direction receive the points; the Count stays exact (the points go on the kept triangles, and raising the Count still adds points without moving the earlier ones) and **By Density counts the kept area**. It works together with the slope limits.
* **Light Prim:** a Distant Light gives one direction (it shines along its -Z axis, so the way towards it is its +Z axis); a Sphere / Disk / Rect / Cylinder light gives the direction from every triangle to the light's position, so the points land on the faces that lean towards the lamp. A Dome light has no direction and is refused with a message. **Soft Edge** keeps the density at full up to Spread x (1 - Soft) and fades it smoothly to nothing at the Spread Angle; **Include Opposite Direction** also keeps the faces that point the other way.
* The Surface read-out says how many triangles were kept ("Keep By Direction: 2 of 12 triangles kept, area 100"). With the option off everything is exactly as in v1.29.0 (tested). `tests/validate_surfdir.py` (6 groups, 5 mutations), demo `tools/build_demo_surfdir_v1300.py` (`Arraytron_v1.30.0_surfdir_demo.hip`: flat tops, and the faces turned to a sun). Both builds. Not done: a viewport preview of the kept triangles (the Surface read-out gives the numbers); the light is read at the default time, not animated. Note: the default Slope Max of 90 degrees still leaves out downward faces, whatever the direction (raise it to 180 to scatter on undersides).

## v1.29.0 - Prototype Bank source type: Group Children
* **A new Source Type in the Prototype Bank: Group Children.** One row stands for every child prim of a group: Prim Path `/World/Group/*` (or just `/World/Group`) makes each active, drawable child its own prototype, in stage order. A name pattern works too (`/World/Group/rock*`, `?` and `[ab]` as well). The row's **Weight, Scale, Scale Random and Rotation Offset apply to each child** (a row of weight 1 with four children against a normal row of weight 4 gives 4 : 1 : 1 : 1 : 1). Children that are not drawable (materials), inactive, or deeper than one level are not prototypes; a child that holds this node's Output Prim is skipped. Resolved Prototypes lists every child. Works with every Selection Mode.
* A Group Children row has no LOD / Proxy prims of its own (they are ignored, the LOD generator skips it). A Biome Prototype Mix, Instance Place and an Override that name the row take its first child.
* Behind it: `resolve()` expands the row; a new Python SOP `PROTO_EXPAND` tells the prototype assignment (`src/vex_v1290/prototype_assignment.vfl`, the other VEX files are copies of vex_v190) which bank row each prototype belongs to. Without a group row everything is as in v1.28.0 (tested). `tests/validate_groups.py` (5 groups, 5 mutations), demo `tools/build_demo_groups_v1290.py` (`Arraytron_v1.29.0_groups_demo.hip`). Both builds. Not verified in the interface (GUI): the new menu entry and the picker in the Parameters pane.

## v1.28.0 - Paint the mask with Houdini's own Attribute Paint brush
* **New Mask Source: Houdini Paint, with three buttons.** **Paint Mask With Houdini Brush** builds a paint helper (a geometry object in `/obj` named `<node>_mask_paint`: the scattering surface as a dense mesh with a float point attribute `mask`, an **Attribute Paint SOP**, and OUT) and enters Houdini's own Attribute Paint viewport state with its heat map: every operation of that brush (Smooth, Sample, Multiply ..., foreground / background, soft edge, opacity, symmetry, pressure). Nothing is scattered while you paint. **Finish And Scatter** reads the painted attribute back into a compressed map, leaves the brush, shows the node again and the points are scattered with the mask (Mask Effect Density / Scale as for every source). **Clear Houdini Paint** forgets the map and deletes the helper. Press the first button again to continue the same strokes.
* The brush starts with the node's Foreground, Background, radius, feather and strength. **Paint Detail** sets how many points the helper surface has along its longer side (capped at about 200000 triangles); **Plane Size** gives modes without a surface (Line, Area, Grid, Circle ...) a flat square to paint on; Paint Surface, Unpainted Value, Map Feather and Map Resolution of the live brush also work here. Invert, Low / High, Gamma, the Remap Curve and the Output Range shape the result as for every source.
* The live brush of v1.26.0 / v1.27.0 (Mask Source Painted) is unchanged. `src/arraytron_hpaint.py`, `tests/validate_hpaint.py` (6 groups, 7 mutations), demo `tools/build_demo_hpaint_v1280.py` (`Arraytron_v1.28.0_hpaint_demo.hip`, with the helper in the file). Both builds. **Not verified in the interface (GUI), and not testable in hython:** that the button really enters Attribute Paint on the helper (`viewer.setCurrentState('sidefx_attribpaint')` with the helper as the viewer's network), that painting there is picked up (the tests stand in for the strokes with a wrangle after the Attribute Paint SOP), and that Finish And Scatter returns the viewer to the node's network.

## v1.27.0 - The full mask brush
* **The mask brush now has the controls of Houdini's Attribute Paint.** A **Foreground** and a **Background** value (X swaps them while painting; keys 9 / 0 change the Foreground); eleven **Brush Operations** (Paint, Erase, Add, Subtract, **Smooth, Multiply, Maximum, Minimum, Paint Background, Sample Foreground, Sample Background**; keys 1 to 8), their own menus for **Shift** (default Smooth) and **Ctrl** (default Opposite: Paint becomes Erase, as before); **Symmetry X / Z** about a Symmetry Center; **Fill Mask** (forget the paint and make the mask the Foreground everywhere); **Ctrl+Shift drag** resizes the brush; the prompt line shows the **mask value under the brush**.
* **Not realtime on purpose for the full operations:** Smooth, Multiply, Maximum and Minimum are applied when you release the mouse. Paint, Erase, Add, Subtract keep the live update of v1.26.0 (Live Update).
* A v1.26.0 painting gives the same scatter (tested). Demo `tools/build_demo_maskfull_v1270.py` (`Arraytron_v1.27.0_maskfull_demo.hip`). `tests/validate_maskpaint.py` now has 10 groups and 13 mutations (new: mp_smooth, mp_sym, mp_stamp, mp_shift, mp_heavy). Both builds. Not verified in the interface (GUI): the brush in a real Scene Viewer. Not done: tablet pressure, the Attribute Paint shape / Connected Only / Visible Only options and the middle mouse operations (the middle button and Alt navigate the camera here).

## v1.26.0 - Painted mask: a live viewport brush with feather, and full mask remap
* **New Mask Source: Painted.** Press **Paint Mask** (Variation tab, Mask) and drag on the surface: the mask is painted with a viewport brush and **the scatter follows the brush live** (the paint is written about ten times a second while the stroke goes on, one undo step per stroke; **Live Update** switches this off for heavy scatters). Works in every Distribution Mode: the brush paints on the Surface Prim / Paint Target / Biome terrain, or on a ground plane at Y 0 (or on the **Paint Surface** you name).
* **Brush:** Operation (Paint towards the Brush Value, Erase, Add, Subtract; Ctrl flips it), Radius, Strength (a weak brush builds up like an airbrush), **Feather** (0 hard disc to 1 soft from the middle, with a Linear / Smooth / Gaussian curve; the white inner ring shows the hard core) and Brush Value. Shortcuts: LMB paint, Ctrl+LMB opposite, 1-4 operation, [ ] radius, - = strength, , . feather, 9 0 value, F curve, wheel with Shift / Ctrl / Ctrl+Shift, H help, Esc / Enter finish. **Unpainted Value** (0 empty until painted, 1 full until erased), **Map Feather** (blurs the whole painted map, in scene units) and **Map Resolution**. **Show Mask While Painting** turns Mask > Visualize on while the brush is active and off again at the end.
* **Full remap of the mask weight, for every Mask Source:** Invert and Low / High as before, then **Gamma**, a **Remap Curve** (a ramp, switched on with Use Remap Curve) and an **Output Range** (squeeze or flip the final weight). All at defaults that reproduce v1.25.2 exactly (tested).
* New: `src/arraytron_maskpaint.py`, the mask brush in `src/arraytron_paint_state.py`, `tests/validate_maskpaint.py` (7 groups, 8 mutations: mp_order, mp_feather, mp_base, mp_blur, mp_gamma, mp_range, mp_live, mp_ctrl), demo `tools/build_demo_maskpaint_v1260.py` (`Arraytron_v1.26.0_maskpaint_demo.hip`: a feathered clearing, a path through a forest, a remapped airbrush). Both builds. Not verified in the interface (GUI): the live brush in a real Scene Viewer (stroke feel, the undo step, the mask display), the look of the demo. The paint is in the space the points are generated in, like the Image and Biome map (a Bounds Transform moves the scatter, not the paint).

## v1.25.2 - The test ground steps aside for an external surface
* **The built-in test plane is no longer added when you scatter on your own surface.** The plane is added to the stream only while **Surface Prim** still names it (`/World/TestGround` or a prim under it); as soon as Surface Prim points at another prim (a terrain, a Grid LOP, any external source) the plane is left out, so it no longer lies under or through your surface. The same on both builds.
* **Wiring an external source into a node that still uses the test ground switches it off:** Built-in Test Ground goes off and Surface Prim returns to its default (`/World/Terrain`), set by an `OnInputChanged` handler on the HDA (`test_ground_input_changed`). A Surface Prim you typed yourself is never replaced.
* Nodes with Built-in Test Ground off (the default for every node that is not a test run) are unchanged. Demo: `tools/build_demo_groundauto_v1252.py` (`Arraytron_v1.25.2_groundauto_demo.hip`). `tests/validate_testsetup.py` now has 4 groups and 8 mutations (new: ts_autohide, ts_wire). Not verified in the interface (GUI): that the handler fires when you drag a wire in the network editor.

## v1.25.1 - Test setup: a ground plane, and it really runs
* **A new node starts as a test run on a ground plane:** 30 built-in spheres scattered (Surface mode) on a built-in flat 10 x 10 test ground at `/World/TestGround/Plane`, instead of a 5 x 5 Grid layout. The plane is a Python LOP inside the HDA that adds it to the stream while **Built-in Test Ground** (Prototypes tab, section TEST SETUP) is on; wire a real surface and switch it off or change Surface Prim.
* **Fix: the test setup did not run on a new node in the interface.** The check required every parameter to be at its default (the Visualize ramp is not), so the hook skipped real nodes. It now looks only at the wiring, the mode and Prototype 1, and prints why when it skips. New button **Start From Test Setup** makes any node a test run (one undo step).
* `tests/validate_testsetup.py` (2 groups, 6 mutations: ts_inputs, ts_changed, ts_mode, ts_path, ts_force, ts_ground). Both builds.

## v1.25.0 - Mask noise types, Visualize colours, test setup
* **The Mask Source Noise offers all fifteen noise types** (Variation tab, Mask > Noise Type right under Mask Source): Perlin, Simplex, Random, Curl, Value, Alligator, Worley, Voronoi, Ridged, Billow, Turbulence, FBM, Domain Warp, Flow, Periodic (with a Period). The default is Value, the original mask noise, so existing masks do not change. Frequency, Octaves, Roughness, Contrast, Offset and Seed work for all of them; Visualize shows them too. They are numpy versions (`src/arraytron_noises.py`), the same ideas as the VEX of the positional shift but not the same pattern. The Noise section is now called **Noise Positional Shift**.
* **Visualize paints vertex colours** on a copy of the scattering surface (Surface Style: Vertex Colours / Dots / Both; Surface Resolution = the number of small triangles), with **palettes** (Blue to Yellow, Heat, Viridis, Magma, Rainbow, Grayscale, Red Yellow Green, Cool to Warm, Terrain), a **Custom Gradient** ramp, a **Range** to stretch small differences and a **Surface Opacity**. The instances use the same palette and range.
* **A new node starts as a test run:** made in the interface with nothing wired in and nothing changed, it becomes the built-in sphere (a USD file inside the HDA) on a 5 x 5 Grid, so something shows before real prototypes and surfaces are plugged in. The HDA now works with **no input** (Min Inputs 0). Scripts and tests get the plain defaults (the hook runs only when the interface is available).
* Demos: `build_demo_masknoise_v1250.py`, `build_demo_palettes_v1250.py` (also in the all-demos scene). `tests/validate_masknoise.py` (4 groups, 5 mutations), `tests/validate_testsetup.py` (2 groups, 4 mutations), `tests/validate_noise.py` 10 groups. Both builds.

## v1.24.0 - Proxy display, Visualize, eleven new noise types
* **Display: Boxes and Spheres** (Debugging tab, next to Points Only): every instance is hidden and drawn as a guide box (the bound of its prototype, turned and scaled like the instance) or as a sphere around it, coloured by prototype. A cheap proxy of the whole scatter. Guide purpose, never rendered (the render is empty while it is on).
* **Visualize** (Debugging tab, section VISUALIZE; also a Visualize menu in the Mask and the Noise sections): shows the Mask, the Field Stack, Mask x Field Stack or the Position Noise as colour, blue 0 to yellow 1, on dots over the scattering surface (Surface, Paint, Cluster and Area modes) and / or on the instances (a dot at every instance, or the colours of the Points Only / Boxes / Spheres display). The Noise stage now leaves `v@noise_disp` for it.
* **Fix: the display and debug guides did not show in the viewport.** Hydra does not draw the children of a PointInstancer that are not prototypes, so every Debug view now sits in a sibling prim `<output>_View` (with the transform of the instancer). Nodes older than v1.22.0 keep the child prim.
* **Noise moved to the Variation tab** (section NOISE above the Mask, the toggle is now called Noise) and has **eleven new types**: Value, Alligator, Worley / Cellular, Voronoi, Ridged Multifractal, Billow, Turbulence, FBM, Domain Warp, Flow and Periodic (with a Period). All use Frequency, Octaves, Roughness, Pattern Offset, Seed and the per-axis Amount. Older nodes keep their tab.
* Demos: `build_demo_noisetypes_v1240.py` (all new types + the Mask visualizer), `build_demo_viz_v1240.py`, `build_demo_proxy_v1240.py`; all in the all-demos scene.
* `tests/validate_noise.py` (9 groups, 16 mutations: view_hide, view_points, view_shape, viz_heat, viz_field, viz_noise, viz_lift, noise_ridged, noise_period and the earlier ones). Both builds. Documentation `docs/NOISE_AND_DISPLAY.md`.

## v1.23.0 - Copy settings between Arraytron nodes
* **Import Settings** (Prototypes tab, section COPY SETTINGS): copies the settings of another Arraytron node onto this one. Source Node empty: the button finds one itself (wired to the same input first, then the one with the most changed settings, then the newest). What was copied and what had no counterpart is written into Last Import.
* **From code:** `hou.node(dst).hdaModule().copy_settings(dst, src, only_changed=False)` returns `{copied, missing, failed}`; `import_settings(node, source=None)` is the button. Works between any versions: the single Prototype of the first releases becomes row 1 of the Prototype Bank; multiparm counters are copied first so the rows exist; animation (keyframes) is copied; buttons and read-outs are not settings. One undo step. Shortcut: expressions are copied as their value, not as text.
* Checked on the legacy nodes of a shot (v0.15 nodes, one Prototype): 39 settings copied, the same 10 instances as the old node. `tests/validate_copy.py` (4 groups, 5 mutations). Docs: `docs/COPY_SETTINGS.md`.

## v1.22.0 - Noise, Points Only display, cycling Stagger
* **Position Noise for every Distribution Mode** (Layout tab, section NOISE; off by default): Perlin, Simplex, Random (per point, keyed on the id) or Curl noise, an **Amount per axis** (0 keeps an axis exactly), Frequency, Octaves / Roughness, Pattern Offset and a Seed. It runs after the distribution and the Rows, before the Mask, the Field Stack and the rest, and never changes ids or counts. `src/vex_v190/noise.vfl`, `docs/NOISE_AND_DISPLAY.md`.
* **Display: Points Only** (Debugging tab): hides every instance (invisibleIds) and draws the scattering points as guide points, coloured and sized by the Debug options. Not rendered; the render is empty while it is on.
* **Fix: Stagger Rows above 1** pushed a Circle's rings outward (a straight shift along the tangent). It now cycles (1.5 is 0.5, a whole number is off) and in a Circle the odd rings are turned about the centre with their facing, so they keep their orbit.
* `tests/validate_noise.py` (7 groups, 9 mutations); `tests/validate_rows.py` 7 groups (new `rows_wrap`, `rows_orbit`). New demo `build_demo_noise_v1220.py` (also in the all-demos scene). Both builds.

## v1.21.1 - LOD generator on Houdini's own assets
* **Fix: the LOD levels of a Test Geometry asset (Rubber Toy, ...) rendered black or did not exist.** Two causes: the meshes of Houdini's assets are **left-handed** and the generated normals pointed into the mesh (a level shaded from the inside renders black, though the material was bound), and the assets are **instanceable** (their meshes and materials are instance proxies that the traversal skipped, so no level was written at all). Now the normals follow the orientation and the traversal steps into instance proxies; the levels are bound to the material of the hero. Right-handed meshes are unchanged.
* New tool `tools/lodgen_render_check.py <version> [--instanceable 0|1]`: renders the Rubber Toy as hero, LOD 1, LOD 2 and proxy with Karma (CPU) and compares the colour of each level with the hero (PASS when within the tolerance). v1.21.1: all three levels within 0.05 of the hero; v1.20.0: black.
* `tests/validate_lodgen.py` has 10 groups and 10 mutations (new: `lodgen_hand`, `lodgen_proxy`). Both builds.

## v1.21.0 - LOD generator keeps the materials
* **Fix: the generated LOD levels lost the textures of the hero.** Face GeomSubsets (a material per face group) were dropped, Material and shader prims inside the prototype were copied without their connections (black), and a binding inherited from a parent was not found by the copy. Now the subsets are mapped onto the reduced triangles, the hero's effective material is bound directly on every copy (also on every subset), and no Material or Shader prim is copied: the levels use the hero's own materials and textures. Defaults and everything else are unchanged; earlier builds keep their old behaviour.
* **The all-demos scene is laid out as a grid** (6 boxes per row, equal cells) instead of scattered boxes. The LOD demo's dense rock has two materials by face group (stone, moss) so the levels show both.
* `tests/validate_lodgen.py` has 9 groups and 8 mutations (subsets mapped onto the triangles, bindings, inherited bindings, no copied material, the hero network untouched, an exact copy keeps its subsets). Both builds. Documentation `docs/CAMERA_LOD_PRIMVARS.md`.

## v1.20.0 - Painted biome map
* **Paint where a biome grows.** The **Paint Biome Map** button enters a viewport brush (a mode of the Arraytron viewer state): drag to paint the active biome row (keys 1 to 9), Ctrl+drag to keep it out, radius / strength / falloff on keys and wheel, one undo step per stroke. Every row has a **Painted Map** menu (Off by default = exactly v1.19.0; **Add And Erase**: grows also where painted, kept out where erased; **Only Where Painted**). The paint is a list of stamps turned into a per-row map over the terrain at cook time (*Map Resolution*, default 256), combined with the weight of the conditions; the ids are the biome's own, so painting never moves anything outside the stroke. Painted biomes take part in the layers and the clearance. Clear Row Paint / Clear All Paint, a read-out of the stamps.
* New suite `tests/validate_biomemap.py` (6 groups, 4 mutations); the Biome demo gets a *Painted flowers* row along a painted path. Both builds. Documentation `docs/BIOME.md`.

## v1.19.0 - Biome layers, exclusion and presets
* **Layers and Clearance** (every Biomes row): *Layer* (1 top to 4), *Clearance* (a radius times the point's own scale) and *Excludes Rows*. A biome on a lower layer keeps clear of the points of the layers above it, and a biome keeps the rows it excludes clear whatever their layer. Only the biomes above remove points, so a lower layer never moves the ones above; ids stay stable; Clearance 0 (the default) is exactly v1.18.0. The read-out counts the points *cleared by the layers above*.
* **Biome presets:** *Load Preset...* (Temperate Forest, Alpine, Coastal Wetland, Desert, and your own) and *Save Preset...*; elevations are fractions of the terrain height so a preset fits any terrain; one undo step. User presets in `biome_presets.json` next to the Asset Library.
* New suite `tests/validate_biomelayers.py` (6 groups, 4 mutations); the Biome demo shows the forest clearing the rocks and stones under its trees. Both builds. Documentation `docs/BIOME.md`.

## v1.18.0 - Asset Library
* **Asset Library** (Parameters pane, under the Mode Palette): a local catalogue of USD assets with **your own categories** (Trees, Plants, Rocks, Props by default). Import from the **Solaris Asset Catalog** (names, thumbnails, tags), from USD files, from a folder or by dragging files; search by name or tag; **Add to Bank** (or double-click) puts an asset into the Prototype Bank as a USD File row. Thumbnails for plain USD files are drawn by a small software renderer. One JSON file per user (`Documents/Arraytron/library`, or `ARRAYTRON_LIBRARY`). Logic in the HDA's PythonModule (usable from scripts), Qt section in the panel. Documentation `docs/ASSET_LIBRARY.md`.
* **Stagger Rows is a slider** (0 to 1, the fraction of the gap; 0 off, 0.5 the old brick pattern) instead of a tick. Earlier releases are unchanged.
* New suite `tests/validate_library.py` (6 groups, 4 mutations); the Rows suite checks the slider. Both builds.

## v1.17.0 - Mode Palette
* **The Distribution Mode is chosen on a palette of big icon cells** at the top of the node's Parameters pane: one cell per mode with its **title under the icon**, the selected one lit (warm tile, yellow frame), the others dim; click a cell to choose the mode. It is a Python Panel registered for the Arraytron node type (like the brush row of Paint Instances) with the node's own parameter dialog embedded below it: no parameter was added, removed or moved and the output is identical to v1.16.0. Icons are drawn by code (`tools/make_mode_icons.py`, 22 SVGs embedded in the HDA); the Paint icon is a simple brush. `ARRAYTRON_NO_PARM_PANEL=1` keeps Houdini's plain dialog.
* New suite `tests/validate_modepanel.py` (4 groups, 4 mutations). Both builds (PySide6 / PySide2). Documentation `docs/MODE_PALETTE.md`.

## v1.16.0 - Biome effect
* **Effect per condition** in every Biome row (Layout tab, Biomes table): *Elevation / Slope / Moisture / Temperature Effect* (0 to 1, default 1). 1 is the condition as set, 0 ignores it completely, in between it only partly counts (`weight = 1 - effect * (1 - band)`), so a biome can follow the elevation but not the temperature. Defaults reproduce v1.15.0 exactly.
* `tests/validate_biome.py` now has 8 groups and 7 mutations (`biome_effect`). The demo uses the Effect on the Shore stones. Both builds. Documentation `docs/BIOME.md`.

## v1.15.0 - Biome
* **New Distribution Mode: Biome** (Layout tab): rule based scatter on a terrain. A table of biomes; every row has its conditions (**elevation, slope, moisture, temperature**, each a range with a soft edge), a density, a **Prototype Mix** (bank rows with weights) and a scale range. Biomes blend at their borders (an ecotone): a candidate survives with the probability of the product of its four band weights, with the id keyed hash of the Mask, so a higher density only ever adds points and biomes never move each other's points.
* **Fields:** elevation, slope (face or smooth normals), moisture (constant, noise, distance to a water mesh or curve, an image; with variation and bias) and temperature (base minus a lapse rate, noise, a warm facing). **Primvar: biome**, a **Biome** colour for the debug view, a per-biome read-out.
* New suite `tests/validate_biome.py` (7 groups, 6 mutations) and a demo (forest, alpine firs, cliff rocks, shore stones on a hilly terrain with a pond). Both builds. Documentation `docs/BIOME.md`.

## v1.14.0 - Rows
* **Rows** (Layout tab, section ROWS; Line, Circle / Radial and Curve): the path is laid out in several parallel rows (next to each other, concentric rings, copies of the curve pushed to the side) with *Row Spacing*, *Centre The Rows*, *Random Offset* (across), *Random Shift Along*, *Stagger Rows* and a seed. The count of the mode is the points of one row. Row 0 keeps its ids; the other rows get derived ids, so changing the number of rows never renames a point. It runs right after the distribution, so the Mask, Field Stack, Falloff, Variation and everything after it work on every row. Off by default: the output is exactly v1.13.0.
* The Curve generator writes the direction of the path (`pathdir`) on its points. New suite `tests/validate_rows.py` (6 groups, 6 mutations) and a demo. Both builds. Documentation `docs/ROWS.md`.

## v1.13.0 - Falloff follows the mode, renamed tabs, Export tab
* **Falloff respects the other modes** (*Region: Automatic*): **Cluster** fades every cluster to its own boundary (centre and radius of each cluster, not the box or circle around all of them); **Paint** fades across the width of every stroke (the viewport brush now records the path of each Add / Replace stroke, stored in the Paint Data as `p2`; scenes painted earlier fall back to the whole layout); **Grid** uses all three axes when it has layers in Y (a 3D matrix), so its top and bottom boundaries count too. *Whole layout* keeps the v1.12.0 behaviour.
* **Tabs renamed:** Source -> **Prototypes**, Look -> **Variation**, Finish -> **Debugging**; **Export USD** and the cache read-out moved to a new **Export** tab (nine tabs). Parameter names did not change.
* New suite groups: falloff 10 groups / 10 mutations, paint 18 groups / 5 more mutations (stroke paths). Both builds. Documentation `docs/FALLOFF.md`.

## v1.12.0 - Falloff
* **Falloff** (Layout tab, section FALLOFF): the scatter is full size and densest in the centre and fades towards the edges, in scale and in density. Works with every Distribution Mode; Radial or Box shape (every edge of a rectangle fades), Linear / Smooth / Gaussian curve, a flat centre, an edge density and an edge scale, automatic or custom centre and reach, X and Z or X, Y and Z. After the Mask and the Field Stack (their results are kept), before the Variation. Off by default: the output is exactly v1.11.0.
* New suite `tests/validate_falloff.py` (6 groups, 6 mutations) and a demo (plain, radial and box patches). Both builds. Documentation `docs/FALLOFF.md`.

## v1.11.0 - Place tool extras and cleanups
* **Place tool:** press, drag, release (drag sideways to turn, up or down to scale the new instance; a heading line in the marker); **Snap Position** (grid, kept on the surface) and **Snap Rotation (deg)**; **Place Along Curve** (a BasisCurves prim, by count or spacing, following the curve, optionally projected on the surface).
* **Cleanups:** a new Arraytron node is called `arraytron1` (not `instancer1`); the Physics Settle switch is called **Settle Instances**.
* `tests/validate_place.py` now has 14 groups and 13 mutations; the Place demo gets stepping stones along a curve. Both builds.

## v1.10.0 - Instance Place arrays
* **Copies:** any row of the Placed Instances table can make an array like the Copy and Transform SOP: *Copies*, *Step Translate*, *Step Rotate*, *Step Scale* and *Step Space* (Local follows the copy: spirals, fans, squares; World: straight rows). Copy 0 keeps the row id, the other copies get stable ids derived from it (`1000000000 + id * 10000 + k`); a row without copies is exactly as before.
* The viewport tool places arrays too: new settings *New Copies*, *New Step Translate / Rotate / Scale / Space*; Ctrl+click on a copy deletes its whole row.
* `tests/validate_place.py` now has 11 groups and 9 mutations (arrays against 4x4 matrix products); the Place demo shows a spiral and a fence. Both builds.

## v1.9.0 - Instance Place
* **New Distribution Mode: Instance Place** (Layout tab): instances are placed one at a time, like the transforms of a Copy and Transform SOP. A table (*Placed Instances*) holds every instance: on, stable id, position, rotation, scale and the Prototype Bank row it uses. Mask, Field Stack, Separation, Physics, Instance Overrides, Grow, Variation and primvars work on placed instances like on any others.
* **Place Instances in Viewport:** click a surface to add one instance (aligned to the surface normal if you want, with the New Scale, New Rotation and New Prototype Row settings); Ctrl+click deletes the one under the mouse; wheel and keys change the settings; every click is one undo step. Selecting the node never starts the tool. Fix Ids writes unique ids into rows that have none.
* New suite `tests/validate_place.py` (8 groups, 5 mutations); demo `Arraytron_v1.9.0_place_demo.hip`; documentation `docs/INSTANCE_PLACE.md`. Both builds. New VEX folder `src/vex_v190` (a placed instance may name its Prototype Bank row).

## v1.8.0 - LOD generator
* **Generate LODs** (Optimize tab): reduced copies of every prototype are written as the LOD 1, LOD 2 and Proxy levels of each Prototype Bank row that has no prim of its own for the level (a typed prim always wins). Set the share of triangles of each level (50 / 20 / 5 % by default) and a minimum. Vertex clustering with quadric positions, plain numpy, the same in Houdini 22 and 20.5 / 21; uv, colours and other primvars, transforms and material bindings are carried over; the heroes are never touched. Switch by distance or screen size with the existing Level Of Detail controls.
* New LOD_GENERATOR node (Python LOP) between the source resolver and the compiler; it does nothing with the switch off. New suite `tests/validate_lodgen.py` (8 groups, 5 mutations) and a demo (a ladder of four levels and a field of rocks).

## v1.7.0 - Pick Instance
* **Pick Instance in Viewport** (Finish tab): click an instance in the viewport and its stable id becomes an override row; Ctrl+click ticks Delete as well. A yellow ring marks the instance under the mouse and the prompt shows its id (and its row when it has one). Esc / Enter finishes; every click is one undo step. Instances come from the node's USD stage, so deleted, hidden and not yet grown instances are not pickable. Both builds.
* Selecting the node never starts picking; only the button does. New suite `tests/validate_pick.py` (6 groups, 5 mutations).

## v1.6.2 - Physics tab
* The **Settle** tab is now called **Physics** (the *Physics Settle* switch inside it keeps its name). Parameters and output are unchanged; scenes built with older versions keep their node type and their tab names.

## v1.6.1 - Paint no longer switches the mode by itself
* **Fix:** selecting the Arraytron node (for example after working on another node) entered the Paint viewport tool, which switched *Distribution Mode* to Paint and broke the layout. The tool now never changes the mode: with any other mode it stays idle (nothing drawn, every mouse and key event is left to Houdini) and it wakes up only when the mode is Paint (the *Start Painting* button sets it). Scenes already switched by the old tool need the mode set back by hand.
* The HDA is otherwise identical to v1.6.0 (the suites compare against it); both builds. The paint suite checks the idle behaviour.

## v1.6.0 - Paint shortcuts
* **Paint tool shortcuts:** Ctrl+LMB erase, Shift+LMB relax, Ctrl+Shift+LMB drag sideways = radius, mouse wheel with Shift / Ctrl / Ctrl+Shift = radius / strength / density, keys `[ ]` radius, `- =` strength, `, .` density, `1-4` operation (Add, Remove, Replace, Relax), `F` falloff, `H` help line. Alt and the middle mouse button still navigate.
* A live prompt line shows the brush values (radius, strength, density, falloff, point count); the brush ring changes colour with the operation and a white inner ring shows a strength below 1.
* New suite group 'Brush shortcuts' in `tests/validate_paint.py` (17 groups, 3 new mutations); both builds. The K demo carries the shortcut list in its node comment.
* **Check for Updates:** an *Arraytron* shelf tool installs a newer release from GitHub (`version.json` + zip, SHA-256 checked, nothing runs in the background); `tools/make_update_zip.py` builds the update zip. The HDA itself is unchanged.

## v1.5.0 - Imported Points
* **Paint tool fix (2026-10-15):** the viewport brush follows the mouse (mouse ray from `ui_event.ray()`), a click paints a dab, tool errors show in the viewport prompt. New demo: the letter K painted with the brush (`Arraytron_v1.5.0_paint_k_demo.hip`).
* **Imported Points** (Layout tab, mode 9 in the list): scatter on the points of an FX simulation or any points, from a **SOP node** or a **USD Points / PointInstancer prim** (world space, time samples, time offset); the instances follow the simulation over the timeline.
* Controls: **use percent of points** (stable, only adds), **instance ids** from the source's own id attribute (a particle keeps its prototype, look and overrides), **scale** from `pscale` / `scale` times a multiplier, **orientation** from an orient attribute, along the velocity or from a normal, **copy attributes** from the source.
* **Even Percent** Selection Mode: the Prototype Bank weights become nearly exact percentages for any set of ids (stable per id), with a **Share Of The Points** read-out.
* **IDs for AOVs:** primvars `source_id` and any copied source attribute (besides `arraytron_id`, `prototype_id`, `random`).
* Houdini 22 and Houdini 20.5 / 21 builds with identical output (`tests/validate_h205.py`); new suite `tests/validate_imported.py` (13 groups, 7 mutations) and a demo with 1,800 animated particles. Documentation: `docs/IMPORTED_POINTS.md`.

## v1.1.0 - Houdini 20.5 and 21
* **Houdini 20.5 / 21 build** (`otls_h205/Arraytron_v1.1.0_H205.hda`): the same node on the older Instancer LOP. Houdini 22 keeps its HDA and its behaviour; every suite passes unchanged. The 20.5 / 21 build writes the same PointInstancer (prototype paths, bank order, `protoIndices`, `invisibleIds`, primvars): `tests/validate_h205.py` compares the two on every demo and on an edge-case scene.
* The installer prepares Houdini 20.5, 21 and 22, each with its own build; demos for both (`demos`, `demos_h205`).
* Fixes that came out of the port and also apply to Houdini 22: the debug view no longer uses `Geometry.pointCount()`; the Grow `invisibleIds` are written at the time sample of the instancer when it has one.
* Known limits in 20.5 / 21: restart Houdini after updating the HDA (a re-installed node type loses its parameters there, a SideFX handle-binding problem); no Bullet ground margin; the interface was not checked by eye (headless tests only).

## v1.0.0 - production release
* **Instance overrides** (Finish tab): Delete, Move, Rotate, Scale, Prototype per stable instance id; applied after the physics and before Grow.
* **Paint:** Replace and Relax added to the brush operations.
* **Debug views** (guide purpose, never rendered): generated and rejected points, colour by prototype / id / weight, axes, collision radius, cluster centres.
* **Export USD** (self-contained instances file) and a caching strategy (`docs/CACHING_AND_PIPELINE.md`).
* **Stable-id audit** of every Distribution Mode; **production tests** (saved scene round trip, cross-process determinism, 20,000 point stress, fuzzing, `usdchecker`, script lint, release hygiene).
* Documentation: user guide, index, troubleshooting, handoff; a richer Help tab in the HDA; the installer package (`Arraytron_v1.0.0_Release.rar`) and the DevKit for continuing the work on another PC (`Arraytron_v1.0.0_DevKit.rar`).
* Fixes found by fuzzing: debug and Grow-arrow guides no longer crash when the points fail to cook.

## v0.9.0
* **Optimize tab:** camera optimisation (frustum, distance, density by distance, behind camera; hidden through `invisibleIds`), LOD / proxy prototypes per Prototype Bank row (switch by distance or screen size), extended primvars.

## v0.8.0
* **Cluster** distribution; No Overlap merged into **Separation & Collision** (priority, **Avoid Geometry**).

## v0.7.0
* **Field Stack** (Height, Slope, Noise, Image, Distance, Exclusion; Multiply / Add / Subtract / Min / Max). HDA icon embedded.

## v0.6.0
* Viewport **brush** (Paint mode, Python Viewer State); clearer input sockets; all demos in one scene.

## v0.5.2
* Six-tab interface and the **Grow** animation.

## v0.5.1 / v0.5.0
* **No Overlap**; **Masks** (noise, image, mesh primvar).

## v0.4.6 / v0.4.5 / v0.4.0
* Surface Scatter; Curve; **Physics Settle** (Bullet, cached).

## v0.3.x and earlier
* Prototype Bank, Circle, Variation, Grid, Scale Instances, Bounds Transform with viewport handle (`docs/VERSIONING.md`).
