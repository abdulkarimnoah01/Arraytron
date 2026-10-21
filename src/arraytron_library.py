
# ---- Asset Library: a local catalogue of USD assets with custom categories (src/arraytron_library.py)
# The library is one JSON file per user (default Documents/Arraytron/library/library.json, or the folder in ARRAYTRON_LIBRARY) next to a thumbs/ folder. An asset is a USD file (plus an optional
# prim inside it) with a name, a category, tags and a thumbnail. Assets come from the Solaris Asset Gallery (its items, names and thumbnails), from USD files or from a folder of them, and are
# added to the node's Prototype Bank as "USD File" rows. This code never touches the points, only the Prototype Bank parameters when you ask for it.
import json, os, re, time, uuid
LIBRARY_VERSION = 1
DEFAULT_CATEGORIES = ('Trees', 'Plants', 'Rocks', 'Props')
UNCATEGORIZED = 'Uncategorized'
USD_SUFFIXES = ('.usd', '.usda', '.usdc', '.usdz')

def library_dir():
    """The folder of the library: ARRAYTRON_LIBRARY, else Documents/Arraytron/library."""
    folder = os.environ.get('ARRAYTRON_LIBRARY')
    if not folder:
        folder = os.path.join(os.path.expanduser('~'), 'Documents', 'Arraytron', 'library')
    return folder

def library_file(folder=None):
    return os.path.join(folder or library_dir(), 'library.json')

def empty_library():
    return {'version': LIBRARY_VERSION, 'categories': list(DEFAULT_CATEGORIES), 'assets': []}

def load_library(folder=None):
    """The library as a dict. A missing file is a new library; a broken file is kept aside (library.json.broken) and a new library starts, so a bad file never blocks the panel."""
    path = library_file(folder)
    if not os.path.exists(path):
        return empty_library()
    try:
        with open(path, 'r', encoding='utf8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or not isinstance(data.get('assets'), list) or not isinstance(data.get('categories'), list):
            raise ValueError('not an Arraytron library')
    except (ValueError, OSError):
        try:
            os.replace(path, path + '.broken')
        except OSError:
            pass
        return empty_library()
    data.setdefault('version', LIBRARY_VERSION)
    return data

def save_library(data, folder=None):
    """Write the library atomically (a temp file, then a rename), so an interrupted save never leaves a half-written file."""
    folder = folder or library_dir()
    os.makedirs(folder, exist_ok=True)
    path = library_file(folder)
    temp = path + '.tmp'
    with open(temp, 'w', encoding='utf8') as handle:
        json.dump(data, handle, indent=1, sort_keys=True)
    os.replace(temp, path)
    return path

# ---- categories
def clean_name(name):
    name = re.sub(r'\s+', ' ', str(name or '')).strip()
    return name[:40]

def add_category(data, name):
    name = clean_name(name)
    if not name or name.lower() == UNCATEGORIZED.lower():
        return None
    for existing in data['categories']:
        if existing.lower() == name.lower():
            return existing
    data['categories'].append(name)
    return name

def rename_category(data, old, new):
    new = clean_name(new)
    if old not in data['categories'] or not new or new.lower() == UNCATEGORIZED.lower():
        return False
    if any(c.lower() == new.lower() and c != old for c in data['categories']):
        return False
    data['categories'] = [new if c == old else c for c in data['categories']]
    for asset in data['assets']:
        if asset.get('category') == old:
            asset['category'] = new
    return True

def delete_category(data, name):
    """Remove a category; its assets are not deleted, they move to Uncategorized."""
    if name not in data['categories']:
        return False
    data['categories'] = [c for c in data['categories'] if c != name]
    for asset in data['assets']:
        if asset.get('category') == name:
            asset['category'] = UNCATEGORIZED
    return True

def move_category(data, name, offset):
    categories = data['categories']
    if name not in categories:
        return False
    index = categories.index(name)
    target = min(max(index + offset, 0), len(categories) - 1)
    categories.insert(target, categories.pop(index))
    return True

# ---- assets
def default_prim_of(file_path):
    """The default prim of a USD file ('' when it has none or the file cannot be read)."""
    try:
        from pxr import Usd
        stage = Usd.Stage.Open(file_path, Usd.Stage.LoadNone)
        prim = stage.GetDefaultPrim()
        return str(prim.GetPath()) if prim and prim.IsValid() else ''
    except Exception:
        return ''

def add_asset(data, file_path, name=None, category=None, prim='', tags=(), thumb='', source='file'):
    """Add an asset; the same file and prim in the same library is not added twice (the existing entry is returned, its category updated when one is given)."""
    file_path = str(file_path).replace('\\', '/')
    for asset in data['assets']:
        if asset['file'] == file_path and asset.get('prim', '') == prim:
            if category:
                asset['category'] = add_category(data, category) or asset['category']
            return asset
    if category:
        category = add_category(data, category) or UNCATEGORIZED
    else:
        category = UNCATEGORIZED
    asset = {'id': uuid.uuid4().hex[:12], 'name': clean_name(name) or os.path.splitext(os.path.basename(file_path))[0], 'category': category, 'file': file_path, 'prim': prim or '',
             'tags': sorted({clean_name(t).lower() for t in tags if clean_name(t)}), 'thumb': thumb or '', 'source': source, 'added': int(time.time())}
    data['assets'].append(asset)
    return asset

def find_asset(data, asset_id):
    for asset in data['assets']:
        if asset['id'] == asset_id:
            return asset
    return None

def remove_asset(data, asset_id, folder=None):
    asset = find_asset(data, asset_id)
    if asset is None:
        return False
    data['assets'].remove(asset)
    thumb = asset.get('thumb')
    if thumb and os.path.isabs(thumb) is False:
        try:
            os.remove(os.path.join(folder or library_dir(), thumb))
        except OSError:
            pass
    return True

def set_asset(data, asset_id, **changes):
    asset = find_asset(data, asset_id)
    if asset is None:
        return False
    if 'category' in changes:
        category = changes['category']
        asset['category'] = (add_category(data, category) or UNCATEGORIZED) if category and category != UNCATEGORIZED else UNCATEGORIZED
    if 'name' in changes and clean_name(changes['name']):
        asset['name'] = clean_name(changes['name'])
    if 'tags' in changes:
        asset['tags'] = sorted({clean_name(t).lower() for t in changes['tags'] if clean_name(t)})
    return True

def query_assets(data, category=None, text=''):
    """Assets of one category (None = all) whose name, tags or file name contain every word of the search text, sorted by name."""
    words = [w for w in re.split(r'\s+', str(text or '').lower()) if w]
    found = []
    for asset in data['assets']:
        if category and asset.get('category') != category:
            continue
        hay = ' '.join([asset['name'], ' '.join(asset.get('tags', ())), os.path.basename(asset['file'])]).lower()
        if all(w in hay for w in words):
            found.append(asset)
    return sorted(found, key=lambda a: a['name'].lower())

# ---- importing
def save_thumbnail(data_bytes, asset_id, folder=None):
    """Store thumbnail image bytes as thumbs/<id>.png (or .jpg by content) and return the relative path."""
    if not data_bytes:
        return ''
    folder = folder or library_dir()
    thumbs = os.path.join(folder, 'thumbs')
    os.makedirs(thumbs, exist_ok=True)
    extension = '.png' if bytes(data_bytes[:4]) == b'\x89PNG' else '.jpg'
    relative = 'thumbs/%s%s' % (asset_id, extension)
    with open(os.path.join(folder, relative), 'wb') as handle:
        handle.write(bytes(data_bytes))
    return relative

def gallery_assets(source):
    """The USD assets of an Asset Gallery data source (hou.AssetGalleryDataSource or anything with the same methods) as dicts: id, name, file, tags, thumbnail bytes. Items that are not USD files
    (snapshots, LOP node references) are skipped."""
    found = []
    for item in source.itemIds():
        try:
            path = source.filePath(item)
        except Exception:
            continue
        if not path or not str(path).lower().endswith(USD_SUFFIXES):
            continue
        try:
            thumb = source.thumbnail(item)
        except Exception:
            thumb = b''
        try:
            tags = list(source.tags(item))
        except Exception:
            tags = []
        found.append({'id': item, 'name': source.label(item) or os.path.splitext(os.path.basename(path))[0], 'file': str(path).replace('\\', '/'), 'tags': tags, 'thumb': thumb})
    return found

def import_gallery(data, source, item_ids=None, category=None, folder=None):
    """Add Asset Gallery items (all of them, or the given ids) to the library under a category. Returns the added or updated assets."""
    out = []
    for item in gallery_assets(source):
        if item_ids is not None and item['id'] not in item_ids:
            continue
        asset = add_asset(data, item['file'], name=item['name'], category=category, prim=default_prim_of(item['file']), tags=item['tags'], source='gallery')
        if item['thumb'] and not asset.get('thumb'):
            asset['thumb'] = save_thumbnail(item['thumb'], asset['id'], folder)
        out.append(asset)
    return out

def usd_files_in(folder, recursive=True):
    found = []
    for root, dirs, files in os.walk(folder):
        for name in sorted(files):
            if name.lower().endswith(USD_SUFFIXES):
                found.append(os.path.join(root, name).replace('\\', '/'))
        if not recursive:
            break
    return found

def import_files(data, paths, category=None):
    """Add USD files (or every USD file under a folder) to the library; the name is the file name, the prim the file's default prim."""
    out = []
    for path in paths:
        files = usd_files_in(path) if os.path.isdir(path) else ([path] if str(path).lower().endswith(USD_SUFFIXES) else [])
        for file_path in files:
            out.append(add_asset(data, file_path, category=category, prim=default_prim_of(file_path)))
    return out

# ---- using an asset
def library_bank_rows(node):
    """The Prototype Bank rows of an Arraytron node as (row number, type, file, prim) for the USD File rows."""
    rows = []
    for index in range(1, node.evalParm('protos') + 1):
        rows.append((index, node.evalParm('proto_type%d' % index), node.evalParm('proto_file%d' % index), node.evalParm('proto_fileprim%d' % index)))
    return rows

def add_to_bank(node, asset, row=None):
    """Put a library asset into the Prototype Bank of an Arraytron node as a USD File row: a new row at the end, or the given row number replaced. Returns the row number.
    A bank that only holds the untouched default row (a Prim Path row with the default crate path) gets that row replaced instead of a second row. Undoable (one undo step)."""
    import hou
    with hou.undos.group('Arraytron: add %s to the Prototype Bank' % asset['name']):
        count = node.evalParm('protos')
        if row is None:
            if count == 1 and node.evalParm('proto_type1') == 0 and node.evalParm('proto_prim1') == node.parm('proto_prim1').parmTemplate().defaultValue()[0]:
                row = 1
            else:
                node.parm('protos').set(count + 1)
                row = count + 1
        node.parm('proto_type%d' % row).set(2)
        node.parm('proto_file%d' % row).set(asset['file'])
        node.parm('proto_fileprim%d' % row).set(asset.get('prim', ''))
        node.parm('proto_on%d' % row).set(1)
    return row
