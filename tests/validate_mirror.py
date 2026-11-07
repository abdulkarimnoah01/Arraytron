"""v1.34.0 in real Houdini: hython tests/validate_mirror.py [version]
Mirror (the Mirror tab): a list of mirror operations on the finished scatter. Plane X / Y / Z and Custom Plane (with a Center), Radial (Count, Angle Span, Mirror Each Slice, a custom Axis), several operations one
after the other (2 planes give 4 copies, 3 give 8), Keep Original off (a flip), Mirror The Instances Too (a true mirror image: negative scale) or only the placement, the ids of the copies, Max Instances. Every copy is
checked against independent numpy matrices (the instance transform of the original, reflected or turned). Env ARRAYTRON_MUTATE=mi_center|mi_flip|mi_keep|mi_ids|mi_angle|mi_slice|mi_vector breaks the module; the suite
must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.34.0':'v1.33.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_mirror_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
STRIDE=1<<20
def write_scene():
    path=WORK/'mirror.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Ball','Box'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def node(stage,source,name='Mi',typ=None,protos=2,count=40,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(protos);a.parm('proto_prim1').set('/World/Props/Ball')
    if protos>1:a.parm('proto_prim2').set('/World/Props/Box')
    a.parm('mode').set(1);a.parm('area_count').set(count);a.parm('area_sizex').set(8.0);a.parm('area_sizez').set(6.0);a.parmTuple('rotation_random').set((20.0,180.0,20.0));a.parm('scale_random').set(0.3)
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def ops(a,*rows):
    """rows: dicts of the Mirror Operations parms (without the number)."""
    a.parm('mirror_on').set(1);a.parm('mirror_ops').set(len(rows))
    for i,row in enumerate(rows,1):
        for k in ('mirror_en','mirror_type','mirror_axis','mirror_normal','mirror_center','mirror_count','mirror_span','mirror_slice','mirror_angle','mirror_flip','mirror_keep'):a.parmTuple('%s%d'%(k,i)).revertToDefaults()      # every call starts from the defaults
        for k,v in row.items():
            pt=a.parmTuple('%s%d'%(k,i))
            if len(pt)>1 or isinstance(v,(tuple,list)):pt.set(v)
            else:pt[0].set(v)
def all_errors(n):
    o=list(n.errors())
    for c in n.children():o+=all_errors(c)
    return o
def out(a):
    a.stage();errs=all_errors(a);assert not errs,errs;pi=UsdGeom.PointInstancer(a.stage().GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=np.int64);pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3);sc=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3)
    q=pi.GetOrientationsAttr().Get(t) or [];orient=np.array([[x.GetImaginary()[0],x.GetImaginary()[1],x.GetImaginary()[2],x.GetReal()] for x in q]).reshape(-1,4);pr=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int)
    o=np.argsort(ids);return dict(ids=ids[o],pos=pos[o],scale=sc[o],orient=orient[o],proto=pr[o])
def mat(q,s):
    x,y,z,w=q.T;R=np.stack([np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],-1),np.stack([2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],-1),np.stack([2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],-1)],1)
    return R*s[:,None,:]                                                                                       # R @ diag(s): the columns of R scaled
def ref(n):
    n=np.asarray(n,dtype=float);n/=np.linalg.norm(n);return np.eye(3)-2*np.outer(n,n)
def rot(axis,deg):
    a=np.asarray(axis,dtype=float);a/=np.linalg.norm(a);t=math.radians(deg);K=np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]]);return np.eye(3)+math.sin(t)*K+(1-math.cos(t))*(K@K)
def copy_of(res,k):
    """The instances of copy number k (ids id + STRIDE * k), sorted by original id."""
    m=(res['ids']>>20)==k;return {key:v[m] for key,v in res.items()}
def mutate(a):
    g=a.hdaModule().mir_apply.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='mi_center':
        good=g['mir_reflect'];g['mir_reflect']=lambda s,n,c,f:good(s,n,np.zeros(3),f)                                                                      # the Center is ignored
    elif MUTATE=='mi_flip':
        good=g['mir_reflect'];g['mir_reflect']=lambda s,n,c,f:good(s,n,c,not f)                                                                            # Mirror The Instances Too reversed
    elif MUTATE=='mi_keep':
        good=g['mir_blocks'];g['mir_blocks']=lambda s,op:good(s,dict(op,keep=True))                                                                        # Keep Original ignored
    elif MUTATE=='mi_ids':
        good=g['mir_apply'];g['mir_apply']=lambda s,o,*r:(lambda res:(dict(res[0],id=np.asarray(s['id'])[res[1]]),)+res[1:])(good(s,o,*r))                  # copies keep the ids of the originals
    elif MUTATE=='mi_angle':
        good=g['mir_blocks'];g['mir_blocks']=lambda s,op:good(s,dict(op,span=op['span']*0.5))                                                              # the span is halved
    elif MUTATE=='mi_slice':
        good=g['mir_blocks'];g['mir_blocks']=lambda s,op:good(s,dict(op,slice=False))                                                                      # Mirror Each Slice ignored
    elif MUTATE=='mi_vector':
        g['MIRROR_VECTORS']=()                                                                                                                              # vectors are not mirrored
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def defaults():
    st,src=new_scene('defaults');a=node(st,src);b=node(st,src,'Old',typ=OLD_TYPE);assert a.parm('mirror_on') is not None and a.evalParm('mirror_on')==0 and a.evalParm('mirror_ops')==1 and b.parm('mirror_on') is None
    x,y=out(a),out(b)
    for k in x:assert np.allclose(x[k],y[k],atol=2e-3),k                                                                                                    # off: the same as the release before
    names=[t.label() for t in a.parmTemplateGroup().entries() if t.type()==hou.parmTemplateType.Folder and t.folderType()==hou.folderType.Tabs]
    assert 'Mirror' in names and names.index('Mirror')==names.index(versions.tab_names(VID)['look'])+1                                                       # a Mirror tab after Variation
    assert a.evalParm('mirror_type1')==0 and a.evalParm('mirror_flip1')==1 and a.evalParm('mirror_keep1')==1 and a.evalParm('mirror_count1')==6 and a.evalParm('mirror_span1')==360.0

def plane():
    st,src=new_scene('plane');a=node(st,src);base=out(a);n=len(base['ids']);assert n==40
    ops(a,dict(mirror_type=0,mirror_center=(1.0,0.0,0.0)));res=out(a);assert len(res['ids'])==2*n and np.array_equal(res['ids'][:n],base['ids']) and len(np.unique(res['ids']))==2*n     # originals keep their ids, the copies are new
    c=copy_of(res,1);assert np.array_equal(c['ids']-STRIDE,base['ids'])
    assert np.allclose(c['pos'][:,0],2.0-base['pos'][:,0],atol=1e-4) and np.allclose(c['pos'][:,1:],base['pos'][:,1:],atol=1e-4) and np.array_equal(c['proto'],base['proto'])           # mirrored about x = 1, same prototypes
    M=mat(base['orient'],base['scale']);R=ref((1,0,0));M2=mat(c['orient'],c['scale'])
    assert np.allclose(M2,R@M,atol=3e-3)                                                                                                                         # the instance is the mirror image
    a.parm('mirror_flip1').set(0);c=copy_of(out(a),1);M2=mat(c['orient'],c['scale'])
    assert np.allclose(c['scale'],base['scale'],atol=1e-5) and np.allclose(M2,R@M@R,atol=3e-3)                                                                  # placement only: R M R, the scale is kept
    a.parm('mirror_flip1').set(1);a.parm('mirror_type1').set(1);c=copy_of(out(a),1);assert np.allclose(c['pos'][:,1],-base['pos'][:,1],atol=1e-4)                            # Plane Y
    a.parm('mirror_type1').set(2);c=copy_of(out(a),1);assert np.allclose(c['pos'][:,2],-base['pos'][:,2],atol=1e-4)                                                       # Plane Z

def custom_plane():
    st,src=new_scene('custom');a=node(st,src);base=out(a)
    m=a.hdaModule();s0=dict(P=np.zeros((1,3)),orient=np.array([[0,0,0,1.0]]),scale=np.ones((1,3)),N=np.array([[1.0,2.0,3.0]]),v=np.array([[0.0,1.0,0.0]]));r=m.mir_reflect(s0,np.array([1.0,0.0,0.0]),np.zeros(3),True)
    assert np.allclose(r['N'],[[-1.0,2.0,3.0]]) and np.allclose(r['v'],[[0.0,1.0,0.0]])                                                             # the vector attributes follow the mirror
    n=np.array([1.0,0.0,1.0]);c0=np.array([0.5,0.0,-0.5])
    ops(a,dict(mirror_type=3,mirror_normal=tuple(n),mirror_center=tuple(c0)));c=copy_of(out(a),1);un=n/np.linalg.norm(n)
    exp=base['pos']-2*((base['pos']-c0)@un)[:,None]*un[None,:];assert np.allclose(c['pos'],exp,atol=1e-4)
    assert np.allclose(mat(c['orient'],c['scale']),ref(n)@mat(base['orient'],base['scale']),atol=3e-3)

def several():
    st,src=new_scene('several');a=node(st,src);base=out(a);n=len(base['ids'])
    ops(a,dict(mirror_type=0),dict(mirror_type=2));res=out(a);assert len(res['ids'])==4*n and len(np.unique(res['ids']))==4*n
    P=base['pos'];M=mat(base['orient'],base['scale']);RX,RZ=ref((1,0,0)),ref((0,0,1))
    for k,(R,Rp) in enumerate(((np.eye(3),np.eye(3)),(RX,RX),(RZ,RZ),(RZ@RX,RZ@RX))):                                                                                # the copies: original, X, Z, Z of X
        c=copy_of(res,k);assert np.allclose(c['pos'],P@Rp.T,atol=1e-4) and np.allclose(mat(c['orient'],c['scale']),R@M,atol=3e-3),k
    ops(a,dict(mirror_type=0),dict(mirror_type=1),dict(mirror_type=2));res=out(a);assert len(res['ids'])==8*n and len(np.unique(res['ids']))==8*n                                # three planes: eight
    ops(a,dict(mirror_type=0),dict(mirror_type=0,mirror_en=0));assert len(out(a)['ids'])==2*n                                                                       # a disabled operation is left out
    ops(a,*[dict(mirror_type=0,mirror_center=(float(i),0.0,0.0)) for i in range(5)]);assert len(out(a)['ids'])==32*n                                                            # a custom number of operations (5 give 32)

def keep_flip():
    st,src=new_scene('keep');a=node(st,src);base=out(a);n=len(base['ids'])
    ops(a,dict(mirror_type=0,mirror_keep=0));res=out(a);assert len(res['ids'])==n and np.allclose(res['pos'][:,0],-base['pos'][:,0],atol=1e-4) and np.array_equal(res['ids'],base['ids']+STRIDE)    # the scatter is replaced by its mirror image
    ops(a,dict(mirror_type=0),dict(mirror_type=2,mirror_keep=0));res=out(a);assert len(res['ids'])==2*n                                                                  # 2 ops, the second drops what it was given (2n -> 2n)
    a.parm('mirror_max').set(5*n);ops(a,dict(mirror_type=0),dict(mirror_type=2),dict(mirror_type=1));res=out(a);assert len(res['ids'])==4*n                                                  # Max Instances stops the third operation (it would make 8n)
    assert 'Max Instances' in a.hdaModule().mirror_info(a)
    a.parm('mirror_max').set(20000000);a.parm('mirror_on').set(0);assert len(out(a)['ids'])==n and 'off' in a.hdaModule().mirror_info(a)

def radial():
    st,src=new_scene('radial');a=node(st,src);base=out(a);n=len(base['ids']);P=base['pos']
    ops(a,dict(mirror_type=4,mirror_axis=1,mirror_count=6));res=out(a);assert len(res['ids'])==6*n and len(np.unique(res['ids']))==6*n
    for k in range(6):
        c=copy_of(res,k);R=rot((0,1,0),360.0*k/6);assert np.allclose(c['pos'],P@R.T,atol=1e-4) and np.allclose(mat(c['orient'],c['scale']),R@mat(base['orient'],base['scale']),atol=3e-3) and np.allclose(c['scale'],base['scale'],atol=1e-5)
    ops(a,dict(mirror_type=4,mirror_axis=1,mirror_count=4,mirror_span=90.0));res=out(a)                                                                              # a fan: 4 copies 22.5 degrees apart
    for k in range(4):assert np.allclose(copy_of(res,k)['pos'],P@rot((0,1,0),22.5*k).T,atol=1e-4)
    ops(a,dict(mirror_type=4,mirror_axis=0,mirror_count=3,mirror_center=(0.0,1.0,0.0)));res=out(a);c=copy_of(res,2);R=rot((1,0,0),240.0);assert np.allclose(c['pos'],(P-[0,1,0])@R.T+[0,1,0],atol=1e-4)    # axis X through a centre
    ops(a,dict(mirror_type=4,mirror_axis=3,mirror_normal=(0.0,0.0,1.0),mirror_count=2));c=copy_of(out(a),1);assert np.allclose(c['pos'],P@rot((0,0,1),180.0).T,atol=1e-4)           # a custom axis

def kaleidoscope():
    st,src=new_scene('kaleido');a=node(st,src);base=out(a);n=len(base['ids']);P=base['pos']
    ops(a,dict(mirror_type=4,mirror_axis=1,mirror_count=3,mirror_slice=1));res=out(a);assert len(res['ids'])==6*n and len(np.unique(res['ids']))==6*n                                    # a mirror in every slice: 2 x 3 copies
    # the mirror plane holds the Y axis; its normal is the Y axis x the direction at the plane angle; the copies are turned by k * 120 degrees
    start=np.array([1.0,0.0,0.0]);ax=np.array([0.0,1.0,0.0]);u=start-ax*np.dot(start,ax);u/=np.linalg.norm(u)
    for ang in (0.0,30.0):
        a.parm('mirror_angle1').set(ang);res=out(a);d=rot((0,1,0),ang)@u;nrm=np.cross(ax,d);nrm/=np.linalg.norm(nrm);R=ref(nrm);M=mat(base['orient'],base['scale'])
        c1=copy_of(res,1);assert np.allclose(c1['pos'],P@R.T,atol=1e-4) and np.allclose(mat(c1['orient'],c1['scale']),R@M,atol=3e-3)                                            # the mirror image of the first slice
        c2=copy_of(res,5);Rt=rot((0,1,0),240.0);assert np.allclose(c2['pos'],(P@R.T)@Rt.T,atol=1e-4)                                                                       # a mirror image turned 240
    a.parm('mirror_flip1').set(0);c=copy_of(out(a),1);assert np.allclose(c['scale'],base['scale'],atol=1e-5)

def modes():
    st,src=new_scene('modes')
    for mode,extra in ((0,dict(line_count=12)),(3,dict(circle_count=16)),(5,dict(surface_prim='/World/Props/Box',surface_count=30))):
        a=node(st,src,'M%d'%mode,**extra);a.parm('mode').set(mode);base=out(a);ops(a,dict(mirror_type=0),dict(mirror_type=4,mirror_count=3));res=out(a);assert len(res['ids'])==6*len(base['ids']) and len(np.unique(res['ids']))==len(res['ids'])
    a=node(st,src,'Attr');a.parm('mode').set(1);base=out(a);ops(a,dict(mirror_type=0));res=out(a);assert np.array_equal(copy_of(res,1)['proto'],base['proto']) and set(np.unique(res['proto']))==set(np.unique(base['proto']))

def main():
    for name,func in (('Off: the same as the release before, a Mirror tab with the defaults',defaults),
                      ('Plane X / Y / Z: positions about the Center, the instance is the exact mirror image (R M), or only the placement (R M R)',plane),
                      ('Custom Plane: any normal and centre',custom_plane),
                      ('Several operations: 2 planes give 4, 3 give 8, a disabled one is left out, five give 32, unique ids',several),
                      ('Keep Original off flips the scatter, Max Instances stops an operation',keep_flip),
                      ('Radial: Count about X / Y / custom axis, a centre, an Angle Span fan',radial),
                      ('Mirror Each Slice: a kaleidoscope with the plane angle',kaleidoscope),
                      ('Every distribution mode, prototypes follow the copies',modes)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_mirror_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
