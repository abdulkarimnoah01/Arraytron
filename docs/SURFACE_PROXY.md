# Big surfaces: the surface cache, Reduced Proxy and the ghost (v1.31.0)

## Why
In a large scene the node took many seconds every time it was selected ("Evaluating python" in the status bar) and every recook was slow. The cause, measured on a set with a scanned mountain of **8 380 418 triangles** in Surface mode (Houdini 20.5.445):

| | before (1.30.1) | now (1.31.0) |
| --- | --- | --- |
| Surface text (read when the node is selected) | 9 s | 0.2 s |
| First cook | 27 s | 13 s |
| Recook (new Seed, Density, Slope ...) | 17 s | 0.5 s |
| Recook with Reduced Proxy (150 000 triangles) | - | 0.3 s |

Every cook, and the **Surface** text of the Layout tab, read every triangle of the mesh again, built the normals and the vertex normals (`np.add.at`: 6 s on 8 million triangles) and threw it all away.

## What changed
* **The surface is read once and kept.** The triangles, areas and normals of the Surface Prim stay in memory (read only) until the incoming stage cooks again or the prim changes. Seed, Density, Count, Slope, Keep By Direction, Offset and the other settings never read the mesh again. Everything that reads a surface (Surface, Biome, Cluster, Paint, Fields, Mask Paint, Place) goes through the same cache. At most about 3 GB are kept (the oldest entry goes first).
* **The vertex normals are 20 times faster** (`np.bincount` instead of `np.add.at`), so the first read is faster too.
* **The Surface text no longer reads a big surface.** Selecting the node shows "About N triangles. The area and the number of points appear once the node has cooked" for a surface of more than 200 000 triangles that is not in the cache yet; after the first cook the full text (triangles, area, points) comes from the cache in a fraction of a second. A smaller surface is read for the text as before.

## Scatter On Reduced Proxy (Surface mode)
For a very dense surface you can scatter on a poly reduced copy of it:

* **Scatter On Reduced Proxy** (off by default). The copy is made once (vertex clustering on a grid, numpy only: 8 million triangles in about 3 seconds), kept, and made again only when the surface or the target changes.
* **Target Triangles** (default 100 000): about this many triangles (the result lands within 40 percent of it). More follows the surface more closely.
* **Ghost Proxy** (menu: Hidden, Viewport Only (default), Viewport And Render): the reduced surface drawn as a translucent mesh (`<output>_View/GhostProxy`, next to the instancer), so you see what the points are scattered on. Viewport Only is a guide and never renders; Hidden draws nothing in the viewport or the render; Viewport And Render gives the mesh the default purpose so Karma renders it too.
* **The amount of points follows the area of the original surface**, so a By Density amount does not change with the reduction; By Count stays exact. Keep By Direction and the slope limits see the proxy's (smoother) normals.
* **The points lie within about one cell of the real surface** (the vertices of the copy are the means of the merged vertices). In the tests on a smooth hill an 8 000 triangle proxy of a 97 000 triangle surface keeps the points within 0.15 units on average (the hill is 6 units high). That is right for terrain and for props that may sit slightly off the skin; raise Target Triangles when they must sit exactly on it.

## The Scattered counter
The Layout tab shows **Scattered** under the Distribution Mode (read only): how many instances the node makes, how many points were generated before Mask, Falloff, Thin, Separation or Avoid removed some, and how many instances use each prototype ("1,240 instances (1,500 generated, 260 removed by ...)", then "Fir 700,  Rock 540"). It never cooks the node itself: while the node has changed and not cooked yet it shows the last count marked old.

## Point Limit and the counter
Surface mode makes at most **Point Limit** points (default 10 000, the old fixed cap; raise it up to 5 000 000), whatever Count or Density ask for. A Density of 1000 on a big surface asks for billions, so the node used to stop silently at 10 000. The **Scattered** counter now says so: "10,000 instances - LIMITED: the settings ask for 28,030,000,000, the Point Limit is 10,000". A million instances cook in about a second (the viewport is the limit).

## Compared with the native Instancer (v1.31.1)
Set `RnD_environment_kaspixjackie_setdress_v021.hip`, Houdini 20.5.445, the 8.38 million triangle mountain. The native Instancer LOP scatters with its internal Scatter and Align SOP; Arraytron's Surface mode with By Count. Counts: Arraytron is exact (1 000, 10 068, 100 000, 1 000 000); the native node 1 000, 10 068, 99 996, 999 991. Cook times, first / recook with a new seed:

| Instances | Native Instancer | Arraytron |
| --- | --- | --- |
| 10 068 | 5.7 s / 0.6 s | 0.3 s / 0.3 s |
| 100 000 | 7.0 s / 2.1 s | 0.6 s / 0.6 s |
| 1 000 000 | 9.1 s / 4.0 s | 3.9 s / 4.0 s |

The first cook of the first size also reads the surface once (about 4 s). Before v1.31.1 the million-instance recook was 6.3 s (3.1 s Surface scatter, 1.8 s prototype paths in the 20.5 / 21 build); it is 4.0 s now.

## Place is retired
The Instance Place mode is removed from the Distribution Mode palette and menu (the Arraytron Stamp node does that job). The menu keeps the slot, labelled "Place (retired)", so **Biome keeps mode 10** and scenes saved with the Place mode still load and cook.

## Tested
`tests/validate_surfproxy.py` (9 groups; the mutations `sp_reduce`, `sp_cache`, `sp_stale`, `sp_area`, `sp_info`, `sp_count`, `sp_limit` make it fail) in Houdini 22 and 20.5: the reduction (target, area, winding, distance to the surface), the cache (one read, read-only, Seed / Density / Slope / proxy never read again, a moved stage or another prim does), the Surface text (no read for a big surface), the proxy (same amount, near the surface, stable, By Count exact, Keep By Direction, the text), the ghost (a translucent guide, off with the toggle), Place retired (menu, palette, Biome at 10, mode 9 loads), the contract and the previous release unchanged with the proxy off. Demo: `tools/build_demo_surfproxy_v1310.py` (`dist/Arraytron_v1.31.0_surfproxy_demo.hip`, a 770 000 triangle mountain scattered on itself and on a proxy).

## Not verified
GUI: whether selecting the node is as fast in the real Houdini session as in hython (the numbers above are hython on the set's file), how the ghost looks, and the Place mode's absence in the palette. The cache lives in the Houdini process (it is not saved in the hip). The first cook after loading a scene still reads the surface once (13 s for 8 million triangles); the proxy makes later changes fast but does not shorten that first read.
