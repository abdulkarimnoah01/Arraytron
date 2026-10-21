"""Render check of the LOD generator on Houdini's Rubber Toy (Test Geometry): hython tools/lodgen_render_check.py <version> [--instanceable 0|1] [--out folder]
The toy (textured with a MaterialX network) stands four times in a row, once as the hero and once at every generated level (LOD 1, LOD 2, Proxy: the camera LOD distances switch every
instance to its level at once), seen by a long-lens camera and rendered with Karma CPU. Every toy is cut out with the alpha of the image and its mean colour is compared with the hero's:
a level that lost its textures renders black (a small fraction of the hero's brightness). Prints one line per level and exits with 1 when a level is not within the tolerance of the hero.
Needs a Houdini that can render with Karma (a license). Run it with the release you want to check: the same script shows the old behaviour (v1.20.0 renders black levels) and the fix."""
from pathlib import Path
import argparse, sys, tempfile
import hou, loptoolutils
import numpy as np
from pxr import Usd, UsdGeom
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import versions, demo_compat

parser = argparse.ArgumentParser()
parser.add_argument('version')
parser.add_argument('--instanceable', type=int, default=1)
parser.add_argument('--out', default='')
parser.add_argument('--tolerance', type=float, default=0.35)
args = parser.parse_args()
VID = versions.resolve(args.version)
out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix='arraytron_lodcheck_'))
out_dir.mkdir(parents=True, exist_ok=True)
hou.hipFile.clear(suppress_save_prompt=True)
hou.hda.installFile(str(versions.hda(VID)), force_use_assets=True)
stage = hou.node('/stage')

toy = stage.createNode('assetreference', 'rubbertoy')
loptoolutils.referenceTestAsset(toy, 'rubbertoy')
toy.parm('instanceable').set(int(args.instanceable))
toy.parm('primpath').set('/rubbertoy')
cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render'])
box = cache.ComputeWorldBound(toy.stage().GetPrimAtPath('/rubbertoy')).ComputeAlignedRange()
size = box.GetSize()
scale = 2.2 / max(size[0], size[1], size[2])
center = (box.GetMin() + box.GetMax()) * 0.5
print('toy size', tuple(round(x, 3) for x in size), 'scale', round(scale, 4))

camera = stage.createNode('camera', 'render_camera')
camera.setInput(0, toy)
camera.parm('primpath').set('/World/Camera')
camera.parm('projection').set('perspective')               # a long lens far away: the four toys, side by side at the same depth, are seen without distortion (12 units across)
camera.parm('focalLength').set(180)
camera.parm('horizontalAperture').set(36)
camera.parmTuple('aspectratio').set((16, 5))
camera.parmTuple('t').set((0.0, 1.0, 60.0))
camera.parm('lookatenable').set(1)
camera.parmTuple('lookatposition').set((0.0, 1.0, 0.0))
camera.parm('clippingRange1').set(0.1)
camera.parm('clippingRange2').set(200)

source = camera
levels = (('hero', -4.5, (1e6, 1e6, 1e6)), ('lod1', -1.5, (0.0, 1e6, 1e6)), ('lod2', 1.5, (0.0, 0.0, 1e6)), ('proxy', 4.5, (0.0, 0.0, 0.0)))
for name, x, thresholds in levels:
    node = stage.createNode(versions.type_name(VID), 'Arraytron_' + name)
    node.setInput(0, source)
    node.parm('outputpath').set('/World/' + name)
    node.parm('protos').set(1)
    node.parm('proto_prim1').set('/rubbertoy')
    node.parm('proto_scale1').set(scale)
    node.parm('mode').set(0)
    node.parm('line_count').set(1)
    node.parm('bound_tx').set(x)
    node.parm('bound_ty').set(1.0 - scale * float(center[1]))
    node.parm('cam_on').set(1)
    node.parm('cam_prim').set('/World/Camera')
    node.parm('cam_frustum').set(0)
    node.parm('cam_lod').set(1)
    node.parm('lod_by').set(0)
    node.parm('lodg_on').set(1)
    node.parm('lodg_1').set(40.0)
    node.parm('lodg_2').set(12.0)
    node.parm('lodg_3').set(3.0)
    for parm, value in zip(('lod_d1', 'lod_d2', 'lod_d3'), thresholds):
        node.parm(parm).set(value)
    node.parm('scale_random_mode').set(0)
    node.parm('scale_random').set(0.0)
    source = node

def intensity(light, value):
    light.parm('xn__inputsintensity_control_jeb').set('set')
    light.parm('xn__inputsintensity_i0a').set(value)
dome = stage.createNode('domelight', 'render_dome')
dome.setInput(0, source)
intensity(dome, 1.0)
sun = stage.createNode('distantlight', 'render_sun')
sun.setInput(0, dome)
intensity(sun, 2.0)
sun.parmTuple('r').set((-40, 30, 0))
settings = demo_compat.karma_settings(stage, sun)
settings.parm('engine').set('cpu')
settings.parm('camera').set('/World/Camera')
settings.parm('pathtracedsamples').set(24)
picture = out_dir / ('lodcheck_%s_inst%d.png' % (VID, args.instanceable))
settings.parm('picture').set(str(picture).replace('\\', '/'))
settings.parm('res_mode').set('manual')
settings.parm('res_mode').pressButton()
demo_compat.set_resolution(settings, (1280, 400))

rs = settings.stage()
for name, x, thresholds in levels:
    inst = UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/' + name))
    print(name, 'prototype index', list(inst.GetProtoIndicesAttr().Get(1)))
rop = stage.createNode('usdrender_rop', 'RENDER')
rop.setInput(0, settings)
rop.parm('rendersettings').set(settings.parm('primpath').eval() if settings.parm('primpath') is not None else '/Render/karma_xpu')
rop.render()
if not picture.exists():
    sys.exit('the render wrote nothing: %s' % picture)

from PIL import Image
img = np.asarray(Image.open(picture).convert('RGBA'), dtype=np.float64) / 255.0
H, W = img.shape[:2]
print('image', W, 'x', H, 'to', picture)
stats = {}
for index, (name, x, thresholds) in enumerate(levels):
    x0 = int(W * (index / 4.0)); x1 = int(W * ((index + 1) / 4.0))
    cell = img[:, x0:x1]
    mask = cell[:, :, 3] > 0.5
    pixels = cell[:, :, :3][mask]
    stats[name] = (mask.mean(), pixels.mean(axis=0) if len(pixels) else np.zeros(3))
hero_cover, hero_rgb = stats['hero']
print('%-6s coverage %.3f  mean RGB %s' % ('hero', hero_cover, np.round(hero_rgb, 3)))
bad = []
if hero_cover < 0.02:
    bad.append('hero is not visible')
for name in ('lod1', 'lod2', 'proxy'):
    cover, rgb = stats[name]
    lum_ratio = float(rgb.mean() / max(hero_rgb.mean(), 1e-9))
    worst = float(np.max(np.abs(rgb - hero_rgb) / np.maximum(hero_rgb, 0.02)))
    verdict = 'ok' if (cover > 0.5 * hero_cover and worst <= args.tolerance) else 'BAD'
    print('%-6s coverage %.3f  mean RGB %s  brightness vs hero %.2f  worst channel difference %.2f  %s' % (name, cover, np.round(rgb, 3), lum_ratio, worst, verdict))
    if verdict != 'ok':
        bad.append(name)
print('RESULT', 'FAIL ' + ','.join(bad) if bad else 'PASS')
sys.exit(1 if bad else 0)
