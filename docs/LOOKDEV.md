# Lookdev tab: materials and per-instance variation (v1.35.0)

The **Lookdev** tab (after Edit, before Optimize) puts materials on the finished scatter and makes values of a material vary per instance.

## Material Assignments

A row binds a **Material** prim of the stream to **All Prototypes** or to the prototypes of one **Prototype Row** (its LODs too). Wire your material library (a Material Library LOP) into the first input; the Material field lists the material prims it finds. The binding is stronger than the bindings inside the prototype; rows further down win. A material can only go on a prototype: every instance of that prototype gets it.

## Per-Instance Variation

A row gives every instance its own value between **Min** and **Max**, from its **Instance Id** (it keeps its value when other settings change) or one value per **Prototype**, with a **Seed**.

* **Type** decides how the value is made: **Float** one number; **Vector3** every component random on its own (random colours on a colour input; a component with Min = Max stays fixed, for an `hsvadjust` amount use Min `-0.1 1 1`, Max `0.1 1 1` to vary the hue only); **Color3** one blend between the Min colour and the Max colour.
* The value is written as the primvar `arraytron_lk<row>` on the PointInstancer (per instance), typed like the input it is wired to.
* **Connect Automatically** adds a reader next to the shader (MaterialX `geompropvalue`, or `UsdPrimvarReader` for USD Preview materials) and wires it into the **Input** of the **Shader** (a name inside the material, a path relative to it such as `materialx/mtlxstandard_surface`, or a full path).
* **Operation**: **Replace** (the input takes the value), **Multiply** or **Add** (MaterialX: what fed the input, a texture or a constant, is kept and multiplied by the value or added to it).
* **Primvar Only** writes just the primvar; read it in any shader yourself (a VEX material for example).

## A ready-made USD asset (the rubber toy)

1. Wire the asset into the first input and use its prim as the prototype (Prim Path `/rubbertoy`).
2. Arraytron copies the asset into the prototypes, its material too: pick that copy, `/World/Arraytron/Prototypes/rubbertoy/mtl/ToyShader` (the Material menu lists it).
3. Shader `materialx/mtlxstandard_surface`, Input `subsurface_color` (this asset's look comes from its subsurface; check which input drives the colour of yours), Operation **Multiply**, Type Vector3, Min `0.15 0.15 0.15`, Max `1 1 1`: every toy keeps its texture with its own tint.

The edit is made on Arraytron's copy of the asset; the file on disk is never touched.

## Editing the asset's own material after the scatter

To change a value of the asset's material for every instance (not per instance), override it on Arraytron's copy after the Arraytron node: an Edit Properties LOP on the shader prim (for example `.../ToyShader/materialx/mtlxmultiply1`, input `in2`; not tested), or a Python LOP that sets the inputs (tested). Only the values set are written; the textures and the rest of the material stay. Demo: `Arraytron_v1.35.0_matedit_demo.hip` (`tools/build_demo_matedit_v1350.py`: the toy as scattered next to the same scatter with the node `edit_toy_material`, whose Tint, Subsurface and Roughness Scale override the shader values).

Houdini's Edit Material LOP does not work on this asset: its shaders sit inside a MaterialX node graph, and Edit Material writes them back without their values (black toys; the same on the original `/rubbertoy` material, Houdini 20.5).

Code: `src/arraytron_lookdev.py` (appended to the PythonModule), the Python LOP `lookdev` (`src/lookdev.py`) after the camera optimisation. Test: `tests/validate_lookdev.py`. Demo: `Arraytron_v1.35.0_lookdev_demo.hip` (MaterialX hue per instance, a USD Preview clay colour per instance, the rubber toy tinted).

Generated LOD levels (Generate LODs) use the same materials as the hero copy, so the variation reaches every level (v1.38.2). The variation shows in Karma; the Houdini GL viewport shows the plain material. Not verified: Karma VEX material builders (use Primvar Only), render engines other than Karma.
