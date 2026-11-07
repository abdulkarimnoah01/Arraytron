
# ---- Houdini Paint mask (src/arraytron_hpaint.py): paint the Mask with Houdini's own Attribute Paint brush (heat map, every operation, symmetry, pressure ...), then scatter. Not realtime.
# Paint Mask With Houdini Brush builds a helper geometry object in /obj (<node name>_mask_paint): the scattering surface of the node, subdivided into a dense mesh (Paint Detail points along its longer side) with a
# float point attribute mask, followed by an Attribute Paint SOP, and enters the Attribute Paint viewport state. You paint there with everything the Houdini brush has. Finish And Scatter reads the painted
# attribute back: the points are splatted top-down into a grid over X and Z (the same space as the other mask sources), the empty cells are filled from their neighbours, and the grid is stored in the hidden
# parameter mask_hpaint_data (zlib, 16 bit). Mask Source Houdini Paint reads that grid like the painted mask (Unpainted Value outside it, Map Feather blurs it), so Invert, Low / High, Gamma, the Remap Curve and the
# Output Range work as for every source. The helper is kept, so the next Paint Mask With Houdini Brush continues the same strokes.
import zlib, base64
HPAINT_MAX_TRIS = 200000
HPAINT_HELPER_SUFFIX = '_mask_paint'
_HPAINT_DECODED = {}

def hpaint_weld(P, T):
    """Merge points that lie at the same place (the triangles of several meshes come with their own points) so a subdivided surface has shared points and Attribute Paint leaves no seams."""
    P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
    T = np.asarray(T, dtype=np.int64).reshape(-1, 3)
    key = np.round(P * 1e5).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = np.asarray(inv).reshape(-1)
    T = inv[T]
    T = T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 2] != T[:, 0])]
    return P[first], T

def hpaint_dense(P, T, target, max_tris=HPAINT_MAX_TRIS):
    """The mesh split uniformly in fours (every triangle into four, shared edge midpoints) until its longest edge is at most `target` or another round would pass max_tris triangles. Returns (P, T, longest edge)."""
    P = np.asarray(P, dtype=np.float64)
    T = np.asarray(T, dtype=np.int64)
    for _ in range(10):
        e = np.concatenate([P[T[:, 0]] - P[T[:, 1]], P[T[:, 1]] - P[T[:, 2]], P[T[:, 2]] - P[T[:, 0]]])
        longest = float(np.linalg.norm(e, axis=1).max())
        if longest <= target or len(T) * 4 > max_tris:
            return P, T, longest
        n = len(T)
        edges = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1)
        uniq, inv = np.unique(edges, axis=0, return_inverse=True)
        inv = np.asarray(inv).reshape(3, n) + len(P)
        P = np.vstack([P, 0.5 * (P[uniq[:, 0]] + P[uniq[:, 1]])])
        a, b, c = T[:, 0], T[:, 1], T[:, 2]
        m01, m12, m20 = inv[0], inv[1], inv[2]
        T = np.concatenate([np.stack([a, m01, m20], axis=1), np.stack([b, m12, m01], axis=1), np.stack([c, m20, m12], axis=1), np.stack([m01, m12, m20], axis=1)])
    return P, T, longest

def hpaint_grid(P, mask, base, res):
    """The painted points as a map: (grid [z, x], spec (x0, z0, cell, nx, nz)). The points are averaged into the cells they fall in (looking from above), the cells without a point take the mean of their neighbours
    (up to six rounds) and then `base`. The cell is the longer side over res - 1, or larger when the points are further apart than that."""
    P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
    mask = np.asarray(mask, dtype=np.float64).reshape(-1)
    lo = P[:, [0, 2]].min(axis=0)
    hi = P[:, [0, 2]].max(axis=0)
    ext = np.maximum(hi - lo, 1e-9)
    spacing = float(np.sqrt(ext[0] * ext[1] / max(len(P), 1)))
    cell = max(float(ext.max()) / (max(int(res), 8) - 1), 1.2 * spacing)
    nx = int(np.ceil(ext[0] / cell)) + 1
    nz = int(np.ceil(ext[1] / cell)) + 1
    ix = np.clip(np.round((P[:, 0] - lo[0]) / cell).astype(np.int64), 0, nx - 1)
    iz = np.clip(np.round((P[:, 2] - lo[1]) / cell).astype(np.int64), 0, nz - 1)
    total = np.zeros((nz, nx))
    count = np.zeros((nz, nx))
    np.add.at(total, (iz, ix), mask)
    np.add.at(count, (iz, ix), 1.0)
    have = count > 0
    grid = np.where(have, total / np.maximum(count, 1.0), 0.0)
    for _ in range(6):
        if have.all():
            break
        pad_v = np.pad(np.where(have, grid, 0.0), 1)
        pad_h = np.pad(have.astype(np.float64), 1)
        s = sum(pad_v[1 + dz:1 + dz + nz, 1 + dx:1 + dx + nx] for dz in (-1, 0, 1) for dx in (-1, 0, 1))
        c = sum(pad_h[1 + dz:1 + dz + nz, 1 + dx:1 + dx + nx] for dz in (-1, 0, 1) for dx in (-1, 0, 1))
        fill = (~have) & (c > 0)
        grid = np.where(fill, s / np.maximum(c, 1.0), grid)
        have = have | fill
    grid = np.where(have, grid, float(base))
    return np.clip(grid, 0.0, 1.0), (float(lo[0]), float(lo[1]), float(cell), int(nx), int(nz))

def hpaint_encode(grid, spec):
    """The map as text: JSON with the grid as zlib-compressed 16 bit values (base64)."""
    q = np.round(np.clip(np.asarray(grid, dtype=np.float64), 0.0, 1.0) * 65535.0).astype('<u2')
    x0, z0, cell, nx, nz = spec
    return json.dumps({'v': 1, 'x0': round(x0, 6), 'z0': round(z0, 6), 'cell': round(cell, 8), 'nx': int(nx), 'nz': int(nz), 'data': base64.b64encode(zlib.compress(q.tobytes(), 6)).decode('ascii')}, separators=(',', ':'))

def hpaint_decode(text):
    """(grid [z, x], spec) of the mask_hpaint_data text, or None for an empty text; a text that is not a Houdini paint map is an error."""
    text = (text or '').strip()
    if not text:
        return None
    hit = _HPAINT_DECODED.get(text)
    if hit is not None:
        return hit
    try:
        d = json.loads(text)
        nx, nz = int(d['nx']), int(d['nz'])
        q = np.frombuffer(zlib.decompress(base64.b64decode(d['data'])), dtype='<u2')
        grid = q.astype(np.float64).reshape(nz, nx) / 65535.0
        spec = (float(d['x0']), float(d['z0']), float(d['cell']), nx, nz)
    except (ValueError, KeyError, TypeError, zlib.error) as error:
        raise ValueError('The Houdini paint cannot be read (%s). Clear it with Clear Houdini Paint.' % error)
    _HPAINT_DECODED.clear()
    _HPAINT_DECODED[text] = (grid, spec)
    return grid, spec

def hpaint_values(text, xz, base=0.0, blur=0.0):
    """The Houdini paint map read at (n, 2) points of (x, z); `base` where nothing was baked or beyond the map."""
    xz = np.asarray(xz, dtype=np.float64).reshape(-1, 2)
    base = min(max(float(base), 0.0), 1.0)
    got = hpaint_decode(text)
    if got is None:
        return np.full(len(xz), base)
    grid, spec = got
    if blur > 0.0:
        grid = maskpaint_blur(grid, blur / spec[2])
    return maskpaint_sample(grid, spec, xz, base)

# ---------------------------------------------------------------- Houdini side
HPAINT_SOP = ('asset=hou.node(hou.pwd().parent().userData("arraytron_node") or "")\n'
              'if asset is None:raise hou.NodeError("The Arraytron node of this paint helper is gone: delete the helper.")\n'
              'asset.hdaModule().sop_hpaint_surface(hou.pwd().geometry(),asset)\n')

def hpaint_has_surface(asset):
    """True when the brush has a real surface (the Paint Surface prim, or the surface of the Distribution Mode) and not the flat ground plane."""
    mode = asset.evalParm('mode')
    return bool(asset.evalParm('mask_paint_prim').strip()) or (mode == 5 and asset.parm('surface_prim') is not None) or mode == 6 or (mode == 10 and asset.parm('biome_prim') is not None)

def hpaint_surface(asset):
    """The triangles to paint on: the surface of maskpaint_surface, or a flat square of Plane Size around the origin when there is none."""
    if hpaint_has_surface(asset):
        return maskpaint_surface(asset)
    return plane_surface(max(asset.evalParm('mask_hpaint_plane'), 1e-3) * 0.5, 0.0)

def sop_hpaint_surface(geo, asset):
    """The Python SOP of the helper: the dense surface with the point attribute mask at the Unpainted Value."""
    P, T, area, normals, vn = hpaint_surface(asset)
    P, T = hpaint_weld(P, T)
    ext = max(float(np.ptp(P[:, 0])), float(np.ptp(P[:, 2])), 1e-6)
    P, T, longest = hpaint_dense(P, T, ext / max(asset.evalParm('mask_hpaint_detail'), 8))
    geo.clear()
    geo.addAttrib(hou.attribType.Point, 'mask', float(asset.evalParm('mask_paint_base')))
    pts = geo.createPoints([tuple(p) for p in P.tolist()])
    for t in T.tolist():
        poly = geo.createPolygon()
        for i in t:
            poly.addVertex(pts[i])

def hpaint_helper_path(asset):
    return asset.userData('arraytron_hpaint') or ''

def hpaint_helper(asset, create=True):
    """The paint helper of the node (a geo object in /obj), made when it does not exist: Python SOP surface -> Attribute Paint (attribute mask, Foreground / Background / radius / soft edge / opacity from the
    brush settings of the node) -> OUT. Returns the geo object, or None when it does not exist and create is False."""
    path = hpaint_helper_path(asset)
    geo = hou.node(path) if path else None
    if geo is not None:
        return geo
    if not create:
        return None
    parent = hou.node('/obj')
    geo = parent.createNode('geo', asset.name() + HPAINT_HELPER_SUFFIX)
    geo.setUserData('arraytron_node', asset.path())
    for child in geo.children():
        child.destroy()
    surface = geo.createNode('python', 'SURFACE')
    surface.parm('python').set(HPAINT_SOP)
    paint = geo.createNode('attribpaint', 'PAINT')
    paint.setInput(0, surface)
    paint.parm('stroke_attrib').set('mask')
    paint.parm('fgfloat').set(asset.evalParm('mask_brush_value'))
    if asset.parm('mask_brush_bg') is not None:
        paint.parm('bgfloat').set(asset.evalParm('mask_brush_bg'))
    paint.parm('stroke_radius').set(asset.evalParm('mask_brush_radius'))
    paint.parm('stroke_softedge').set(asset.evalParm('mask_brush_feather'))
    paint.parm('stroke_opacity').set(asset.evalParm('mask_brush_strength'))
    out = geo.createNode('null', 'OUT')
    out.setInput(0, paint)
    paint.setDisplayFlag(True)                                                                # the brush paints the displayed Attribute Paint node; OUT is where the result is read
    paint.setRenderFlag(True)
    geo.layoutChildren()
    asset.setUserData('arraytron_hpaint', geo.path())
    return geo

def hpaint_start(asset):
    """Paint Mask With Houdini Brush button: Mask Source Houdini Paint, the helper (made or reused), and Houdini's Attribute Paint state in the viewport."""
    if asset.evalParm('mask_source') != 5:
        asset.parm('mask_source').set(5)
    geo = hpaint_helper(asset)
    geo.node('SURFACE').cook(force=True)
    paint = geo.node('PAINT')
    if hou.isUIAvailable():
        viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if viewer is None:
            raise hou.NodeError('Open a Scene Viewer pane to paint the mask.')
        viewer.setPwd(geo)
        paint.setCurrent(True, clear_all_selected=True)
        viewer.setCurrentState(paint.type().defaultState())
    return geo

def hpaint_bake(asset, geo=None):
    """Read the painted attribute of the helper (or of a given hou.Geometry) into mask_hpaint_data. Returns the number of points read."""
    if geo is None:
        helper = hpaint_helper(asset, create=False)
        if helper is None:
            raise hou.NodeError('There is no paint to finish: press Paint Mask With Houdini Brush first.')
        geo = helper.node('OUT').geometry()
    if geo is None or geo.findPointAttrib('mask') is None:
        raise hou.NodeError('The paint helper has no mask attribute (is its surface empty?).')
    P = np.array(geo.pointFloatAttribValues('P'), dtype=np.float64).reshape(-1, 3)
    m = np.array(geo.pointFloatAttribValues('mask'), dtype=np.float64)
    if not len(P):
        raise hou.NodeError('The paint helper has no points.')
    grid, spec = hpaint_grid(P, m, asset.evalParm('mask_paint_base'), asset.evalParm('mask_paint_res'))
    with hou.undos.group('Arraytron Houdini paint'):
        asset.parm('mask_hpaint_data').set(hpaint_encode(grid, spec))
        if asset.evalParm('mask_source') != 5:
            asset.parm('mask_source').set(5)
    return len(P)

def hpaint_finish(asset):
    """Finish And Scatter button: bake the painted mask, leave the paint state and show the node again (the scatter follows from the mask)."""
    count = hpaint_bake(asset)
    if hou.isUIAvailable():
        viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if viewer is not None:
            viewer.setCurrentState('select')
            viewer.setPwd(asset.parent())
        asset.setCurrent(True, clear_all_selected=True)
    return count

def hpaint_clear(asset):
    """Clear Houdini Paint button: forget the baked map and remove the paint helper (undoable for the map)."""
    had = bool(asset.evalParm('mask_hpaint_data'))
    helper = hpaint_helper(asset, create=False)
    with hou.undos.group('Arraytron clear Houdini paint'):
        asset.parm('mask_hpaint_data').set('')
    if helper is not None:
        helper.destroy()
    if asset.userData('arraytron_hpaint'):
        asset.destroyUserData('arraytron_hpaint')
    return had

def hpaint_field(asset, P):
    """The Houdini paint mask (0 .. 1, before Invert and the remap) at the points P (n, 3), read in X and Z."""
    try:
        return hpaint_values(asset.evalParm('mask_hpaint_data'), np.asarray(P, dtype=np.float64).reshape(-1, 3)[:, [0, 2]], asset.evalParm('mask_paint_base'), asset.evalParm('mask_paint_blur'))
    except ValueError as error:
        raise hou.NodeError(str(error))

def hpaint_info(asset):
    """Read-only text for the Mask folder when the source is Houdini Paint."""
    try:
        got = hpaint_decode(asset.evalParm('mask_hpaint_data'))
    except ValueError as error:
        return str(error)
    helper = hpaint_helper(asset, create=False)
    if got is None:
        return 'Nothing baked yet. Press Paint Mask With Houdini Brush, paint, then Finish And Scatter.%s' % (' (A paint helper exists: %s.)' % helper.path() if helper is not None else '')
    grid, spec = got
    return 'Houdini paint baked: %d x %d cells of %.3g, mask min %.3g, mean %.3g, max %.3g.%s' % (spec[3], spec[4], spec[2], grid.min(), grid.mean(), grid.max(), ' Helper: %s.' % helper.path() if helper is not None else '')
