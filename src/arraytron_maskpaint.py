
# ---- Painted mask (src/arraytron_maskpaint.py): paint the Mask with a viewport brush, live (Mask Source: Painted).
# The paint is a list of STAMPS: op, x, y, z (the hit on the surface; y is only for the viewport preview), radius, strength, feather, value, curve. They are kept in the hidden parameter mask_paint_data (JSON).
# At cook time the stamps become a 2D map over the XZ extent of the paint (a grid of at most mask_paint_res cells along the longer side), applied in the order they were painted:
#   op 0 Paint      the map moves towards the brush Value by the stamp weight (an airbrush: a weak brush builds up over several dabs)
#   op 1 Erase      the map moves towards 0
#   op 2 Add        the map rises by the stamp weight x Value (clipped to 1)
#   op 3 Subtract   the map falls by the stamp weight x Value (clipped to 0)
# The stamp weight is the strength x the brush profile: 1 in the hard core of the brush (radius x (1 - feather)), fading to 0 at the rim over the feather zone with the curve (Linear, Smooth, Gaussian).
# Unpainted places hold mask_paint_base. The map can be blurred (mask_paint_blur, scene units) and is then read at the points like any other mask source; Invert, Low / High, Gamma, the Remap Curve and
# the Output Range of the Mask folder shape it (arraytron_mask.py). Points outside the paint get the base value.
import json, hashlib
MASKPAINT_MAX = 100000                 # stamps kept
MASKPAINT_COLUMNS = 9                  # op, x, y, z, radius, strength, feather, value, curve
MASKPAINT_OPS = ('Paint', 'Erase', 'Add', 'Subtract', 'Smooth', 'Multiply', 'Maximum', 'Minimum')       # the operations a stamp can hold (v1.27.0 added the last four)
MASKPAINT_MENU = ('Paint', 'Erase', 'Add', 'Subtract', 'Smooth', 'Multiply', 'Maximum', 'Minimum', 'Paint Background', 'Sample Foreground', 'Sample Background')   # the brush operation menus: the first eight are stamp operations, then Paint Background, then the two samplers
MASKPAINT_CURVES = ('Linear', 'Smooth', 'Gaussian')
_MASKPAINT_CACHE = {}
_MASKPAINT_DECODED = {}

def maskpaint_decode(text):
    """The stamps (n, 9) of the mask_paint_data text; an empty text is no stamps, a text that is not a painted mask is an error."""
    text = (text or '').strip()
    if not text:
        return np.zeros((0, MASKPAINT_COLUMNS))
    hit = _MASKPAINT_DECODED.get(text)
    if hit is not None:
        return hit
    try:
        data = json.loads(text)
        stamps = np.array(data['stamps'], dtype=np.float64).reshape(-1, MASKPAINT_COLUMNS)
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError('The painted mask cannot be read (%s). Clear it with Clear Mask Paint.' % error)
    _MASKPAINT_DECODED.clear()
    _MASKPAINT_DECODED[text] = stamps
    return stamps

def maskpaint_encode(stamps):
    stamps = np.asarray(stamps, dtype=np.float64).reshape(-1, MASKPAINT_COLUMNS)[-MASKPAINT_MAX:]
    if not len(stamps):
        return ''
    rows = [[int(s[0]), round(float(s[1]), 3), round(float(s[2]), 3), round(float(s[3]), 3), round(float(s[4]), 4), round(float(s[5]), 3), round(float(s[6]), 3), round(float(s[7]), 3), int(s[8])] for s in stamps]
    return json.dumps({'v': 1, 'stamps': rows}, separators=(',', ':'))

def maskpaint_add(stamps, op, pos, radius, strength, feather, value, curve):
    """The stamps with one more (a copy) and whether one was added: a stamp that repeats the last one (same operation, radius, feather and value) closer than a fifth of the radius is skipped, so a slow
    drag does not pile up stamps."""
    stamps = np.asarray(stamps, dtype=np.float64).reshape(-1, MASKPAINT_COLUMNS)
    if len(stamps):
        last = stamps[-1]
        if int(last[0]) == int(op) and abs(last[4] - radius) < 1e-9 and abs(last[6] - feather) < 1e-9 and abs(last[7] - value) < 1e-9 and np.hypot(last[1] - pos[0], last[3] - pos[2]) < 0.2 * radius:
            return stamps, False
    new = np.vstack([stamps, [[op, pos[0], pos[1], pos[2], radius, strength, feather, value, curve]]])
    return new[-MASKPAINT_MAX:], True

def maskpaint_profile(t, feather, curve):
    """The brush weight 0..1 at t = distance / radius. 1 up to t = 1 - feather (the hard core), then falling to 0 at t = 1 over the feather zone: Linear, Smooth (smoothstep) or Gaussian (a bell cut
    to exactly 0 at the rim). Feather 0 is a hard disc."""
    t = np.clip(np.asarray(t, dtype=np.float64), 0.0, None)
    feather = min(max(float(feather), 0.0), 1.0)
    u = np.where(t <= 1.0 - feather, 0.0, (t - (1.0 - feather)) / max(feather, 1e-9))
    u = np.clip(u, 0.0, 1.0)
    if int(curve) == 0:
        w = 1.0 - u
    elif int(curve) == 1:
        w = 1.0 - u * u * (3.0 - 2.0 * u)
    else:
        edge = np.exp(-4.5)
        w = (np.exp(-4.5 * u * u) - edge) / (1.0 - edge)
    return np.where(t <= 1.0 + 1e-12, np.clip(w, 0.0, 1.0), 0.0)

def maskpaint_spec(stamps, res, blur=0.0):
    """The grid of the paint: (x0, z0, cell, nx, nz). It covers every stamp (with its radius) plus room for the blur; the cell is the longer side divided by res - 1."""
    stamps = np.asarray(stamps, dtype=np.float64).reshape(-1, MASKPAINT_COLUMNS)
    r = stamps[:, 4]
    lo = np.array([(stamps[:, 1] - r).min(), (stamps[:, 3] - r).min()])
    hi = np.array([(stamps[:, 1] + r).max(), (stamps[:, 3] + r).max()])
    pad = 4.0 * max(float(blur), 0.0) + 0.01 * float((hi - lo).max()) + 1e-6
    lo = lo - pad
    hi = hi + pad
    res = int(max(res, 8))
    cell = float((hi - lo).max()) / (res - 1)
    nx = int(np.ceil((hi[0] - lo[0]) / cell)) + 1
    nz = int(np.ceil((hi[1] - lo[1]) / cell)) + 1
    return (float(lo[0]), float(lo[1]), cell, nx, nz)

def maskpaint_blur(grid, sigma):
    """A Gaussian blur of the map, sigma in cells (an FFT with the edge values repeated, so a map that is flat at its border stays flat)."""
    if sigma < 0.25:
        return grid
    nz, nx = grid.shape
    pad = int(np.ceil(4.0 * sigma))
    g = np.pad(grid, pad, mode='edge')
    fy = np.fft.fftfreq(g.shape[0])
    fx = np.fft.rfftfreq(g.shape[1])
    kernel = np.exp(-2.0 * np.pi ** 2 * sigma ** 2 * (fy[:, None] ** 2 + fx[None, :] ** 2))
    out = np.fft.irfft2(np.fft.rfft2(g) * kernel, s=g.shape)[pad:pad + nz, pad:pad + nx]
    return np.clip(out, 0.0, 1.0)

def _smooth_window(grid, iz0, iz1, ix0, ix1, sigma):
    """The blur (a Gaussian of sigma cells, edge values repeated) of the block grid[iz0:iz1 + 1, ix0:ix1 + 1], looking a little beyond the block so its border blends with the map around it."""
    k = int(np.ceil(2.0 * sigma))
    pz0, pz1 = max(0, iz0 - k), min(grid.shape[0] - 1, iz1 + k)
    px0, px1 = max(0, ix0 - k), min(grid.shape[1] - 1, ix1 + k)
    win = grid[pz0:pz1 + 1, px0:px1 + 1]
    ker = np.exp(-0.5 * (np.arange(-k, k + 1) / sigma) ** 2)
    ker /= ker.sum()
    g = np.pad(win, k, mode='edge')
    h, w = win.shape
    t = sum(ker[i] * g[:, i:i + w] for i in range(2 * k + 1))
    o = sum(ker[j] * t[j:j + h, :] for j in range(2 * k + 1))
    return o[iz0 - pz0:iz0 - pz0 + (iz1 - iz0 + 1), ix0 - px0:ix0 - px0 + (ix1 - ix0 + 1)]

def maskpaint_raster(stamps, spec, base=0.0, blur=0.0):
    """The map as a (nz, nx) array [z, x] with values in 0 .. 1: the stamps applied in the order painted on a field of `base`, then blurred by `blur` scene units."""
    x0, z0, cell, nx, nz = spec
    grid = np.full((nz, nx), min(max(float(base), 0.0), 1.0))
    for s in np.asarray(stamps, dtype=np.float64).reshape(-1, MASKPAINT_COLUMNS):
        op, sx, sz, r, strength, feather, value, curve = int(s[0]), s[1], s[3], max(s[4], 1e-9), s[5], s[6], s[7], int(s[8])
        ix0 = max(0, int(np.floor((sx - r - x0) / cell)))
        ix1 = min(nx - 1, int(np.ceil((sx + r - x0) / cell)))
        iz0 = max(0, int(np.floor((sz - r - z0) / cell)))
        iz1 = min(nz - 1, int(np.ceil((sz + r - z0) / cell)))
        if ix1 < ix0 or iz1 < iz0:
            continue
        xs = x0 + np.arange(ix0, ix1 + 1) * cell
        zs = z0 + np.arange(iz0, iz1 + 1) * cell
        w = maskpaint_profile(np.hypot(xs[None, :] - sx, zs[:, None] - sz) / r, feather, curve) * strength
        view = grid[iz0:iz1 + 1, ix0:ix1 + 1]
        if op == 0:
            view += (value - view) * w
        elif op == 1:
            view -= view * w
        elif op == 2:
            view += w * value
        elif op == 3:
            view -= w * value
        elif op == 4:                                                                          # Smooth: the map moves towards its own blur (sigma a quarter of the radius)
            view += (_smooth_window(grid, iz0, iz1, ix0, ix1, min(max(0.25 * r / cell, 0.6), 12.0)) - view) * w
        elif op == 5:                                                                          # Multiply: towards the map x value
            view += (view * value - view) * w
        elif op == 6:                                                                          # Maximum: towards the larger of the map and the value
            view += (np.maximum(view, value) - view) * w
        else:                                                                                  # Minimum
            view += (np.minimum(view, value) - view) * w
        np.clip(view, 0.0, 1.0, out=view)
    return maskpaint_blur(grid, blur / cell) if blur > 0.0 else grid

def maskpaint_sample(grid, spec, xz, outside):
    """The map at points (n, 2) of (x, z): bilinear, `outside` beyond the grid."""
    x0, z0, cell, nx, nz = spec
    xz = np.asarray(xz, dtype=np.float64).reshape(-1, 2)
    gx = (xz[:, 0] - x0) / cell
    gz = (xz[:, 1] - z0) / cell
    inside = (gx >= 0.0) & (gx <= nx - 1.0) & (gz >= 0.0) & (gz <= nz - 1.0)
    gx = np.clip(gx, 0.0, nx - 1.0)
    gz = np.clip(gz, 0.0, nz - 1.0)
    ix = np.minimum(np.floor(gx).astype(np.int64), max(nx - 2, 0))
    iz = np.minimum(np.floor(gz).astype(np.int64), max(nz - 2, 0))
    ix1 = np.minimum(ix + 1, nx - 1)
    iz1 = np.minimum(iz + 1, nz - 1)
    tx = gx - ix
    tz = gz - iz
    val = grid[iz, ix] * (1 - tx) * (1 - tz) + grid[iz, ix1] * tx * (1 - tz) + grid[iz1, ix] * (1 - tx) * tz + grid[iz1, ix1] * tx * tz
    return np.where(inside, val, float(outside))

def maskpaint_values(stamps, xz, res, base=0.0, blur=0.0):
    """The painted mask read at (n, 2) points; the map is kept while the stamps, the resolution, the base and the blur stay the same."""
    stamps = np.asarray(stamps, dtype=np.float64).reshape(-1, MASKPAINT_COLUMNS)
    xz = np.asarray(xz, dtype=np.float64).reshape(-1, 2)
    base = min(max(float(base), 0.0), 1.0)
    if not len(stamps):
        return np.full(len(xz), base)
    spec = maskpaint_spec(stamps, res, blur)
    key = (hashlib.md5(stamps.tobytes()).hexdigest(), spec, base, round(float(blur), 6))
    grid = _MASKPAINT_CACHE.get(key)
    if grid is None:
        if len(_MASKPAINT_CACHE) > 12:
            _MASKPAINT_CACHE.clear()
        grid = _MASKPAINT_CACHE[key] = maskpaint_raster(stamps, spec, base, blur)
    return maskpaint_sample(grid, spec, xz, base)

def maskpaint_stamp_for(menu, fg, bg):
    """What a Brush Operation menu entry does: (stamp operation, brush value), or None for the two samplers (they read the mask instead of changing it)."""
    menu = int(menu)
    if menu <= 7:
        return menu, fg
    if menu == 8:
        return 0, bg
    return None

def maskpaint_mirrors(pos, sym_x, sym_z, center):
    """The positions a dab is repeated at for the symmetry: the dab itself, and its mirror images across the plane X = center X and / or Z = center Z (a dab on a mirror plane is not doubled)."""
    out = [tuple(pos)]
    cx, cz = center
    if sym_x:
        out += [(2.0 * cx - p[0], p[1], p[2]) for p in list(out)]
    if sym_z:
        out += [(p[0], p[1], 2.0 * cz - p[2]) for p in list(out)]
    keep = []
    for p in out:
        if not any(abs(p[0] - q[0]) < 1e-6 and abs(p[2] - q[2]) < 1e-6 for q in keep):
            keep.append(p)
    return keep

# ---------------------------------------------------------------- Houdini side
def maskpaint_data(asset):
    try:
        return maskpaint_decode(asset.evalParm('mask_paint_data'))
    except ValueError as error:
        raise hou.NodeError(str(error))

def maskpaint_field(asset, P):
    """The painted mask (0 .. 1, before Invert and the remap) at the points P (n, 3), read in X and Z."""
    return maskpaint_values(maskpaint_data(asset), np.asarray(P, dtype=np.float64).reshape(-1, 3)[:, [0, 2]], asset.evalParm('mask_paint_res'), asset.evalParm('mask_paint_base'), asset.evalParm('mask_paint_blur'))

def maskpaint_apply(asset, stamps, label='Arraytron mask paint'):
    """Write the stamps to the node (one undo step)."""
    with hou.undos.group(label):
        asset.parm('mask_paint_data').set(maskpaint_encode(stamps))

def maskpaint_clear(asset):
    """Clear all the paint (one undo step). Returns the number of stamps removed."""
    removed = len(maskpaint_data(asset))
    maskpaint_apply(asset, np.zeros((0, MASKPAINT_COLUMNS)), 'Arraytron clear mask paint')
    return removed

def maskpaint_value_at(asset, stamps, x, z):
    """The painted mask (before Invert and the remap) at one place, for the Sample operations."""
    return float(maskpaint_values(stamps, np.array([[x, z]]), asset.evalParm('mask_paint_res'), asset.evalParm('mask_paint_base'), 0.0)[0])

def maskpaint_fill(asset):
    """Fill Mask button: forget the paint and make the mask the Foreground value everywhere (undoable). Returns the number of stamps removed."""
    removed = len(maskpaint_data(asset))
    with hou.undos.group('Arraytron fill mask'):
        asset.parm('mask_paint_data').set('')
        asset.parm('mask_paint_base').set(asset.evalParm('mask_brush_value'))
    return removed

def maskpaint_surface(asset):
    """The triangles the brush paints on: the Paint Surface prim when it is set, else the surface of the Distribution Mode (Surface Prim, the Paint Target, the Biome terrain), else the ground plane at Y 0."""
    if asset.evalParm('mask_paint_prim').strip():
        return stage_surface(asset, 'mask_paint_prim')
    mode = asset.evalParm('mode')
    if mode == 5 and asset.parm('surface_prim') is not None:
        return stage_surface(asset, 'surface_prim')
    if mode == 6:
        return paint_surface(asset)
    if mode == 10 and asset.parm('biome_prim') is not None:
        return stage_surface(asset, 'biome_prim')
    return plane_surface(1000.0, 0.0)

def maskpaint_start(asset):
    """Paint Mask button: Mask Source Painted, this node current, the viewport tool in mask painting mode (Esc finishes)."""
    if asset.evalParm('mask_source') != 4:
        asset.parm('mask_source').set(4)
    if not hou.isUIAvailable():
        raise hou.NodeError('Painting the mask needs the Houdini interface (a Scene Viewer).')
    viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if viewer is None:
        raise hou.NodeError('Open a Scene Viewer pane to paint the mask.')
    asset.setUserData('arraytron_maskpaint', '1')
    asset.setCurrent(True, clear_all_selected=True)
    viewer.setCurrentState(paint_state_name(asset))

def maskpaint_info(asset):
    """Read-only text for the Mask folder when the source is Painted."""
    try:
        stamps = maskpaint_decode(asset.evalParm('mask_paint_data'))
    except ValueError as error:
        return str(error)
    if not len(stamps):
        return 'Nothing painted yet. Press Paint Mask, then drag over the surface; Ctrl-drag erases. The mask is %.3g everywhere until you paint.' % asset.evalParm('mask_paint_base')
    names = [int(np.count_nonzero(stamps[:, 0] == k)) for k in range(len(MASKPAINT_OPS))]
    return '%d stamps (%s). Painted extent %.3g x %.3g.' % (len(stamps), ', '.join('%d %s' % (n, MASKPAINT_OPS[k].lower()) for k, n in enumerate(names) if n),
                                                           stamps[:, 1].max() - stamps[:, 1].min(), stamps[:, 3].max() - stamps[:, 3].min())
