"""Measure the Paint brush with Density / Scale Falloff: hython tools/profile_paint_falloff.py [--quick]   (hython 22 or 20.5; build the Stamp first with tools/build_stamp_light.py)
For 300, 3 000 and 10 000 stamps already placed, a prototype of 200 000 triangles (its geometry is read by the stamps surface), and long strokes, it reports the time of one move of the brush (what the
tool pays for every mouse position), of the surface read after a write, of painting the same stroke again, and of the classic dab brush for comparison. Writes tests/profile_paint_falloff_<22|205>.json."""
import sys, os, json, time, platform
from pathlib import Path
import numpy as np
import hou
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import versions
H205=versions.is_h205();QUICK='--quick' in sys.argv
VER=__import__('re').search(r"STAMP_VERSION='([0-9.]+)'",(ROOT/'tools'/'build_stamp_light.py').read_text(encoding='utf-8')).group(1)
HDA=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v%s%s.hda'%(VER,'_H205' if H205 else ''));TYPE='arraytron::stamp::%s'%VER
hou.hda.installFile(str(HDA),force_use_assets=True)
SCENE='''from pxr import Gf, UsdGeom, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
UsdGeom.Xform.Define(stage,'/World/Props/Rock');UsdGeom.Sphere.Define(stage,'/World/Props/Rock/Geom')
UsdGeom.Xform.Define(stage,'/World/Props/Dense');g=UsdGeom.Mesh.Define(stage,'/World/Props/Dense/Geom');n=316;pts=[];idx=[]
for i in range(n+1):
    for j in range(n):
        la=math.pi*i/n;lo=2*math.pi*j/n;pts.append(Gf.Vec3f(0.5*math.sin(la)*math.cos(lo),0.5*math.cos(la),0.5*math.sin(la)*math.sin(lo)))
for i in range(n):
    for j in range(n):idx+=[i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j]
g.CreatePointsAttr(Vt.Vec3fArray(pts));g.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));g.CreateFaceVertexIndicesAttr(Vt.IntArray(idx))
'''
def hardware():
    cpu=platform.processor()
    try:
        import subprocess;cpu=subprocess.run(['powershell','-NoProfile','-Command','(Get-CimInstance Win32_Processor).Name'],capture_output=True,text=True,timeout=20).stdout.strip() or cpu
        ram=subprocess.run(['powershell','-NoProfile','-Command','[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)'],capture_output=True,text=True,timeout=20).stdout.strip()
    except Exception:ram='?'
    return dict(cpu=cpu,cores=os.cpu_count(),ram_gb=ram,os=platform.platform(),houdini=hou.applicationVersionString(),python=platform.python_version())
def stats(a):
    a=np.asarray(a);return dict(mean=round(float(a.mean()),2),p95=round(float(np.percentile(a,95)),2),max=round(float(a.max()),2),n=len(a))
def setup(n_existing):
    hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(HDA),force_use_assets=True);st=hou.node('/stage');sc=st.createNode('pythonscript','s');sc.parm('python').set(SCENE)
    a=st.createNode(TYPE,'p');a.setInput(0,sc);a.parm('protos').set(2);a.parm('proto_prim1').set('/World/Props/Rock');a.parm('proto_prim2').set('/World/Props/Dense');a.parm('sit').set(1)
    m=a.hdaModule();rg=np.random.RandomState(4);a.parm('paint_radius').set(2.0);a.parm('paint_density').set(3.0);a.parm('paint_spacing').set(0.3)
    a.parm('stamps').set('\n'.join('%.3f 0 %.3f  0 0 0  1 1 1  %d 1'%(rg.uniform(-100,100),rg.uniform(-100,100),1+k%2) for k in range(n_existing)));return a,m
def long_stroke(a,m,flush,moves,z0):
    bd=m.stamp_proto_bounds(a);sf=m.stamp_surface(a);sk=m.StampPaintStroke(a,sf,bd);sk.FLUSH_S=flush;tm=[];tu=[]
    for k in range(moves):
        t=time.time();sk.move((-95.0+0.45*k,0.0,z0+6.0*np.sin(k*0.04)),(0,1,0));tm.append((time.time()-t)*1000);t=time.time();sf.update(a);tu.append((time.time()-t)*1000)
    t=time.time();sk.finish();fin=(time.time()-t)*1000;return tm,tu,fin,sk.added
def main():
    out=dict(hardware=hardware(),version=VER,runs=[])
    moves=150 if QUICK else 400
    for n_ex in (300,3000,10000):
        a,m=setup(n_ex);m.stamp_paint_preset(a,'soft');bd=m.stamp_proto_bounds(a);sf=m.stamp_surface(a)
        t=time.time();m.stamp_surface(a);first=(time.time()-t)*1000                                    # reading the scene and the 200 000 triangle prototype
        tm,tu,fin,added=long_stroke(a,m,0.05,moves,20.0);tm0,tu0,fin0,added0=long_stroke(a,m,0.0,moves,40.0)
        # the same stroke again: Spacing keeps it from doubling
        a.parm('stamps').set(a.evalParm('stamps'));sf=m.stamp_surface(a);before=m.stamp_count(a.evalParm('stamps'));pts=[(-95.0+0.45*k,0.0,20.0+6.0*np.sin(k*0.04)) for k in range(moves)];t=time.time();again=m.stamp_paint_path(a,sf,pts,bd);tagain=(time.time()-t)*1000
        # the classic dab brush, for comparison
        a.parm('paint_dens_on').set(0);a.parm('paint_scale_on').set(0);sf=m.stamp_surface(a);cfg=m.stamp_settings(a);rng=np.random.RandomState(1);dabs=[]
        for k in range(30):
            p=np.array([-90.0+k*1.2,0.0,60.0]);h=sf.hit(p+np.array([0,100.0,0]),(0,-1,0),stamps=False);t=time.time();np_,nn=m.stamp_paint_dab(sf,h[0],h[1],2.0,3.0,0.3,0.5,rng,m.stamp_rows(a.evalParm('stamps'))[:,0:3])
            if len(np_):m.stamp_add_batch(a,np_,nn,cfg=cfg,bounds=bd)
            dabs.append((time.time()-t)*1000)
        out['runs'].append(dict(existing=n_ex,first_surface_read_ms=round(first,1),move_buffered=stats(tm),surface_update_buffered=stats(tu),stamps_buffered=added,move_every_write=stats(tm0),surface_update_every_write=stats(tu0),stamps_every_write=added0,
                                repaint_same_stroke=dict(added=again,ms=round(tagain,1),existing=before),classic_dab=stats(dabs)))
        print(json.dumps(out['runs'][-1]));sys.stdout.flush()
    (ROOT/'tests'/('profile_paint_falloff_%s.json'%('205' if H205 else '22'))).write_text(json.dumps(out,indent=1))
    print(json.dumps(out['hardware']))
main()
