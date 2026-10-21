
# ---- Painted biome map (src/arraytron_biomemap.py): paint where a biome grows (and where it stays out) with a viewport brush.
# The paint is a list of STAMPS: row (the biome row), sign (+1 paint, -1 erase), x, y, z (the hit on the terrain; y is only for the viewport preview), radius, strength, falloff. They are kept in the hidden
# parameter biome_map_data (JSON). At cook time every biome row whose Map menu is not Off turns its stamps into a 2D map over the terrain (a grid of biome_map_res x biome_map_res cells in X and Z,
# the stamps applied in the order they were painted: paint takes the maximum, erase the minimum), samples it at its candidates and combines it with the weight of the conditions:
#   Add And Erase:       painted places grow even when the conditions say no (union), erased places are kept free (the weight shrinks to 0)
#   Only Where Painted:  the biome grows where the conditions hold AND it is painted
# The viewport tool is the biome mode of the Arraytron viewer state (src/arraytron_paint_state.py). A row without paint, or with Map Off, is exactly as before.
BIOMEMAP_MAX = 100000                  # stamps kept
BIOMEMAP_COLUMNS = 8                   # row, sign, x, y, z, radius, strength, falloff
_BIOMEMAP_CACHE = {}

def biomemap_decode(text):
    """The stamps (n, 8) of the biome_map_data text; an empty text is no stamps, a text that is not a biome map is an error."""
    text = (text or '').strip()
    if not text:
        return np.zeros((0, BIOMEMAP_COLUMNS))
    try:
        data = json.loads(text)
        stamps = np.array(data['stamps'], dtype=np.float64).reshape(-1, BIOMEMAP_COLUMNS)
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError('The painted biome map cannot be read (%s). Clear it with Clear All Paint.' % error)
    return stamps

def biomemap_encode(stamps):
    stamps = np.asarray(stamps, dtype=np.float64).reshape(-1, BIOMEMAP_COLUMNS)[-BIOMEMAP_MAX:]
    if not len(stamps):
        return ''
    rows = [[int(s[0]), int(s[1]), round(float(s[2]), 3), round(float(s[3]), 3), round(float(s[4]), 3), round(float(s[5]), 4), round(float(s[6]), 3), int(s[7])] for s in stamps]
    return json.dumps({'v': 1, 'stamps': rows}, separators=(',', ':'))

def biomemap_add(stamps, row, sign, pos, radius, strength, falloff):
    """The stamps with one more (a copy) and whether one was added: a stamp of the same row, sign and radius that lies closer than a fifth of the radius to the last one is skipped, so a slow drag does
    not pile up stamps."""
    stamps = np.asarray(stamps, dtype=np.float64).reshape(-1, BIOMEMAP_COLUMNS)
    if len(stamps):
        last = stamps[-1]
        if int(last[0]) == int(row) and int(last[1]) == int(sign) and abs(last[5] - radius) < 1e-9 and np.hypot(last[2] - pos[0], last[4] - pos[2]) < 0.2 * radius:
            return stamps, False
    new = np.vstack([stamps, [[row, sign, pos[0], pos[1], pos[2], radius, strength, falloff]]])
    return new[-BIOMEMAP_MAX:], True

def biomemap_bounds(P):
    """(x0, z0, x1, z1) of the terrain in the XZ plane, a little larger than the points."""
    P = np.asarray(P, dtype=np.float64)
    lo = P[:, [0, 2]].min(axis=0)
    hi = P[:, [0, 2]].max(axis=0)
    pad = max(float((hi - lo).max()) * 0.01, 1e-6)
    return float(lo[0] - pad), float(lo[1] - pad), float(hi[0] + pad), float(hi[1] + pad)

def biomemap_raster(stamps, row, bounds, res):
    """The map of one biome row as a (res, res) array [z, x] with values in -1 .. 1: the stamps of the row applied in order (paint: maximum of the value and the stamp weight, erase: minimum of the value
    and minus the stamp weight; the weight is the falloff of the distance times the strength)."""
    x0, z0, x1, z1 = bounds
    res = int(max(res, 2))
    grid = np.zeros((res, res))
    cx = (x1 - x0) / (res - 1)
    cz = (z1 - z0) / (res - 1)
    for s in np.asarray(stamps).reshape(-1, BIOMEMAP_COLUMNS):
        if int(s[0]) != int(row):
            continue
        sx, sz, r, strength, fall = s[2], s[4], max(s[5], 1e-9), s[6], int(s[7])
        ix0 = max(0, int(np.floor((sx - r - x0) / cx)))
        ix1 = min(res - 1, int(np.ceil((sx + r - x0) / cx)))
        iz0 = max(0, int(np.floor((sz - r - z0) / cz)))
        iz1 = min(res - 1, int(np.ceil((sz + r - z0) / cz)))
        if ix1 < ix0 or iz1 < iz0:
            continue
        xs = x0 + np.arange(ix0, ix1 + 1) * cx
        zs = z0 + np.arange(iz0, iz1 + 1) * cz
        weight = falloff_weight(np.hypot(xs[None, :] - sx, zs[:, None] - sz) / r, fall) * strength
        view = grid[iz0:iz1 + 1, ix0:ix1 + 1]
        reach = weight > 0.0                                          # only the cells the stamp really covers (its box has corners outside the circle)
        if s[1] > 0:
            view[reach] = np.maximum(view[reach], weight[reach])
        else:
            view[reach] = np.minimum(view[reach], -weight[reach])
    return grid

def biomemap_sample(grid, bounds, xz):
    """The map at points (n, 2) of (x, z): bilinear, the value of the nearest border outside the terrain."""
    x0, z0, x1, z1 = bounds
    res = grid.shape[0]
    xz = np.asarray(xz, dtype=np.float64).reshape(-1, 2)
    fx = np.clip((xz[:, 0] - x0) / (x1 - x0) * (res - 1), 0.0, res - 1.0)
    fz = np.clip((xz[:, 1] - z0) / (z1 - z0) * (res - 1), 0.0, res - 1.0)
    ix = np.minimum(np.floor(fx).astype(np.int64), res - 2)
    iz = np.minimum(np.floor(fz).astype(np.int64), res - 2)
    tx = fx - ix
    tz = fz - iz
    return (grid[iz, ix] * (1 - tx) * (1 - tz) + grid[iz, ix + 1] * tx * (1 - tz) + grid[iz + 1, ix] * (1 - tx) * tz + grid[iz + 1, ix + 1] * tx * tz)

def biomemap_combine(w, v, mode):
    """The weight of the conditions w combined with the map value v (-1 .. 1): mode 1 Add And Erase, mode 2 Only Where Painted, anything else leaves w alone."""
    w = np.asarray(w, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    if mode == 1:
        return (1.0 - (1.0 - w) * (1.0 - np.clip(v, 0.0, 1.0))) * (1.0 - np.clip(-v, 0.0, 1.0))
    if mode == 2:
        return w * np.clip(v, 0.0, 1.0)
    return w

def biomemap_values(stamps, row, bounds, res, xz, key=None):
    """The map of a biome row sampled at (n, 2) points; the raster is kept while the stamps, the bounds and the resolution stay the same."""
    cache_key = (key if key is not None else hash(np.asarray(stamps).tobytes()), int(row), tuple(round(b, 6) for b in bounds), int(res))
    grid = _BIOMEMAP_CACHE.get(cache_key)
    if grid is None:
        if len(_BIOMEMAP_CACHE) > 24:
            _BIOMEMAP_CACHE.clear()
        grid = _BIOMEMAP_CACHE[cache_key] = biomemap_raster(stamps, row, bounds, res)
    return biomemap_sample(grid, bounds, xz)

# ---------------------------------------------------------------- Houdini side
def biomemap_data(asset):
    try:
        return biomemap_decode(asset.evalParm('biome_map_data'))
    except ValueError as error:
        raise hou.NodeError(str(error))

def biomemap_apply(asset, stamps, label='Arraytron biome map'):
    """Write the stamps to the node (one undo step)."""
    with hou.undos.group(label):
        asset.parm('biome_map_data').set(biomemap_encode(stamps))

def biomemap_clear(asset, row=None):
    """Clear all the paint (row None) or the paint of one biome row (one undo step). Returns the number of stamps removed."""
    stamps = biomemap_data(asset)
    keep = stamps if row is None else stamps[stamps[:, 0] != row]
    removed = len(stamps) - len(keep) if row is not None else len(stamps)
    biomemap_apply(asset, keep if row is not None else np.zeros((0, BIOMEMAP_COLUMNS)), 'Arraytron clear biome map')
    return removed

def biomemap_surface(asset):
    """The triangles of the terrain (the Terrain prim of the Biome section) for the viewport tool."""
    return stage_surface(asset, 'biome_prim')

def biomemap_start(asset):
    """Paint Biome Map button: Biome mode, this node current, the viewport tool in biome painting mode (Esc finishes)."""
    if asset.evalParm('mode') != 10:
        asset.parm('mode').set(10)
    if not hou.isUIAvailable():
        raise hou.NodeError('Painting a biome map needs the Houdini interface (a Scene Viewer).')
    viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if viewer is None:
        raise hou.NodeError('Open a Scene Viewer pane to paint the biome map.')
    asset.setUserData('arraytron_biomepaint', '1')
    asset.setCurrent(True, clear_all_selected=True)
    viewer.setCurrentState(paint_state_name(asset))

def biomemap_info(asset):
    """Read-only text: the stamps per biome row and the Map setting of the row."""
    if asset.evalParm('mode') != 10:
        return 'Switch Distribution Mode to Biome.'
    try:
        stamps = biomemap_decode(asset.evalParm('biome_map_data'))
    except ValueError as error:
        return str(error)
    names = ['Off', 'Add And Erase', 'Only Where Painted']
    lines = []
    for i in range(1, asset.evalParm('biomes') + 1):
        sel = stamps[stamps[:, 0] == i] if len(stamps) else stamps
        paint = int(np.count_nonzero(sel[:, 1] > 0)) if len(sel) else 0
        erase = int(len(sel)) - paint
        mode = asset.evalParm('biome_map%d' % i)
        if paint or erase:
            lines.append('Row %d %s: map %s, %d paint and %d erase stamps%s' % (i, asset.evalParm('biome_name%d' % i), names[min(mode, 2)], paint, erase,
                                                                                '  (paint ignored: set Map)' if (paint or erase) and not mode else ''))
    return '\n'.join(lines) if lines else 'Nothing painted yet. Press Paint Biome Map, pick a row (keys 1 to 9), drag on the terrain; Ctrl-drag keeps the biome out. Then set the row\'s Map.'
