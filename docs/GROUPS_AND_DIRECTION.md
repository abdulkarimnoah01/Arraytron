# Group Children prototypes and Keep By Direction (v1.29.0, v1.30.0)

## Prototype Bank: Source Type Group Children (v1.29.0)

One Prototype Bank row can stand for a whole group. Set the row's **Source Type** to **Group Children** and put the group in **Prim Path**: `/World/Group/*` or just `/World/Group`. Every active, drawable child prim becomes its own prototype, in stage order. A name pattern works too: `/World/Group/rock*`, `/World/Group/?ir`, `/World/Group/[ab]*`.

* The row's **Weight, Scale, Scale Random and Rotation Offset apply to each child.** A group row of weight 1 with four children next to a normal row of weight 4 gives the mix 4 : 1 : 1 : 1 : 1, as if you had typed five rows. Every Selection Mode works.
* Not instanced: children that are not drawable (materials), inactive, or deeper than one level; a child that holds this node's Output Prim is skipped.
* **Resolved Prototypes** lists every child. The same prim in two rows is refused, as before.
* A Group Children row has no LOD / Proxy prims of its own (they are ignored and the LOD generator skips it). A Biome Prototype Mix, Instance Place and an Override that name the row take its first child.
* How it works: `resolve()` expands the row into one entry per child, all with the row number; the Python SOP PROTO_EXPAND writes the row of every prototype into the detail array `pe_row`, and the prototype assignment (`src/vex_v1290/prototype_assignment.vfl`) walks that array. Without a group row nothing changes.

## Surface mode: Keep By Direction (v1.30.0)

Like Group Create > Keep By Normals: scatter only on the triangles that face a direction. In the Surface settings turn on **Keep By Direction**:

* **Direction From**: **Vector** (a fixed direction, default 0 1 0 = the tops) or **Light Prim** (the way towards a light in the stream). A Distant Light gives one direction (it shines along its -Z axis, so the way towards it is its +Z axis); a Sphere / Disk / Rect / Cylinder light gives, for every triangle, the direction to the light's position; a Dome light has no direction and is refused. The light is read at the default time.
* **Spread Angle** (default 45): how far a triangle normal may turn from the direction and still be kept (the half angle of the cone). **Soft Edge**: 0 is a hard cut; above 0 the density is full up to Spread x (1 - Soft Edge) and fades smoothly to nothing at the Spread Angle. **Include Opposite Direction** also keeps the faces that point the other way.
* The **Count stays exact** (the points go on the kept triangles; raising the Count adds points and moves none), **By Density counts the kept area**, and the slope limits still apply. Note the default Slope Max of 90 degrees leaves out downward faces whatever the direction; raise it to 180 for undersides.
* The Surface read-out says how many triangles were kept. Not done: a viewport preview of the kept triangles. Face normals decide (not the smoothed ones).
