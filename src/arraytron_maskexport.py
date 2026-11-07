
# ---- Save, cache and export the mask (src/arraytron_maskexport.py, v1.32.0): the Mask section, Save, Cache And Export.
# Any Mask Source can be written out as an image (the RAW mask weight, before Invert and the remap, 16 bit grey PNG or a float EXR, looked at from above over an extent), baked (written and then used as the
# Image source with a Top projection, so the mask no longer needs the paint or the noise: a frozen, fast, shareable cache), and the two painted sources (Painted, Houdini Paint) can be saved to a file
# (JSON: the brush stamps, or the baked Houdini paint map) and loaded back into this or another node.
import json, os, struct, zlib

MASK_FILE_TAG = 'arraytron-mask'
MASK_EXPORT_MAX = 8192

def png16_bytes(grid):
    """The bytes of a 16 bit greyscale PNG of grid (rows = top to bottom, values 0..1)."""
    q = np.round(np.clip(np.asarray(grid, dtype=np.float64), 0.0, 1.0) * 65535.0).astype('>u2')
    h, w = q.shape
    raw = b''.join(b'\x00' + q[row].tobytes() for row in range(h))
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 16, 0, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')

def mask_export_extent(asset, points=None):
    """(centre x, centre z, size x, size z) of the area the mask is written over. Extent Automatic: the painted extent for the Painted source, the baked map for Houdini Paint, else the X and Z extent of the
    generated points; plus a tenth of margin. Custom: the Center and Size of the Image projection (mask_center, mask_size)."""
    if asset.evalParm('mask_export_extent') == 1:
        c = asset.evalParmTuple('mask_center')
        s = asset.evalParmTuple('mask_size')
        return float(c[0]), float(c[1]), max(float(s[0]), 1e-6), max(float(s[1]), 1e-6)
    source = asset.evalParm('mask_source')
    lo = hi = None
    if source == 4:
        stamps = maskpaint_data(asset)
        if len(stamps):
            r = stamps[:, 4]
            lo = np.array([np.min(stamps[:, 1] - r), np.min(stamps[:, 3] - r)])
            hi = np.array([np.max(stamps[:, 1] + r), np.max(stamps[:, 3] + r)])
    elif source == 5:
        got = hpaint_decode(asset.evalParm('mask_hpaint_data'))
        if got is not None:
            grid, (x0, z0, cell, nx, nz) = got
            lo = np.array([x0, z0])
            hi = np.array([x0 + cell * (nx - 1), z0 + cell * (nz - 1)])
    if lo is None:
        if points is None:
            points = mask_export_points(asset)
        if len(points):
            lo = points[:, [0, 2]].min(axis=0)
            hi = points[:, [0, 2]].max(axis=0)
        else:
            lo, hi = np.array([-5.0, -5.0]), np.array([5.0, 5.0])
    size = np.maximum(hi - lo, 1e-3) * 1.1
    c = (lo + hi) * 0.5
    return float(c[0]), float(c[1]), float(size[0]), float(size[1])

def mask_export_points(asset):
    """The generated points (before the mask) as (n, 3), or an empty array."""
    try:
        g = asset.node('USD_COMPILER/DISTRIBUTION_GENERATOR').geometry()
        if g is not None and g.intrinsicValue('pointcount'):
            return np.array(g.pointFloatAttribValues('P')).reshape(-1, 3)
    except hou.Error:
        pass
    return np.zeros((0, 3))

def mask_raster(asset, extent, res, y=0.0):
    """The raw mask weight (before Invert and the remap) over the extent as a grid (rows = top to bottom, i.e. -Z to +Z, columns = -X to +X), the longer side res pixels."""
    cx, cz, sx, sz = extent
    res = int(min(max(res, 8), MASK_EXPORT_MAX))
    w = res if sx >= sz else max(int(round(res * sx / sz)), 2)
    h = res if sz > sx else max(int(round(res * sz / sx)), 2)
    xs = cx + ((np.arange(w) + 0.5) / w - 0.5) * sx
    zs = cz + ((np.arange(h) + 0.5) / h - 0.5) * sz
    X, Z = np.meshgrid(xs, zs)
    P = np.stack([X.ravel(), np.full(X.size, float(y)), Z.ravel()], axis=1)
    return np.clip(np.asarray(mask_values(asset, P, np.arange(len(P))), dtype=np.float64).reshape(h, w), 0.0, 1.0)

def mask_export_path(asset):
    path = asset.evalParm('mask_export_path').strip()
    if not path:
        raise hou.NodeError('The mask file is empty: type a path such as C:/folder/arraytron_mask.png.')
    return hou.text.expandString(path)

def mask_write_image(path, grid):
    """Write the grid (0..1) as an image: .png (16 bit grey, no library needed) or any other format OpenImageIO writes (.exr, .tif ...)."""
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    if path.lower().endswith('.png'):
        with open(path, 'wb') as f:
            f.write(png16_bytes(grid))
        return
    import OpenImageIO as oiio
    h, w = grid.shape
    buf = oiio.ImageBuf(oiio.ImageSpec(w, h, 1, oiio.FLOAT))
    buf.set_pixels(oiio.ROI(0, w, 0, h, 0, 1, 0, 1), np.ascontiguousarray(grid, dtype=np.float32))
    if not buf.write(path):
        raise hou.NodeError('Cannot write %s: %s' % (path, buf.geterror()))

def mask_export(asset, path=None):
    """Export Mask Image button: the raw mask over the extent as an image. Returns the report {path, size, extent}."""
    if asset.evalParm('mask_source') == 0:
        raise hou.NodeError('There is no mask to export: choose a Mask Source.')
    path = path or mask_export_path(asset)
    pts = mask_export_points(asset)
    extent = mask_export_extent(asset, pts)
    grid = mask_raster(asset, extent, asset.evalParm('mask_export_res'), float(pts[:, 1].mean()) if len(pts) else 0.0)
    mask_write_image(path, grid)
    report = dict(path=path, size=(grid.shape[1], grid.shape[0]), extent=extent)
    text = 'Wrote %s (%d x %d), centre (%.4g, %.4g), size (%.4g, %.4g).' % (path, grid.shape[1], grid.shape[0], extent[0], extent[1], extent[2], extent[3])
    if asset.parm('mask_export_info') is not None:
        asset.parm('mask_export_info').set(text)
    if hou.isUIAvailable():
        hou.ui.setStatusMessage(text)
    return report

def mask_bake(asset):
    """Bake To Image button: write the mask (as Export Mask Image) and make that image the Mask Source (Image, Top projection over the same extent, clamped at the border), so the paint or the noise is no
    longer evaluated: a frozen, fast mask that can be shared. Invert, Low / High and the other remap settings keep working on it. One undo step."""
    with hou.undos.group('Arraytron bake mask'):
        report = mask_export(asset)
        c = report['extent']
        asset.parm('mask_source').set(2)
        asset.parm('mask_image').set(report['path'])
        asset.parm('mask_proj').set(0)
        asset.parm('mask_channel').set(0)
        asset.parm('mask_outside').set(2)
        asset.parmTuple('mask_center').set((c[0], c[1]))
        asset.parmTuple('mask_size').set((c[2], c[3]))
    return report

def mask_save(asset, path=None):
    """Save Paint button: the painted mask (the stamps) or the Houdini paint map to a JSON file, with the settings that go with it. Returns the path."""
    source = asset.evalParm('mask_source')
    if source == 4:
        data = dict(kind='painted', paint=asset.evalParm('mask_paint_data'))
    elif source == 5:
        data = dict(kind='houdini', paint=asset.evalParm('mask_hpaint_data'))
    else:
        raise hou.NodeError('Save Paint needs the Mask Source Painted or Houdini Paint. Use Export Mask Image for the other sources.')
    if not data['paint']:
        raise hou.NodeError('Nothing is painted yet.')
    data.update({'tag': MASK_FILE_TAG, 'v': 1, 'base': asset.evalParm('mask_paint_base'), 'res': asset.evalParm('mask_paint_res'), 'blur': asset.evalParm('mask_paint_blur')})
    path = path or mask_export_path(asset)
    if not path.lower().endswith('.json'):
        path = os.path.splitext(path)[0] + '.json'
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, 'w') as f:
        json.dump(data, f)
    text = 'Saved the %s paint to %s.' % (data['kind'], path)
    if asset.parm('mask_export_info') is not None:
        asset.parm('mask_export_info').set(text)
    if hou.isUIAvailable():
        hou.ui.setStatusMessage(text)
    return path

def mask_load(asset, path=None):
    """Load Paint button: read a file written by Save Paint into this node (the Mask Source becomes Painted or Houdini Paint). One undo step. Returns the kind."""
    path = path or mask_export_path(asset)
    if not path.lower().endswith('.json') and os.path.isfile(os.path.splitext(path)[0] + '.json'):
        path = os.path.splitext(path)[0] + '.json'
    if not os.path.isfile(path):
        raise hou.NodeError('The file %s does not exist.' % path)
    try:
        with open(path) as f:
            data = json.load(f)
        if data.get('tag') != MASK_FILE_TAG or data['kind'] not in ('painted', 'houdini'):
            raise ValueError('not an Arraytron mask file')
        if data['kind'] == 'painted':
            maskpaint_decode(data['paint'])
        else:
            hpaint_decode(data['paint'])
    except (ValueError, KeyError, TypeError) as error:
        raise hou.NodeError('%s cannot be read (%s).' % (path, error))
    with hou.undos.group('Arraytron load mask'):
        if data['kind'] == 'painted':
            asset.parm('mask_paint_data').set(data['paint'])
            asset.parm('mask_source').set(4)
        else:
            asset.parm('mask_hpaint_data').set(data['paint'])
            asset.parm('mask_source').set(5)
        asset.parm('mask_paint_base').set(data.get('base', 0.0))
        asset.parm('mask_paint_res').set(data.get('res', asset.evalParm('mask_paint_res')))
        asset.parm('mask_paint_blur').set(data.get('blur', 0.0))
    text = 'Loaded the %s paint from %s.' % (data['kind'], path)
    if asset.parm('mask_export_info') is not None:
        asset.parm('mask_export_info').set(text)
    if hou.isUIAvailable():
        hou.ui.setStatusMessage(text)
    return data['kind']
