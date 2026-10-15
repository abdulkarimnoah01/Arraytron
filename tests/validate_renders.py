"""Execute Karma XPU and validate fresh images against composed demo USD."""
from pathlib import Path
import subprocess,json,hashlib
import numpy as np
import OpenImageIO as oiio
from pxr import Usd,UsdGeom
ROOT=Path(__file__).resolve().parents[1]
HUSK=Path('C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/husk.exe')
evidence={'renderer':'Karma XPU','commands':[],'checks':[]}
def render(name,usd,width,height,samples=64):
    dest=ROOT/'renders'/f'{name}.exr'
    cmd=[str(HUSK),'--engine','xpu','--res',str(width),str(height),'--camera','/World/Camera','--pixel-samples',str(samples),'-V','2','--output',str(dest),str(usd)]
    with (ROOT/'renders'/f'{name}.log').open('w',encoding='utf-8') as log:
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    assert result.returncode==0
    image=oiio.ImageBuf(str(dest));assert image.read(),image.geterror()
    pixels=np.asarray(image.get_pixels(oiio.FLOAT))
    assert pixels.shape[:2]==(height,width) and np.isfinite(pixels).all()
    assert pixels[:,:,:3].max()>.1
    preview=oiio.ImageBufAlgo.colorconvert(image,'linear','sRGB');assert preview.write(str(dest.with_suffix('.png')))
    evidence['commands'].append({'argv':cmd,'exit_code':result.returncode,'image_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
    return pixels
import sys
sys.path.insert(0,str(ROOT/'tools'))
import versions
V1=versions.ARCHIVE/'Arraytron_v0.1.0'
line=render('arraytron_v0.1.0_line_xpu',Path(str(V1)+'_line_render.usda'),1000,240)
columns=np.max(line[:,:,:3],axis=(0,2))>.05
runs=np.count_nonzero(columns & ~np.concatenate(([False],columns[:-1])))
assert runs==10,int(runs)
evidence['checks'].append('All ten separated Line instances produce distinct rendered silhouettes')
s=Usd.Stage.Open(str(Path(str(V1)+'_demo_render.usda')))
for path,count in (('/World/Arraytron',10),('/World/ArraytronArea',60)):
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(path));assert len(pi.GetPositionsAttr().Get(1))==count
    assert UsdGeom.Imageable(s.GetPrimAtPath(pi.GetPrototypesRel().GetTargets()[0])).ComputeVisibility()=='inherited'
demo=render('arraytron_v0.1.0_demo_xpu',Path(str(V1)+'_demo_render.usda'),1200,800)
UsdGeom.Imageable(s.GetPrimAtPath('/World/ArraytronArea')).CreateVisibilityAttr().Set('invisible')
s.Export(str(ROOT/'tests/Arraytron_v0.1.0_demo_without_area.usda'))
baseline=render('arraytron_v0.1.0_demo_without_area',ROOT/'tests/Arraytron_v0.1.0_demo_without_area.usda',1200,800)
changed=int(np.count_nonzero(np.max(np.abs(demo[:,:,:3]-baseline[:,:,:3]),axis=2)>.05))
assert changed>10000,changed
evidence['checks'].append(f'Area contributes visible geometry to the XPU demo: {changed} changed pixels versus hidden-Area baseline')
evidence['checks'].append('Fresh finite 1000x240 Line and 1200x800 reference-asset demo images, all husk calls exit 0')
evidence['passed']=True
(ROOT/'tests/render_validation_v0.1.0.json').write_text(json.dumps(evidence,indent=2))
print(json.dumps({'passed':True,'checks':evidence['checks']},indent=2))
