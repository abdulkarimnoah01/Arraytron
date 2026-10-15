"""Render the Grow demo frames with Karma XPU and compose a contact sheet: hython tools/render_grow_sheet.py [version] [samples]
Needs the per-frame render USDs from tools/build_demo_grow_v052.py. Writes renders/arraytron_<version>_grow_demo_xpu.png (3 x 2 frames, labelled)."""
from pathlib import Path
import subprocess, sys, re, time
import numpy as np
import OpenImageIO as oiio
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT);SAMPLES=int(sys.argv[2]) if len(sys.argv)>2 else 96
HUSK=Path('C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/husk.exe')
base=versions.render_usd(VID,'grow');files=sorted(base.parent.glob(base.name.replace('_render.usda','_render_f*.usda')))
assert files,'run build_demo_grow first'
W,H=800,450;tiles=[];t0=time.time()
for usd in files:
    frame=int(re.search(r'_f(\d+)\.usda',usd.name).group(1));exr=ROOT/'renders'/('grow_tmp_%04d.exr'%frame)
    r=subprocess.run([str(HUSK),'--engine','xpu','--res',str(W),str(H),'--camera','/World/Camera','--pixel-samples',str(SAMPLES),'-V','1','--output',str(exr),str(usd)],capture_output=True,timeout=1800)
    assert r.returncode==0,(frame,r.returncode)
    img=oiio.ImageBuf(str(exr));assert img.read();px=np.asarray(img.get_pixels(oiio.FLOAT))[:,:,:3];assert np.isfinite(px).all() and px.max()>0.1
    srgb=np.where(px<=0.0031308,px*12.92,1.055*np.power(np.maximum(px,1e-9),1/2.4)-0.055);tiles.append((frame,np.clip(srgb,0,1)));exr.unlink()
cols=3;rows=(len(tiles)+cols-1)//cols;sheet=np.zeros((rows*H,cols*W,3),dtype=np.float32)
for k,(frame,t) in enumerate(tiles):sheet[(k//cols)*H:(k//cols+1)*H,(k%cols)*W:(k%cols+1)*W]=t
buf=oiio.ImageBuf(oiio.ImageSpec(cols*W,rows*H,3,oiio.FLOAT));buf.set_pixels(oiio.ROI(0,cols*W,0,rows*H,0,1,0,3),sheet)
for k,(frame,_) in enumerate(tiles):oiio.ImageBufAlgo.render_text(buf,(k%cols)*W+16,(k//cols)*H+44,'frame %d'%frame,36,'',(1.0,1.0,1.0))
out=ROOT/'renders'/(versions.render_name(VID,'grow')+'.png');assert buf.write(str(out)),buf.geterror();print('wrote',out,'%d frames in %.0fs'%(len(tiles),time.time()-t0))
