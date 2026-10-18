# Physics Settle, explained for an artist

**What it does, in one sentence:** instead of placing stones by hand or hoping a random scatter looks natural, you *drop* them and let Houdini's physics pile them up the way real stones would, then Arraytron freezes the result and uses it like any other instancer.

## The idea

Think of three steps:

1. **Spawn.** Arraytron makes the stones exactly as it always did (Area, Line, Grid... with your Randomize and your Prototype Bank). With Physics Settle on, it also lifts them into the air and gently separates them so none starts inside another. That cloud of stones hovering above the floor is the *spawn*. You can see it in the viewport before you simulate: it is your "preview".
2. **Simulate.** You press **Simulate & Cache**. Houdini lets the stones fall, bounce a little, tumble, and settle on the ground, on the colliders you named, and on each other. It stops by itself once nearly everything has stopped moving.
3. **Freeze.** The final position and rotation of every stone are saved to a file (the *cache*). From now on the node just reads that file: no simulation happens while you work, scrub the timeline, or render. If you change something that affects the pile, the old pile stays on screen marked **STALE** until you simulate again.

The stones are not "approximately" colliding: every stone gets a collision shape built from your real stone model (its convex hull, at the size the stone actually has), so they rest against each other correctly.

## Your first pile in five minutes

1. Make a stone prototype and an **Area** distribution (Area Size = the spill zone, Count = how many stones). Add rotation and scale randomness in **Randomize**.
2. Open the **Physics** tab and turn on **Physics Settle**. Look at the viewport: the stones are now floating in a stacked cloud, with two outlines: **Ground** (where the floor is) and **Drop** (where the lowest stones start).
3. If there is a floor or a container in your scene, type its prim path in **Collider Prims** (for example `/World/Box`). The built-in **Ground Plane** is on by default at height 0.
4. Press **Simulate & Cache**. A progress bar runs; Cancel stops it without saving anything.
5. Read the **Status** line. "came to rest" means you are done. "NOT at rest" means the time ran out: raise **Maximum Sim Time** and simulate again.

## What to turn when (cheat sheet)

| You want | Turn |
| --- | --- |
| A tighter, calmer pile | **Air Drag** up (it slows the fall like air). Default 5 is already calm; 0 is a violent, scattering pour |
| Stones to roll and slide more | **Friction** down |
| Stones to stay put on slopes and lock together | **Friction** up (0.9 is gravel-like) |
| A bouncier drop | **Bounce** up (gravel is dead: 0.1) |
| A pile that is taller or more heaped | fewer/smaller **Area** (stones fall into a smaller spot) and more **Count** |
| Stones to land more gently | lower **Drop Height** (the spawn cloud is lower, so the fall is shorter) |
| Different luck, same settings | **Seed** (it changes which stones end up on top) |
| It did not finish | **Maximum Sim Time** up |
| Faster, rougher preview while blocking in | **Collision Quality = Draft** |
| Final look for detailed stones | **Standard** (or **High** if neighbours still poke into each other) |

## Things that surprise people

* **"Why is the pile STALE?"** You changed a setting after simulating. Press Simulate & Cache again. Change it back and the old result is valid again, no new simulation needed.
* **"Why did it take two minutes?"** Cost grows with the number of stones: roughly 200 stones take seconds, 1,500 take a few minutes. Block in with fewer stones or Draft quality, then do the final.
* **"The stones went through my floor / box."** The floor must be a mesh or a cube/sphere/cylinder prim in the stream *above* the Arraytron node, and its path must match **Collider Prims**. A pattern that matches nothing is not an error, so double-check the path.
* **"The pile does not move when I move the node's Bounds Transform."** The pile is simulated in world space (so it can meet your world floor). Moving it means simulating again, or put a Transform LOP after the Arraytron node to move the finished pile.
* **Scale is in meters.** Gravity 9.8 and stone sizes assume the scene is in meters. A scene in centimetres needs a gravity of 980.
* **Send the cache with the scene.** The pile lives in a folder next to your HIP (`arraytron_cache`). Without it the node shows the unsettled spawn. Turn on **Error If Not Simulated** for farm or hand-off scenes so a missing cache can never render silently.
* **A concave stone (a bowl, a ring) rests on its convex hull**, like it were wrapped in cling film. Use convex stones, or build a hollow shape from several convex pieces.

## The two demos

* **Railway ballast** (`Arraytron_v0.5.2_physics_railway_demo.hip`): 1,100 stones of one model poured onto a bed between concrete sleepers and two rails. The sleepers and rails are named in Collider Prims, so stones land on top of them and lean against them. About 30 seconds to simulate.
* **Stones in a box** (`Arraytron_v0.5.2_physics_box_demo.hip`): 1,500 stones poured into an open wooden box (floor and four walls are the colliders). The spawn is a small Area above the box, so the stones fall in, pile up, and the walls keep them in. About three minutes to simulate.

Open either one, look at the Physics Settle folder, and try changing **Friction** or **Air Drag**: the old pile turns STALE; press Simulate & Cache to see the new one.

## Related: stop instances overlapping *without* physics

If you only need a tidy scatter (no falling, no piles), the **Spacing** tab (No Overlap) removes or pushes apart instances whose bounding spheres overlap, and **Spacing** tweaks how much room they keep. Physics Settle is for piles; No Overlap is for layouts.
