# Edit tab: select and change instances by hand (v1.35.0)

The **Edit** tab (before Optimize) is the Edit mode of Arraytron Stamp for the generated instances: select instances in the viewport and move, rotate, scale or delete them, live.

## Use it

1. Press **Edit Instances**. The viewport tool starts (the HUD panel lists the keys).
2. **Click** an instance to select it, **Shift+click** adds or removes one, **drag on nothing** draws a box and selects everything inside it. Selected instances get yellow boxes (the box of their prototype, turned and scaled like the instance); the instance under the mouse gets a grey box.
3. Drag Houdini's **edit handle** (it sits at the centre of the selection): move, rotate and scale the selection together. The instances follow while you drag (**Live While Dragging**; off: only the boxes follow and the instances move when you release). One drag is one undo step.
4. **Del** deletes the selection, **A** selects all, **I** inverts, **N** clears. **Esc** or **Enter** finishes.

Buttons on the tab: Select All, Select None, Invert Selection, Delete Selected, Reset Selected (the selected instances come back as generated), Restore Deleted (deleted instances come back, their moves kept), Reset All Edits. **Apply Edits** off shows the scatter as generated and keeps the edits.

## How it works

* The edits are one hidden text parameter, `edit_data`: one line per edited instance, `id  move x y z  rotation quaternion x y z w  scale x y z  on` (on 0 = deleted), like the stamps of Arraytron Stamp. A drag rewrites this one parameter (at most 30 times a second), so it is fast also with hundreds of selected instances; the Instance Overrides list (Debugging tab) is not used.
* The **EDITS** stage applies the store with numpy after the Override Database and before Mirror and Grow. Move is added to the position, the rotation turns the orientation (world space, also under a Bounds Transform), the scales multiply.
* Edits are keyed on the stable instance id: they stay on the same instances when the count, the seed of the variation or other settings change; ids that no longer exist are ignored.
* The selection is the hidden `edit_ids` parameter (not an undo step). The handle works in world space about the centre of the selection.

Code: `src/arraytron_edit.py` (functions, appended to the PythonModule), the Edit mode of `src/arraytron_paint_state.py` (viewer state). Test: `tests/validate_edit.py`. Demo: `Arraytron_v1.35.0_edit_demo.hip` (in the all-demos scene).

Not verified by a test: the mouse itself (clicks, box drag and handle drag are driven by Houdini's viewer; the functions they call are tested).
