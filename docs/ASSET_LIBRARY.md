# Asset Library (v1.18.0)

A **local catalogue of USD assets with your own categories**, in the Arraytron Parameters pane under the Mode Palette (the section **ASSET LIBRARY**, collapsed until you open it). Fill it once (from the Solaris Asset Catalog, from USD files or a folder), organise it in categories such as Trees, Plants, Rocks, Props, then put an asset into the Prototype Bank of any Arraytron node with one click.

## Using it

* **Open** the section with the ASSET LIBRARY bar (the number is the assets in the library). A **category** dropdown (All, your categories, Uncategorized) with **+** (new category), **Rename** and **Delete** next to it, a **search** box (words of the name, the tags or the file name), a grid of thumbnails with the names.
* **Import:** **Asset Catalog...** lists the USD assets of the Solaris Asset Catalog (the Asset Gallery) with their thumbnails and tags: select some (Ctrl / Shift), choose the category, Import. **USD Files...** adds files, **Folder...** every USD file under a folder. You can also **drag USD files** from the file browser onto the grid. The category selected at the moment is where files land (the Asset Catalog picker asks). The same file and prim is never added twice.
* **Use:** select one or more assets and press **Add to Bank**, or **double-click** an asset. Each becomes a **USD File** row at the end of the Prototype Bank (the file and the file's default prim); the Prototype Bank is the normal one, so weights, scale, LOD and everything else work as for any prototype. If the bank only holds the untouched default row, that row is replaced. One undo step per asset.
* **Edit** (right-click an asset): move to a category, rename, tags, show in the file browser, remove from the library (the USD file is never deleted). Deleting a category keeps its assets: they move to **Uncategorized**.
* **Thumbnails:** assets from the Asset Catalog keep the catalogue's thumbnail. For a USD file without one the panel draws a small software render of its meshes, cubes, spheres, cylinders, cones and capsules (flat shaded, three-quarter view), once, into the library's `thumbs` folder; a file it cannot draw keeps a coloured tile with the first letter.

## Where it is stored

One JSON file per user, shared by every Houdini version and every project: `Documents/Arraytron/library/library.json` (the thumbnails in `thumbs/` next to it). Set the environment variable **`ARRAYTRON_LIBRARY`** to use another folder (a shared network library, a per-project one). The file is written atomically; a file that cannot be read is kept as `library.json.broken` and a new library starts, so it never blocks the panel. An entry: id, name, category, USD file, prim, tags, thumbnail, source, date.

## How it is built

The logic (categories, assets, search, the file, importing, Add to Bank) is plain Python in `src/arraytron_library.py`, part of the HDA's PythonModule (`hdaModule()` functions: `load_library`, `save_library`, `add_asset`, `query_assets`, `import_files`, `import_gallery`, `add_to_bank`, ...), so scripts and tests can use it without the interface. The Qt section (`LibraryPanel`, the Asset Catalog picker, the thumbnail renderer) is `src/arraytron_libpanel.py`, embedded in the HDA with the Mode Palette's panel (section `ModePalette.py`, see `docs/MODE_PALETTE.md`). It needs the interface: with `ARRAYTRON_NO_PARM_PANEL=1` or in hython the library functions still work, the panel is not shown.

## Evidence and limits

`tests/validate_library.py` (6 groups, 4 mutations): categories (defaults, add, rename, delete, order), assets (dedupe, search by name and tag, edit, nothing lost with a category), the file (a round trip, an atomic save, a broken file kept aside, `ARRAYTRON_LIBRARY`), importing (USD files, a folder, an Asset Catalog data source with thumbnails and non-USD items skipped, the thumbnail removed with the asset), **Add to Bank on a real node** (the default row replaced, new rows, a chosen row, the prototypes really come from the two files, an edited row kept), the panel code and the thumbnail renderer, the previous release unchanged.

**Seen in the GUI (Houdini 22, screenshots):** the section under the palette, the thumbnails, a category switch, Add to Bank. **Not yet verified:** the **Asset Catalog...** picker against a real Asset Catalog (the catalog was empty; it is tested with a stand-in data source), drag and drop from the file browser, the right-click menu, Houdini 20.5 / 21 with the panel (the same code, PySide2 in 20.5), a very large library (the grid is not paged).
