# Prototype sockets (Arraytron v1.37.0, Arraytron Stamp 0.12.0)

Inputs 2, 3 and 4 of both nodes are **prototype sockets**. Wire models into them the way you wire anything in Solaris (a Reference, an Asset Reference, a SOP Create, a Merge of many, a whole node tree), then click **Import Prototype Inputs**:

* Arraytron: Scatter tab, above the Prototype Bank.
* Arraytron Stamp: Brush > Asset, above the Prototype Bank.
* From Python: `node.hdaModule().proto_import(node)` (returns what it did), `proto_scan(node)` (only looks).

## What one click does

1. **Reads** the stage each socket delivers (so a merge, a switch or a long node tree needs no special handling) and lists every prototype in it.
2. **Prototype Bank:** every prototype becomes a row: Source Type Input Connection, Input 2 / 3 / 4, Prim Path set to the prototype. The row stays live (change the network and the cook follows). Weight, Scale, Scale Random and Rotation Offset are on the row at their defaults, ready to edit. Arraytron Stamp's cards show the new rows at once.
3. **Asset Library:** every prototype becomes an asset in the category **Imported**. A prototype that is a plain reference or payload to an existing USD file adds that file itself (and the prim the reference points at). Anything else (a procedural prim, a SOP Create, a prim with several arcs) is written once as a standalone `.usda` in `<library>/prototypes/<name>_<hash>.usda`, flattened, with the stage's up axis and units; the same content is the same file. The library panel draws its thumbnails like for any asset (reopen the Asset Library section to see the new ones).

## Which prims are prototypes

* Each **top-level prim** of a socket is one prototype; the rule of an Input Connection row without a Prim Path applies (down single-child chains until a component, an assembly or a gprim, or a group with several children).
* A top-level **container of kind group or assembly** gives its children instead (so one reference to a kit that groups its parts gives one prototype per part). To scatter the children of a plain group that has no kind, use a Group Children row.
* Prims with nothing drawable (materials, lights, cameras) and inactive prims are skipped.

## Clicking again, and the toggles

* A prototype that is already a row (the same prim) is kept as it is: your Weight, Scale and the rest stay. Only new prototypes are added, after the rows that are there. A blank row (the default row, or an Input Connection with no Prim Path) is reused first.
* **Replace The Bank:** rebuild the bank from the inputs only; the rows that were there are removed.
* **Also Add To The Asset Library** (on by default): switch it off to fill only the bank.
* One undo step. With nothing wired into the sockets, or nothing drawable in them, the button says so and changes nothing.

## Limits

* The standalone file of a procedural prototype holds the prim and what is below it; materials outside that prim are not copied (a material inside the prim is).
* The Asset Library file of the user (`Documents/Arraytron/library`, or `ARRAYTRON_LIBRARY`) is shared by both tools.

Tests: `hython tests/validate_protoimport.py` (33 checks in both HDAs).
