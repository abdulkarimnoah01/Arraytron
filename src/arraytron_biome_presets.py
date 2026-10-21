
# ---- Biome presets (src/arraytron_biome_presets.py): load a ready-made table of biomes, or save the current table as your own preset.
# A preset is a list of biome rows. Elevation is stored as a FRACTION of the terrain's height (0 = its lowest point, 1 = its highest), so a preset fits any terrain: loading it converts the fractions
# with the height range of the terrain the node points at (Terrain prim of the Biome section). The other ranges (slope, moisture, temperature) are stored as they are. A preset row's Prototype Mix
# is bank row k for the k-th biome unless the preset names one. User presets live next to the Asset Library (biome_presets.json in its folder, see ARRAYTRON_LIBRARY).
BIOME_PRESET_FILE = 'biome_presets.json'
_OPEN = None                                                       # an unbounded elevation (the whole terrain)

def _preset_row(name, density, mix, h, s=(0.0, 180.0), m=(0.0, 1.0), t=None, scale=(0.8, 1.2), layer=1, clear=0.0, excl='', he=0.05, se=8.0, me=0.15, te=3.0, teff=0.0):
    return dict(name=name, density=density, mix=mix, h=list(h) if h else None, he=he, s=list(s), se=se, m=list(m), me=me, t=list(t) if t else None, te=te, scale=list(scale), layer=layer, clear=clear, excl=excl,
                heffect=1.0 if h else 0.0, seffect=1.0, meffect=1.0, teffect=teff)

BUILTIN_BIOME_PRESETS = [
    dict(name='Temperate Forest', description='Canopy trees keep the understory and ground cover clear of their trunks; rocks on the steep faces. Bank rows: 1 trees, 2 shrubs, 3 ground plants, 4 rocks.', rows=[
        _preset_row('Canopy trees', 22.0, '1', (0.02, 0.78), s=(0, 35), m=(0.25, 1.0), scale=(0.8, 1.3), layer=1, clear=1.4, he=0.08),
        _preset_row('Understory shrubs', 45.0, '2', (0.0, 0.85), s=(0, 40), m=(0.2, 1.0), scale=(0.7, 1.2), layer=2, clear=0.6, he=0.08),
        _preset_row('Ground cover', 130.0, '3', (0.0, 0.9), s=(0, 45), m=(0.1, 1.0), scale=(0.6, 1.2), layer=3, he=0.1),
        _preset_row('Cliff rocks', 30.0, '4', None, s=(28, 90), m=(0.0, 1.0), scale=(0.6, 1.5), layer=3, se=8.0)]),
    dict(name='Alpine', description='Conifers on the lower slopes, stunted trees near the tree line, meadow plants between, scree on the steep faces. Bank rows: 1 conifers, 2 stunted trees, 3 meadow plants, 4 rocks.', rows=[
        _preset_row('Conifers', 24.0, '1', (0.05, 0.55), s=(0, 38), m=(0.2, 1.0), scale=(0.8, 1.3), layer=1, clear=1.2, he=0.1),
        _preset_row('Stunted trees', 16.0, '2', (0.5, 0.8), s=(0, 45), m=(0.0, 1.0), scale=(0.35, 0.7), layer=1, clear=0.8, he=0.08),
        _preset_row('Meadow plants', 110.0, '3', (0.25, 0.7), s=(0, 28), m=(0.15, 1.0), scale=(0.6, 1.1), layer=2, he=0.1),
        _preset_row('Scree rocks', 40.0, '4', None, s=(25, 90), m=(0.0, 1.0), scale=(0.5, 1.5), layer=2, se=8.0)]),
    dict(name='Coastal Wetland', description='Reeds in the wet, shrubs on the drier banks, dune grass on the low ground, stones at the water. Bank rows: 1 reeds, 2 shrubs, 3 dune grass, 4 stones.', rows=[
        _preset_row('Reeds', 120.0, '1', (0.0, 0.3), s=(0, 25), m=(0.6, 1.0), scale=(0.8, 1.3), layer=2, me=0.12, he=0.06),
        _preset_row('Shrubs', 30.0, '2', (0.05, 0.6), s=(0, 35), m=(0.3, 0.75), scale=(0.7, 1.3), layer=1, clear=0.9, me=0.12, he=0.08),
        _preset_row('Dune grass', 140.0, '3', (0.0, 0.2), s=(0, 30), m=(0.0, 0.45), scale=(0.6, 1.1), layer=3, he=0.05),
        _preset_row('Water stones', 60.0, '4', None, s=(0, 35), m=(0.8, 1.0), scale=(0.5, 1.3), layer=2, me=0.1)]),
    dict(name='Desert', description='Scrub and cacti on the dry ground, rocks on the steep faces, dry grass between. Bank rows: 1 scrub, 2 cacti, 3 rocks, 4 dry grass.', rows=[
        _preset_row('Scrub', 40.0, '1', (0.0, 0.7), s=(0, 28), m=(0.0, 0.4), scale=(0.7, 1.2), layer=2, he=0.08),
        _preset_row('Cacti', 9.0, '2', (0.0, 0.6), s=(0, 22), m=(0.0, 0.3), scale=(0.8, 1.4), layer=1, clear=2.0, he=0.08),
        _preset_row('Rocks', 35.0, '3', None, s=(18, 90), m=(0.0, 1.0), scale=(0.5, 1.6), layer=2, se=8.0),
        _preset_row('Dry grass', 90.0, '4', (0.0, 0.8), s=(0, 30), m=(0.05, 0.55), scale=(0.6, 1.1), layer=3, he=0.1)]),
]

def biome_preset_path():
    return os.path.join(library_dir(), BIOME_PRESET_FILE)

def biome_load_user_presets():
    """The user's presets as a list of dicts (a missing or broken file is no presets)."""
    try:
        with open(biome_preset_path(), 'r', encoding='utf8') as handle:
            data = json.load(handle)
        return [p for p in data.get('presets', []) if isinstance(p, dict) and p.get('name') and isinstance(p.get('rows'), list)]
    except (OSError, ValueError, AttributeError):
        return []

def biome_save_user_presets(presets):
    os.makedirs(library_dir(), exist_ok=True)
    path = biome_preset_path()
    with open(path + '.tmp', 'w', encoding='utf8') as handle:
        json.dump({'version': 1, 'presets': presets}, handle, indent=1, sort_keys=True)
    os.replace(path + '.tmp', path)
    return path

def biome_all_presets():
    """(label, preset) of the built-in presets, then the user's own."""
    return [(p['name'], p) for p in BUILTIN_BIOME_PRESETS] + [(p['name'] + '  (mine)', p) for p in biome_load_user_presets()]

def biome_terrain_height(asset):
    """(lowest, highest) height (world Y) of the terrain the node points at; (0, 1) when it cannot be read."""
    try:
        P = stage_surface(asset, 'biome_prim')[0]
        if len(P):
            return float(P[:, 1].min()), float(P[:, 1].max())
    except Exception:
        pass
    return 0.0, 1.0

def biome_snapshot(asset, ymin, span):
    """The current table of the node as a preset's rows (elevation as fractions of the height range)."""
    rows = []
    big = 99999.0
    for i in range(1, asset.evalParm('biomes') + 1):
        lo, hi = asset.evalParmTuple('biome_hrange%d' % i)
        open_h = lo <= -big and hi >= big
        s = asset.evalParmTuple('biome_srange%d' % i)
        m = asset.evalParmTuple('biome_mrange%d' % i)
        t = asset.evalParmTuple('biome_trange%d' % i)
        rows.append(dict(name=asset.evalParm('biome_name%d' % i), density=asset.evalParm('biome_density%d' % i), mix=asset.evalParm('biome_mix%d' % i),
                         h=None if open_h else [(lo - ymin) / span, (hi - ymin) / span], he=asset.evalParm('biome_hedge%d' % i) / span, s=list(s), se=asset.evalParm('biome_sedge%d' % i), m=list(m),
                         me=asset.evalParm('biome_medge%d' % i), t=None if (t[0] <= -99.0 and t[1] >= 99.0) else list(t), te=asset.evalParm('biome_tedge%d' % i), scale=list(asset.evalParmTuple('biome_scale%d' % i)),
                         layer=asset.evalParm('biome_layer%d' % i), clear=asset.evalParm('biome_clear%d' % i), excl=asset.evalParm('biome_excl%d' % i),
                         heffect=asset.evalParm('biome_heffect%d' % i), seffect=asset.evalParm('biome_seffect%d' % i), meffect=asset.evalParm('biome_meffect%d' % i), teffect=asset.evalParm('biome_teffect%d' % i)))
    return rows

def biome_apply_preset(asset, preset):
    """Replace the Biomes table of the node with the rows of a preset (one undo step). Elevations are converted with the terrain's height range."""
    ymin, ymax = biome_terrain_height(asset)
    span = max(ymax - ymin, 1e-6)
    rows = preset['rows'][:BIOME_MAX_ROWS]
    bank = max(1, asset.evalParm('protos'))
    big = 100000.0
    with hou.undos.group('Arraytron: biome preset %s' % preset.get('name', '')):
        asset.parm('biomes').set(len(rows))
        for i, r in enumerate(rows, 1):
            asset.parm('biome_on%d' % i).set(1)
            asset.parm('biome_name%d' % i).set(r.get('name', 'Biome'))
            asset.parm('biome_density%d' % i).set(float(r.get('density', 20.0)))
            asset.parm('biome_mix%d' % i).set(str(r.get('mix') or min(i, bank)))
            h = r.get('h')
            asset.parmTuple('biome_hrange%d' % i).set((ymin + h[0] * span, ymin + h[1] * span) if h else (-big, big))
            asset.parm('biome_hedge%d' % i).set(float(r.get('he', 0.0)) * span if h else 0.0)
            asset.parmTuple('biome_srange%d' % i).set(tuple(r.get('s', (0.0, 180.0))))
            asset.parm('biome_sedge%d' % i).set(float(r.get('se', 0.0)))
            asset.parmTuple('biome_mrange%d' % i).set(tuple(r.get('m', (0.0, 1.0))))
            asset.parm('biome_medge%d' % i).set(float(r.get('me', 0.0)))
            t = r.get('t')
            asset.parmTuple('biome_trange%d' % i).set(tuple(t) if t else (-100.0, 100.0))
            asset.parm('biome_tedge%d' % i).set(float(r.get('te', 0.0)) if t else 0.0)
            asset.parmTuple('biome_scale%d' % i).set(tuple(r.get('scale', (0.8, 1.2))))
            for key, parm in (('heffect', 'biome_heffect'), ('seffect', 'biome_seffect'), ('meffect', 'biome_meffect'), ('teffect', 'biome_teffect')):
                asset.parm('%s%d' % (parm, i)).set(float(r.get(key, 1.0)))
            asset.parm('biome_layer%d' % i).set(int(r.get('layer', 1)))
            asset.parm('biome_clear%d' % i).set(float(r.get('clear', 0.0)))
            asset.parm('biome_excl%d' % i).set(str(r.get('excl', '')))
    return len(rows)

def biome_save_preset(asset, name):
    """Save the current table as a user preset with this name (an existing one with the same name is replaced). Returns the file."""
    ymin, ymax = biome_terrain_height(asset)
    span = max(ymax - ymin, 1e-6)
    name = clean_name(name)
    presets = [p for p in biome_load_user_presets() if p['name'] != name]
    presets.append(dict(name=name, description='Saved from %s' % asset.name(), rows=biome_snapshot(asset, ymin, span)))
    return biome_save_user_presets(presets)

def biome_preset_load(asset):
    """Button: choose a preset from a list and load it (asks before replacing a table that has rows)."""
    entries = biome_all_presets()
    pick = hou.ui.selectFromList([label for label, _ in entries], exclusive=True, title='Biome preset', message='Load a preset into the Biomes table. Elevations fit the Terrain prim\'s height.', width=520, height=260)
    if not pick:
        return None
    preset = entries[pick[0]][1]
    if asset.evalParm('biomes') > 0 and hou.ui.displayConfirmation('Replace the %d biome rows of this node with the preset "%s"?' % (asset.evalParm('biomes'), preset['name'])) is False:
        return None
    return biome_apply_preset(asset, preset)

def biome_preset_save(asset):
    """Button: save the current table as a preset of your own."""
    if asset.evalParm('biomes') == 0:
        hou.ui.displayMessage('The Biomes table is empty: nothing to save.')
        return None
    button, name = hou.ui.readInput('Name of the preset (the table is saved with elevations as fractions of the terrain height):', buttons=('Save', 'Cancel'), default_choice=0, close_choice=1, initial_contents=asset.name())
    if button != 0 or not clean_name(name):
        return None
    return biome_save_preset(asset, name)
