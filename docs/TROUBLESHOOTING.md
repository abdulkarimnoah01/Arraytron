# Troubleshooting (v1.21.0)

Errors are written to the node (red) in plain words. The most common ones:

| You see | Why | Fix |
| --- | --- | --- |
| *Prototype N: Prim Path is empty* / *... does not exist in the incoming stage* | the Prototype Bank row points to nothing | type the prim path of the model, or switch the row's *Source Type*. |
| *The Surface Prim / Cluster Surface / Paint Target ... does not exist in the incoming stage* | the prim is not in the stream | wire your scene into the **first input**, and pick the prim from the picker. |
| *No mesh or basic shape found under ...* | the prim holds no mesh | pick a mesh, or a prim above one. |
| *Camera Prim ... is not a camera in the stream* | the camera is not wired in or has another path | put a **Camera LOP before Arraytron** and pick it (default `/cameras/camera1`). |
| *Prototype N LOD 1 (...) is already used by ...* | the same prim is two prototypes | use a different prim for each hero and LOD. |
| *Avoid Geometry: the Prim is empty* / *Export File is empty* | a required path is blank | fill it in or switch the feature off. |
| *Cannot read the paint* | the stored paint text is damaged | press **Clear Paint** and repaint (or restore the node from the saved hip). |
| *No camera data yet* | Camera Optimisation is on but the stage has not cooked | cook the node (select it); check the camera prim. |

## Houdini 20.5 / 21

| You see | Why | Fix |
| --- | --- | --- |
| The Arraytron node has only a few parameters (about 30) after you updated, removed or re-installed the HDA, or opened another scene that recorded the HDA | in Houdini 20.5 and 21 a node type with viewport handle bindings cannot be loaded a second time in the same session (a SideFX problem; Houdini 22 only warns) | **restart Houdini.** Normal work is not affected: the package loads the HDA once at startup, and the demo scenes do not record the HDA. |
| *Houdini 20.5 / 21 build needs the top-level name /X for the prototype ...* | a prim named like a prototype's last name already sits at the top level of your stage (for example `/Rock` next to `/World/Props/Rock`) | rename or move that prim. |
| Physics results differ a little from Houdini 22 | the Bullet solver of 20.5 / 21 is another build and has no ground margin | settle again in the version you render with; caches are keyed by the settings, so each Houdini bakes its own. |

## Painting

| You see | Why | Fix |
| --- | --- | --- |
| The Paint tool is active but the brush circle does not follow the mouse, or nothing is painted | an old state is loaded in the session, or the Paint Target is missing / has no mesh | reopen the hip (or restart Houdini) so the current HDA is loaded; check that the Paint Target prim exists in the first input and holds a mesh or shape; read the viewport prompt, it shows the error of the tool |
| The painted points sit above or below the surface | *Offset* is not 0, or *Align to Normal* tilts them | set Offset 0 and Align 0 (upright) |

## It cooks but the result looks wrong

* **Nothing appears:** check *Count*, the *Mask* (a Density mask with Low = High removes everything), the *Field Stack* read-out ("Kept N of M"), *Separation* / *Avoid Geometry* read-outs, and the Optimize tab's read-out (frustum culling uses the camera aperture and the current frame).
* **Instances in the wrong place:** heights, positions and images use the space the points are generated in; prims are read at their world transform. With a Bounds Transform away from the identity the two no longer line up, so keep it at the identity when fields or avoidance use prims, or use a world-space mode (Surface, Paint, Cluster).
* **Instances sink or float:** *Align to Normal* and *Offset* (Surface, Paint, Cluster); the prototype origin should sit at its base.
* **Some instances vanish when the camera moves:** that is camera optimisation; they are in `invisibleIds`, not deleted. Switch it off to compare.
* **Where did that point go?** Turn on **Debug Views**: *Rejected Points* (red) shows what the Mask, Field Stack, Separation or Avoid Geometry removed.
* **An override does not apply:** the read-out says how many rows named an id that does not exist or a prototype row that is not enabled. Ids come from the stable id (`arraytron_id` primvar, or the *Id* debug colours).
* **Physics shows "stale":** the setup changed since the last cache; press **Simulate & Cache** again.

## Speed

Cooks scale with the instance count and with the geometry used by fields and avoidance. Large meshes used for Slope, Distance, Exclusion or Avoid Geometry are read at every cook (triangles near each point only are tested, but the first pass reads all). Use a simpler proxy prim for those. Paint is limited to 20,000 points per node.

## Reporting a problem

Note the Houdini build, the Arraytron version, the node's read-outs and whether Debug Views show the points. `tests/validate_production.py` (fuzz, round trip, determinism) is the quickest way to check an install.
