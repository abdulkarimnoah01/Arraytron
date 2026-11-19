
# ---- Saved masks (src/arraytron_maskstage.py, v1.38.0): the Mask section, Save, Cache And Export > Save Mask For Other Arraytron Nodes, and the Mask Source Upstream Mask.
# A node that has "Save Mask" on writes its final mask weight (what its own Density / Scale used) onto its output prim as a small grid (customData arraytron:mask: name, extent, size and the zlib compressed
# 16 bit float values) and as a per-instance primvar with a proper name (<node>_mask, or the name you type). The stage carries it down the tree: every Arraytron node below can pick it as its Mask Source
# (Upstream Mask), reads it without evaluating the paint or the noise again (a cache that lives in the stage, no file), and is offered it automatically when it is wired below a node that saved one.
import base64
import hashlib
import json
import re
import zlib
import hou
from pxr import Usd, UsdGeom

MSTAGE_KEY = 'arraytron:mask'
MSTAGE_RESERVED = ('p', 'id', 'n', 'cd', 'alpha', 'pscale', 'scale', 'orient', 'up', 'v', 'rot', 'align', 'srcscale', 'protoindex', 'proto_id', 'protopath', 'maskweight', 'maskscale', 'fieldweight', 'arraytron_id',
                   'prototype_id', 'random', 'mask', 'density', 'cluster', 'biome', 'source_id', 'arraytron_lod')
MSTAGE_CACHE = {}                          # node path -> (key, payload): the grid is not computed again while nothing it depends on changed
MSTAGE_GRIDS = {}                          # md5 of the saved data -> the decoded grid (float32, rows -Z to +Z)
MUP_OFFERED = {}                           # node path -> the mask names already offered to it in this session (a mask is offered once)

def mstage_clean(name):
    """A proper primvar / mask name: letters, digits and underscores, not starting with a digit."""
    text = re.sub(r'\W+', '_', str(name or '')).strip('_')
    if text and text[0].isdigit():
        text = '_' + text
    return text

def mstage_on(asset):
    """True when this node saves its mask: the switch is on and there is a Mask Source (an Upstream Mask counts)."""
    return asset.parm('mstage_on') is not None and bool(asset.evalParm('mstage_on')) and asset.evalParm('mask_source') != 0

def mstage_name(asset):
    """The name the mask is saved under (and the primvar): the one typed in Mask Name, else <node name>_mask. A name that would clash with an attribute the instancer writes itself gets _mask appended."""
    name = mstage_clean(asset.evalParm('mstage_name')) if asset.parm('mstage_name') is not None else ''
    if not name:
        name = mstage_clean(asset.name()) + '_mask'
    if name.lower() in MSTAGE_RESERVED:
        name += '_mask'
    return name

def mstage_primvar(asset):
    """The point attribute that becomes primvars:<name> (the final mask weight of every instance), or '' when no mask is saved."""
    return mstage_name(asset) if mstage_on(asset) else ''

# ---- writing
def mstage_raster(asset, extent, res, y=0.0):
    """The final mask weight (after Edge Fade, Invert, Low / High, Gamma, Remap Curve and Output Range: what the node used) over the extent as a grid, rows -Z to +Z, columns -X to +X, the longer side res cells."""
    cx, cz, sx, sz = extent
    res = int(min(max(res, 8), MSTAGE_MAX_RES))
    w = res if sx >= sz else max(int(round(res * sx / sz)), 2)
    h = res if sz > sx else max(int(round(res * sz / sx)), 2)
    xs = cx + ((np.arange(w) + 0.5) / w - 0.5) * sx
    zs = cz + ((np.arange(h) + 0.5) / h - 0.5) * sz
    X, Z = np.meshgrid(xs, zs)
    P = np.stack([X.ravel(), np.full(X.size, float(y)), Z.ravel()], axis=1)
    raw = np.clip(np.asarray(mask_values(asset, P, np.arange(len(P))), dtype=np.float64), 0.0, 1.0)
    return np.clip(np.asarray(mask_weights(asset, raw), dtype=np.float64).reshape(h, w), 0.0, 1.0)

MSTAGE_MAX_RES = 2048

def mstage_encode(grid):
    """The grid as text: 16 bit floats, zlib, base64 (a smooth mask of 256 x 256 is a few kilobytes)."""
    return base64.b64encode(zlib.compress(np.ascontiguousarray(grid, dtype='<f2').tobytes(), 6)).decode('ascii')

def mstage_decode(payload):
    """The saved grid of a payload as float32 (h, w); decoded once per content."""
    key = hashlib.md5(payload['data'].encode('ascii')).hexdigest() + '%dx%d' % (payload['w'], payload['h'])
    grid = MSTAGE_GRIDS.get(key)
    if grid is None:
        raw = zlib.decompress(base64.b64decode(payload['data']))
        grid = np.frombuffer(raw, dtype='<f2').astype(np.float32).reshape(int(payload['h']), int(payload['w']))
        if len(MSTAGE_GRIDS) > 64:
            MSTAGE_GRIDS.clear()
        MSTAGE_GRIDS[key] = grid
    return grid

def mstage_key(asset, extent, y):
    """What the saved grid depends on, for the cache: every Mask parameter, the name, the size, the area. The sources that read the stage (Mesh Primvar, Upstream Mask) are not cached."""
    if asset.evalParm('mask_source') in (3, 6):
        return None
    vals = []
    for p in asset.parms():
        n = p.name()
        if n.startswith('mask_') or n in ('mstage_res', 'mstage_name', 'seed'):
            try:
                vals.append((n, repr(p.eval())))
            except hou.Error:
                vals.append((n, '?'))
    return (tuple(vals), tuple(round(float(v), 4) for v in extent), round(float(y), 3))

def mstage_payload(asset):
    """The dict stored in customData arraytron:mask for this node, or None when it saves nothing. The grid covers the Export Area (Automatic: the generated points plus a tenth of margin; Custom: the Image
    Center and Size) at the Cache Resolution."""
    if not mstage_on(asset):
        return None
    pts = mask_export_points(asset)
    extent = mask_export_extent(asset, pts)
    y = float(pts[:, 1].mean()) if len(pts) else 0.0
    key = mstage_key(asset, extent, y)
    hit = MSTAGE_CACHE.get(asset.path())
    if key is not None and hit is not None and hit[0] == key:
        return hit[1]
    grid = mstage_raster(asset, extent, asset.evalParm('mstage_res'), y)
    payload = dict(name=mstage_name(asset), v=1, node=asset.path(), source=int(asset.evalParm('mask_source')), cx=float(extent[0]), cz=float(extent[1]), sx=float(extent[2]), sz=float(extent[3]),
                   w=int(grid.shape[1]), h=int(grid.shape[0]), data=mstage_encode(grid))
    if key is not None:
        MSTAGE_CACHE[asset.path()] = (key, payload)
    return payload

def mstage_author(asset, instancer):
    """Called by the Python LOP that finishes the output prim: write (or remove) customData arraytron:mask."""
    payload = mstage_payload(asset)
    if payload is None:
        instancer.ClearCustomDataByKey(MSTAGE_KEY)
    else:
        instancer.SetCustomDataByKey(MSTAGE_KEY, payload)

# ---- finding and using the masks of the nodes above
def mstage_find(stage):
    """The masks saved in a stage: [payload dict + 'prim'] for every prim that carries customData arraytron:mask, in stage order. The prototypes below an instancer are not searched."""
    found = []
    if stage is None:
        return found
    it = iter(Usd.PrimRange(stage.GetPseudoRoot()))
    for prim in it:
        data = prim.GetCustomDataByKey(MSTAGE_KEY) if prim.IsValid() else None
        if data and 'data' in data and 'name' in data:
            item = dict(data)
            item['prim'] = str(prim.GetPath())
            found.append(item)
        if prim.IsA(UsdGeom.PointInstancer):
            it.PruneChildren()
    return found

def mup_stage(asset):
    """The stage the Upstream Mask reads: everything that reaches the Source Resolver while cooking."""
    node = asset.node('SOURCE_RESOLVER')
    stage = node.stage() if node is not None else None
    if stage is None:
        raise hou.NodeError('The incoming stage is not available.')
    return stage

def mup_names(asset):
    return [n for n in asset.evalParm('mup_name').split() if n]

def mup_values(asset, P):
    """The Upstream Mask source: the saved mask(s) named in Upstream Mask, looked at from above at each point, bilinear, black (or the edge value) beyond the saved area; several names are combined (Multiply,
    Maximum or Minimum). Raises hou.NodeError with the saved names when one is missing."""
    names = mup_names(asset)
    if not names:
        raise hou.NodeError('Upstream Mask: choose a mask. Wire this node below an Arraytron node that has Save Mask on, then pick it in Upstream Mask (or click Find Upstream Masks).')
    saved = {p['name']: p for p in mstage_find(mup_stage(asset))}
    missing = [n for n in names if n not in saved]
    if missing:
        raise hou.NodeError('Upstream Mask: %s not found in the incoming stage. Saved masks there: %s.' % (', '.join('"%s"' % n for n in missing), ', '.join('"%s"' % n for n in sorted(saved)) or 'none'))
    P = np.asarray(P, dtype=np.float64)
    edge = 2 if asset.evalParm('mup_outside') == 1 else 0
    mode = asset.evalParm('mup_combine')
    out = None
    for name in names:
        p = saved[name]
        v = sample_image(mstage_decode(p), (P[:, 0] - p['cx']) / max(p['sx'], 1e-9) + 0.5, (P[:, 2] - p['cz']) / max(p['sz'], 1e-9) + 0.5, edge)
        out = v if out is None else (out * v if mode == 0 else np.maximum(out, v) if mode == 1 else np.minimum(out, v))
    return np.clip(out, 0.0, 1.0)

def mup_menu(asset):
    """The menu of Upstream Mask: the masks saved by the nodes above (token = name, label = name and where it comes from)."""
    try:
        src = asset.inputs()[0] if asset.inputs() else None
        found = mstage_find(src.stage()) if src is not None else []
    except hou.Error:
        found = []
    items = []
    for p in found:
        items += [p['name'], '%s   (%s, %d x %d)' % (p['name'], p.get('node', p['prim']).rsplit('/', 1)[-1], p['w'], p['h'])]
    return items or ['', 'No saved masks above this node (switch Save Mask on in the node above)']

def mup_info(asset):
    """Read-only text under Upstream Mask: which masks the stream above holds, and which this node uses."""
    try:
        src = asset.inputs()[0] if asset.inputs() else None
        if src is None:
            return 'Nothing is wired into the first input.'
        found = mstage_find(src.stage())
    except hou.Error as exc:
        return 'Cannot read the stage above: %s' % exc
    if not found:
        return 'No saved mask above this node. Switch Save Mask on (Mask > Save, Cache And Export) in an Arraytron node above it.'
    used = mup_names(asset) if asset.evalParm('mask_source') == 6 else []
    return '\n'.join('%s %s  from %s  %d x %d cells over %.4g x %.4g' % ('*' if p['name'] in used else '-', p['name'], p.get('node', p['prim']), p['w'], p['h'], p['sx'], p['sz']) for p in found)

def mstage_info(asset):
    """Read-only text under Save Mask: what is saved."""
    if asset.evalParm('mask_source') == 0:
        return 'There is no mask to save: choose a Mask Source.'
    if not asset.evalParm('mstage_on'):
        return 'Off: the mask is only used by this node.'
    try:
        prim = asset.node('OUT_ARRAYTRON').stage().GetPrimAtPath(asset.evalParm('outputpath'))
        data = prim.GetCustomDataByKey(MSTAGE_KEY)
    except Exception as exc:
        return 'Cannot read the stage: %s' % exc
    if not data:
        return 'Saves the mask "%s" (and primvars:%s) when the node cooks.' % (mstage_name(asset), mstage_name(asset))
    return 'Saved the mask "%s": %d x %d cells over %.4g x %.4g; primvars:%s on every instance.' % (data['name'], data['w'], data['h'], data['sx'], data['sz'], data['name'])

# ---- the prompt
def mup_ask(text, buttons):
    return hou.ui.displayMessage(text, buttons=buttons, default_choice=0, close_choice=len(buttons) - 1, title='Arraytron: use the previous mask?')

def mup_select(text, names):
    return hou.ui.selectFromList(names, default_choices=tuple(range(len(names))), message=text, title='Arraytron: use the previous masks?', clear_on_cancel=True)

MUP_ASK = mup_ask
MUP_SELECT = mup_select
MUP_FORCE = False                          # the tests switch it on: the window functions above are replaced by stand-ins

def mup_set_ui(ask=None, select=None, force=None):
    """Replace the window functions (and the 'there is a user interface' check) with stand-ins: for the tests (node.hdaModule() hands out a wrapper, so the module's names can only be changed from inside)."""
    global MUP_ASK, MUP_SELECT, MUP_FORCE
    if ask is not None:
        MUP_ASK = ask
    if select is not None:
        MUP_SELECT = select
    if force is not None:
        MUP_FORCE = force

def mup_apply(asset, names):
    """Use the masks as this node's Mask Source (Upstream Mask, Multiply). One undo step."""
    with hou.undos.group('Arraytron: use the upstream mask'):
        asset.parm('mask_source').set(6)
        asset.parm('mup_name').set(' '.join(names))
        asset.parm('mup_combine').set(0)

def mup_prompt(asset, manual=False):
    """Offer the masks saved above this node. Automatic (an input changed): once per mask and node, only when the node does not use it yet and Offer Upstream Masks is on; the choice is Use, Not Now or Don't Ask
    Again. Manual (the Find Upstream Masks button): always offers every mask. Returns the names that were applied (an empty list when nothing was)."""
    try:
        src = asset.inputs()[0] if asset.inputs() else None
        found = mstage_find(src.stage()) if src is not None else []
    except hou.Error:
        return []
    using = mup_names(asset) if asset.evalParm('mask_source') == 6 else []
    offered = MUP_OFFERED.setdefault(asset.path(), set())
    fresh = [p for p in found if p['name'] not in using and (manual or p['name'] not in offered)]
    if not fresh:
        if manual:
            MUP_ASK('No other masks are saved above this node.' if found else 'No saved mask above this node: switch Save Mask on in an Arraytron node above it.', ('OK',))
        return []
    for p in fresh:
        offered.add(p['name'])
    where = lambda p: '"%s" (%s)' % (p['name'], p.get('node', p['prim']).rsplit('/', 1)[-1])
    current = asset.evalParm('mask_source')
    replace = ' It replaces the Mask Source of this node.' if current not in (0, 6) else ''
    if len(fresh) == 1:
        choice = MUP_ASK('The node above saved the mask %s.\nUse it as the Mask of "%s"?%s' % (where(fresh[0]), asset.name(), replace), ('Use This Mask', 'Not Now', "Don't Ask Again"))
        if choice == 2:
            asset.parm('mup_ask').set(0)
        picked = [fresh[0]['name']] if choice == 0 else []
    else:
        chosen = MUP_SELECT('Arraytron nodes above "%s" saved %d masks. Choose the ones to use (several are multiplied).%s' % (asset.name(), len(fresh), replace), [where(p) for p in fresh])
        picked = [fresh[i]['name'] for i in chosen] if chosen else []
    if picked:
        mup_apply(asset, using + picked if using else picked)
    return picked

def mup_input_changed(asset):
    """OnInputChanged: offer the masks of the nodes above when the first input changed (a window, never while the node is only being loaded or scripted). Does nothing without the user interface or when Offer
    Upstream Masks is off."""
    if asset.parm('mup_ask') is None or not asset.evalParm('mup_ask') or not (hou.isUIAvailable() or MUP_FORCE):
        return []
    return mup_prompt(asset)

def mup_find_button(asset):
    """The Find Upstream Masks button."""
    return mup_prompt(asset, manual=True)
