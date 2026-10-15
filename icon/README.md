# Arraytron icon

`Arraytron-Clean.svg` is the editable vector master (1024 x 1024 viewBox). It uses a monochrome double-ring seal, an inverted triangle, and sixteen scattered isometric cubes/spheres over a construction lattice. It follows the geometric visual language of the supplied PhiAxis and Control/FBC references.

- `Arraytron-Clean.png`: 2048 x 2048 export, transparent outside the white circular field.
- `Arraytron-Preview.png`: 1024 x 1024 preview on white.

The SVG contains named groups and ordinary vector geometry, with no fonts, external references, or embedded raster images. The circle's white interior is intentional. The HDA release files are separate from these design assets.

Rebuild the vector and PNG exports with Houdini's hython:

```text
hython tools/build_arraytron_icon.py
```

The builder uses Python for SVG authoring and Qt SVG for preview rendering.
