"""Render a demo's exported USD with Karma XPU (husk) and write the PNG preview: hython tools/render_demo.py [version] [kind] [samples]
kind is '' (the main demo), 'physics' or 'scatter'. Needs the render USD written by the matching build_demo script.
Exit code 0 only if husk succeeded and the image is finite and not black."""
from pathlib import Path
import subprocess, sys, hashlib, json, time
import numpy as np
import OpenImageIO as oiio
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT);KIND=sys.argv[2] if len(sys.argv)>2 and sys.argv[2]!='-' else '';SAMPLES=int(sys.argv[3]) if len(sys.argv)>3 else 128
HUSK=Path('C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/husk.exe')
usd=versions.render_usd(VID,KIND);name=versions.render_name(VID,KIND);dest=ROOT/'renders'/(name+'.exr');dest.parent.mkdir(exist_ok=True)
size=('1600','900') if KIND else ('1200','800')
cmd=[str(HUSK),'--engine','xpu','--res',size[0],size[1],'--camera','/World/Camera','--pixel-samples',str(SAMPLES),'-V','2','--output',str(dest),str(usd)]
t=time.time()
with dest.with_suffix('.log').open('w',encoding='utf-8') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
assert result.returncode==0,('husk exit code',result.returncode)
image=oiio.ImageBuf(str(dest));assert image.read(),image.geterror()
pixels=np.asarray(image.get_pixels(oiio.FLOAT));assert pixels.shape[:2]==(int(size[1]),int(size[0])) and np.isfinite(pixels).all() and pixels[:,:,:3].max()>0.1
preview=oiio.ImageBufAlgo.colorconvert(image,'linear','sRGB');assert preview.write(str(dest.with_suffix('.png')))
print(json.dumps({'exit_code':result.returncode,'seconds':round(time.time()-t,1),'samples':SAMPLES,'mean_rgb':[round(float(pixels[:,:,c].mean()),4) for c in range(3)],'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()[:16],'png':str(dest.with_suffix('.png'))}))
