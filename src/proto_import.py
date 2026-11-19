# ---- Prototype sockets (src/proto_import.py): Prototype Inputs 2 to 4 of Arraytron and Arraytron Stamp as sockets that fill the Prototype Bank by themselves.
# Embedded in the PythonModule of both HDAs, next to src/arraytron_library.py (it uses its library functions). One click (Import Prototype Inputs) reads every prototype wired into the sockets, through
# merges and node trees (it reads the stage the socket delivers), adds each one to the Prototype Bank as an Input Connection row (so the row stays live: change the network and the cook follows)
# and to the Asset Library as a USD asset (the original file when the prototype is a plain reference to a file, else a standalone .usda written next to the library). Undoable, safe to click again.
import hashlib
import os
import re
import hou
from pxr import Sdf, Usd, UsdGeom

PROTO_SOCKETS = 3                  # Prototype Input 2, 3 and 4 = HDA inputs 1, 2 and 3 (0 is the scene)
PROTO_LIBRARY_CATEGORY = 'Imported'
PROTO_ROW_INPUT = 1                # Source Type menu index of "Input Connection" in both HDAs (0 Prim Path, 1 Input Connection, 2 USD File)

def proto_socket_stage(node, socket):
    """The stage delivered by Prototype Input 2 + socket (socket 0..2), or None when nothing is wired there (or it has no stage)."""
    inputs = node.inputs()
    index = socket + 1
    source = inputs[index] if index < len(inputs) else None
    if source is None:
        return None
    try:
        return source.stage()
    except hou.Error:
        return None

def _drawable(prim):
    """True when the prim is, or holds, something that is drawn: a gprim, or a point instancer (instance proxies included)."""
    try:
        for p in Usd.PrimRange(prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
            if p.IsA(UsdGeom.Gprim) or p.IsA(UsdGeom.PointInstancer):
                return True
    except Exception:
        return prim.IsA(UsdGeom.Gprim)
    return False

def _kind(prim):
    try:
        return str(Usd.ModelAPI(prim).GetKind() or '')
    except Exception:
        return ''

def _descend(prim):
    """The prim a top-level prototype stands for: down single-child chains until a component, an assembly or a gprim, or a group with several children (the rule of an Input Connection row without a Prim Path)."""
    cur = prim
    while True:
        if _kind(cur) in ('component', 'assembly') or cur.IsA(UsdGeom.Gprim):
            return cur
        kids = [c for c in cur.GetChildren() if c.GetName() != 'HoudiniLayerInfo']
        if len(kids) != 1:
            return cur
        cur = kids[0]

def _collect(prim, out):
    """Add the prototypes under one prim: a container (kind group or assembly) gives its children, anything else is one prototype."""
    if prim.GetName() == 'HoudiniLayerInfo' or not prim.IsActive() or not prim.IsA(UsdGeom.Imageable):
        return
    if _kind(prim) in ('group', 'assembly') and not prim.IsA(UsdGeom.Gprim):
        for child in prim.GetChildren():
            _collect(child, out)
        return
    if _drawable(prim):
        out.append(_descend(prim))

def proto_scan(node):
    """Every prototype wired into the Prototype Inputs: [dict(socket, path, name)] in socket and stage order. Each top-level prim of a socket is one prototype (a container of kind group or assembly gives its
    children instead); a prim without anything drawable (materials, lights, cameras) is skipped. Raises hou.NodeError when no Prototype Input is connected."""
    found, seen, wired = [], set(), 0
    for socket in range(PROTO_SOCKETS):
        stage = proto_socket_stage(node, socket)
        if stage is None:
            continue
        wired += 1
        prims = []
        for top in stage.GetPseudoRoot().GetChildren():
            _collect(top, prims)
        for prim in prims:
            path = str(prim.GetPath())
            if path in seen:
                continue
            seen.add(path)
            found.append(dict(socket=socket, path=path, name=prim.GetName()))
    if not wired:
        raise hou.NodeError('No Prototype Input is connected: wire the models into Input 2, 3 or 4, then import them.')
    return found

# ---- the Asset Library side
def _clean_leaf(name):
    return re.sub(r'\W+', '_', name).strip('_') or 'proto'

def _usd_file_of(prim):
    """(file, prim path inside it) when the prim is one plain reference or payload to an existing USD file, else None. The strongest layer that holds a reference decides; two arcs on it are not a plain file."""
    for spec in prim.GetPrimStack():
        items = []
        for listop in (spec.referenceList, spec.payloadList):
            for part in (listop.explicitItems, listop.prependedItems, listop.addedItems, listop.appendedItems):
                items.extend(part)
        if not items:
            continue
        if len(items) != 1 or not items[0].assetPath:
            return None
        item = items[0]
        path = item.assetPath if os.path.isabs(item.assetPath) else spec.layer.ComputeAbsolutePath(item.assetPath)
        path = path.replace('\\', '/')
        if len(path) > 1 and path[1] == ':':                       # Houdini 20.5 writes the drive letter in lower case: one spelling, so the same file is the same library asset
            path = path[0].upper() + path[1:]
        if not os.path.isfile(path) or not path.lower().endswith(USD_SUFFIXES):
            return None
        target = str(item.primPath) if item.primPath else default_prim_of(path)
        if not target:
            return None
        try:
            stage = Usd.Stage.Open(path, Usd.Stage.LoadNone)
            if not stage.GetPrimAtPath(target).IsValid():
                return None
        except Exception:
            return None
        return path, target
    return None

def _export_prim(stage, prim):
    """Write the prim and everything below it as a standalone USD file in <library>/prototypes (flattened, so references and overrides are folded in; the name carries a hash of the content, so the same prototype
    is the same file and a different prototype of the same name is another one). Returns (file, prim path)."""
    flat = stage.Flatten(addSourceFileComment=False)
    leaf = _clean_leaf(prim.GetName())
    layer = Sdf.Layer.CreateAnonymous('.usda')
    Sdf.CopySpec(flat, prim.GetPath(), layer, Sdf.Path('/' + leaf))
    layer.defaultPrim = leaf
    for key in ('upAxis', 'metersPerUnit'):
        if stage.HasMetadata(key):
            layer.pseudoRoot.SetInfo(key, stage.GetMetadata(key))
    text = layer.ExportToString()
    digest = hashlib.sha1(text.encode('utf8')).hexdigest()[:8]
    folder = os.path.join(library_dir(), 'prototypes')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, '%s_%s.usda' % (leaf, digest)).replace('\\', '/')
    if not os.path.isfile(path):
        with open(path, 'w', encoding='utf8') as handle:
            handle.write(text)
    return path, '/' + leaf

def proto_library_entry(node, item):
    """(file, prim path, how) of one scanned prototype: how is 'file' (the original USD file) or 'exported' (written to the library folder)."""
    stage = proto_socket_stage(node, item['socket'])
    prim = stage.GetPrimAtPath(item['path'])
    found = _usd_file_of(prim)
    if found is not None:
        return found[0], found[1], 'file'
    path, target = _export_prim(stage, prim)
    return path, target, 'exported'

# ---- the Prototype Bank side
def _bank_rows(node):
    rows = []
    for r in range(1, node.evalParm('protos') + 1):
        t = node.evalParm('proto_type%d' % r)
        rows.append(dict(row=r, type=t, on=node.evalParm('proto_on%d' % r), socket=node.evalParm('proto_input%d' % r) if t == PROTO_ROW_INPUT else -1,
                         path=(node.evalParm('proto_inprim%d' % r) if t == PROTO_ROW_INPUT else node.evalParm('proto_prim%d' % r) if t == 0 else '').strip()))
    return rows

def _blank_row(node, row):
    """A row that holds nothing the artist chose: the default Prim Path row (empty, the built-in sphere, or the default crate path of Arraytron) or an Input Connection with no Prim Path."""
    t = node.evalParm('proto_type%d' % row)
    if t == PROTO_ROW_INPUT:
        return not node.evalParm('proto_inprim%d' % row).strip()
    if t == 0:
        parm = node.parm('proto_prim%d' % row)
        return node.evalParm('proto_prim%d' % row).strip() in ('', parm.parmTemplate().defaultValue()[0])
    return False

def proto_import(node, library=None, replace=None):
    """Import every prototype wired into the Prototype Inputs: one Input Connection row per prototype in the Prototype Bank (Prim Path set, Weight / Scale / Scale Random / Rotation Offset at their defaults,
    ready to edit) and, when `library` is true, one asset per prototype in the Asset Library (category Imported). `replace`: rebuild the bank from the inputs only (the rows that were there go). Without it the
    rows already there stay as they are (a prototype that is already a row is not added twice, the artist's weights stay), blank rows are reused, the new ones follow. library / replace default to the
    toggles of the node (proto_import_library, proto_import_replace). One undo step. Returns dict(added=[rows], kept=[rows], library=[asset names], exported=[names], found=n)."""
    if library is None:
        library = bool(node.evalParm('proto_import_library')) if node.parm('proto_import_library') is not None else True
    if replace is None:
        replace = bool(node.evalParm('proto_import_replace')) if node.parm('proto_import_replace') is not None else False
    found = proto_scan(node)
    if not found:
        raise hou.NodeError('The Prototype Inputs hold nothing that can be drawn (no geometry was found).')
    result = dict(added=[], kept=[], library=[], exported=[], found=len(found), known=0)
    with hou.undos.group('Import Prototype Inputs'):
        if replace:
            node.parm('protos').set(0)
        rows = _bank_rows(node)
        taken = {(r['socket'], r['path']) for r in rows if r['type'] == PROTO_ROW_INPUT and r['path']}
        taken_paths = {r['path'] for r in rows if r['path']}
        blanks = [r['row'] for r in rows if _blank_row(node, r['row'])]
        count = node.evalParm('protos')
        for item in found:
            if (item['socket'], item['path']) in taken or item['path'] in taken_paths:
                match = [r['row'] for r in rows if r['path'] == item['path']]
                result['kept'].extend(match[:1])
                continue
            if blanks:
                row = blanks.pop(0)
            else:
                count += 1
                node.parm('protos').set(count)
                row = count
            node.parm('proto_type%d' % row).set(PROTO_ROW_INPUT)
            node.parm('proto_input%d' % row).set(item['socket'])
            node.parm('proto_inprim%d' % row).set(item['path'])
            node.parm('proto_on%d' % row).set(1)
            taken.add((item['socket'], item['path']))
            taken_paths.add(item['path'])
            result['added'].append(row)
        if library:
            data = load_library()
            for item in found:
                try:
                    file, prim, how = proto_library_entry(node, item)
                except Exception as exc:                       # one prototype that cannot be written must not stop the others
                    result.setdefault('library_errors', []).append('%s: %s' % (item['name'], exc))
                    continue
                existed = any(a['file'] == file and a.get('prim', '') == prim for a in data['assets'])
                asset = add_asset(data, file, name=item['name'], category=None if existed else PROTO_LIBRARY_CATEGORY, prim=prim, tags=('imported',), source='prototype input')
                if not existed:
                    result['library'].append(asset['name'])
                else:
                    result['known'] += 1
                if how == 'exported':
                    result['exported'].append(asset['name'])
            save_library(data)
    return result

def proto_import_text(result):
    """The sentence the button shows."""
    parts = ['%d prototype%s found' % (result['found'], '' if result['found'] == 1 else 's')]
    parts.append('%d added to the bank' % len(result['added']))
    if result['kept']:
        parts.append('%d already there' % len(result['kept']))
    if result['library']:
        parts.append('%d new in the Asset Library (category %s)' % (len(result['library']), PROTO_LIBRARY_CATEGORY))
    if result.get('known'):
        parts.append('%d already in the Asset Library' % result['known'])
    if result.get('library_errors'):
        parts.append('library: %s' % '; '.join(result['library_errors'][:2]))
    return ', '.join(parts) + '.'

def proto_import_button(node):
    """The Import Prototype Inputs button: the import, then a message (a node error becomes a message box, nothing is changed)."""
    try:
        result = proto_import(node)
    except hou.NodeError as exc:
        text = exc.instanceMessage() if hasattr(exc, 'instanceMessage') else str(exc)
        hou.ui.displayMessage(text, severity=hou.severityType.Warning, title='Import Prototype Inputs') if hou.isUIAvailable() else print(text)
        return None
    text = proto_import_text(result)
    if hou.isUIAvailable():
        hou.ui.setStatusMessage(text)
    else:
        print(text)
    return result
