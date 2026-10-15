"""Cross-version equivalence: the Houdini 20.5 build must write the same PointInstancers as the Houdini 22 build on the same demo scenes.
Plain Python (it starts the two hythons itself):  python tests/validate_h205.py [v1.1.0]   (the Houdini 22 side is the H22 demos of the given release, or of the current
release when the Houdini 22 build of it does not exist yet).  Compared per node and frame: positions, scales and orientations (half precision: 2e-3), ids, protoIndices,
invisibleIds, prototype target paths and order, computed visibility of the targets, primvars, custom data, child prims, errors and warnings.
Self-test: ARRAYTRON_H205_MUTATE=normalize|protopath|hide|stage breaks the Houdini 20.5 / 21 side in memory (tests/dump_demo.py) and this suite must then FAIL."""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
HOUDINI=Path('C:/Program Files/Side Effects Software')
H22=HOUDINI/'Houdini 22.0.368/bin/hython.exe'
OLDER=(('20.5.445',HOUDINI/'Houdini 20.5.445/bin/hython.exe'),('21.0.440',HOUDINI/'Houdini 21.0.440/bin/hython.exe'))     # the one HDA built in 20.5 must work in both
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else 'v1.1.0')
DEMOS=(('','1,24,64'),('paint','1'),('paint_k','1'),('fields','1'),('cluster','1'),('camera','1,12'),('finish','1'),('imported','1,17,48,96'),('grow','1,24,44,84,110'),('mask','1'),('overlap','1'))
TOL=dict(positions=1e-4,scales=1e-4,orientations=2e-3)
def hip22(kind):
    base=versions.CURRENT if (ROOT/'dist'/f'Arraytron_{VID}_{kind+"_" if kind else ""}demo.hip').exists()==False else VID
    return ROOT/'dist'/f'Arraytron_{base}_{kind+"_" if kind else ""}demo.hip'
def hip205(kind):
    return ROOT/'otls_h205'/f'Arraytron_{VID}_H205_{kind+"_" if kind else ""}demo.hip'
def dump(hython,hip,out,frames):
    r=subprocess.run([str(hython),str(ROOT/'tests/dump_demo.py'),str(hip),str(out),frames],capture_output=True,text=True,cwd=str(ROOT))
    assert r.returncode==0 and Path(out).exists(),(hip,r.stdout[-400:],r.stderr[-800:])
def compare(name,a,b):
    assert set(a)==set(b),(name,'nodes',sorted(a),sorted(b))
    for node in a:
        x,y=a[node],b[node];assert set(x['frames'])==set(y['frames'])
        assert x['errors']==y['errors']==[],(name,node,x['errors'],y['errors'])
        for frame in x['frames']:
            p,q=x['frames'][frame],y['frames'][frame];where=(name,node,frame)
            assert set(p)==set(q),(where,'keys',sorted(set(p)^set(q)))
            for key in p:
                u,v=p[key],q[key]
                if key in TOL and u is not None:
                    assert len(u)==len(v),(where,key,'length',len(u),len(v))
                    if key=='orientations':        # q and -q are the same rotation
                        d=np.minimum(np.abs(np.array(u)-np.array(v)).max(axis=1),np.abs(np.array(u)+np.array(v)).max(axis=1)) if len(u) else np.zeros(0)
                        assert (d<=TOL[key]).all(),(where,key,float(d.max()))
                    elif len(u):assert np.abs(np.array(u,dtype=float)-np.array(v,dtype=float)).max()<=TOL[key],(where,key)
                elif key=='primvars':
                    assert set(u)==set(v),(where,key,sorted(u),sorted(v))
                    for k in u:
                        assert u[k][:2]==v[k][:2],(where,k,u[k][:2],v[k][:2])
                        if u[k][2] is not None:assert np.abs(np.array(u[k][2],dtype=float)-np.array(v[k][2],dtype=float)).max()<=2e-3,(where,'primvar',k)
                elif key=='customData':
                    mine=lambda d:{k:x for k,x in d.items() if k.startswith('arraytron')}           # Houdini's own bookkeeping (node ids, doc strings) differs by design
                    assert mine(u)==mine(v),(where,key,mine(u),mine(v))
                else:assert u==v,(where,key,str(u)[:300],str(v)[:300])
    return sum(len(x['frames']) for x in a.values())
REAL='''import hou,json
hou.hda.installFile(%r,force_use_assets=True)
t=hou.nodeType(hou.lopNodeTypeCategory(),%r)
c=hou.node('/stage').createNode('reference','c');c.parm('primpath').set('/World/Props/Crate');c.parm('primpath1').set('/World/Props/Crate');c.parm('filepath1').set(%r);c.parm('filerefprim1').set('defaultPrim')
n=hou.node('/stage').createNode(%r,'A');n.setInput(0,c)
from pxr import UsdGeom
pi=UsdGeom.PointInstancer(n.stage().GetPrimAtPath('/World/Arraytron'))
d=t.definition()
print('REAL '+json.dumps(dict(version=hou.applicationVersionString(),parms=len(n.parms()),bindings=d.sections()['DialogScript'].contents().count('bindhandle'),errors=list(n.errors()),points=len(pi.GetPositionsAttr().Get(1) or []),h205_code='def flat_paths' in d.sections()['PythonModule'].contents())))
'''
def real_install(hython):
    """The shipped file itself (with its viewport handle bindings) installs in a clean session: the node has its parameters, the handle is bound, a default cook works."""
    code=REAL%(str(versions.hda(VID,True)),versions.type_name(VID),(ROOT/'dist/test_assets/crate.usda').as_posix(),versions.type_name(VID))
    r=subprocess.run([str(hython),'-c',code],capture_output=True,text=True,cwd=str(ROOT));line=[l for l in r.stdout.splitlines() if l.startswith('REAL ')]
    assert line,(r.stdout[-300:],r.stderr[-500:])
    return json.loads(line[-1][5:])
def main():
    tmp=Path(tempfile.mkdtemp(prefix='arraytron_h205_'));checks=0
    for name,hython in OLDER:
        info=real_install(hython)
        assert info['parms']>300 and info['bindings']==12 and info['errors']==[] and info['points']==10 and info['h205_code'],info
        print('PASS Houdini %s: the shipped HDA installs in a clean session with its parameters (%d), 12 handle bindings and a clean default cook'%(name,info['parms']));checks+=1
    h22_version=versions.CURRENT if not (ROOT/'dist'/f'Arraytron_{VID}.hda').exists() else VID                    # the Houdini 22 build of the release (or of the current release while it does not exist yet)
    edge22=tmp/'edge_22.hip';r=subprocess.run([str(H22),str(ROOT/'tests/make_h205_edge_scene.py'),str(edge22),h22_version],capture_output=True,text=True,cwd=str(ROOT));assert edge22.exists(),(r.stdout[-300:],r.stderr[-600:])
    dump(H22,edge22,tmp/'edge_22.json','1');edge_a=json.loads((tmp/'edge_22.json').read_text())
    for label,hython in OLDER:
        edge=tmp/('edge_%s.hip'%label);r=subprocess.run([str(hython),str(ROOT/'tests/make_h205_edge_scene.py'),str(edge),VID],capture_output=True,text=True,cwd=str(ROOT));assert edge.exists(),(r.stdout[-300:],r.stderr[-600:])
        dump(hython,edge,tmp/('edge_%s.json'%label),'1');n=compare('edge',edge_a,json.loads((tmp/('edge_%s.json'%label)).read_text()));checks+=1
        print('PASS edge scene (same-leaf names, top-level source, gprim sources, file, SOP, input): Houdini 22 and %s write the same instancers, prototype types and hidden sources (%d node-frames)'%(label,n))
    for kind,frames in DEMOS:
        name=kind or 'main';a_path=tmp/(name+'_22.json');dump(H22,hip22(kind),a_path,frames);a=json.loads(a_path.read_text())
        for label,hython in OLDER:
            b_path=tmp/(name+'_'+label+'.json');dump(hython,hip205(kind),b_path,frames)
            n=compare(name,a,json.loads(b_path.read_text()));checks+=1
            print('PASS %s demo: Houdini 22 and %s write the same instancers (%d node-frames)'%(name,label,n));sys.stdout.flush()
    (ROOT/'tests'/f'validation_h205_{VID}.json').write_text(json.dumps({'houdini22':'22.0.368','older':[l for l,_ in OLDER],'demos':[k or 'main' for k,_ in DEMOS],'passed':True},indent=2))
    print('ALL PASSED',checks)
main()
