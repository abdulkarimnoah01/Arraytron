"""v1.35.0 in real Houdini: hython tests/validate_lookdev.py [version]
The Lookdev tab: Material Assignments (all prototypes or one Prototype Bank row, later rows win, stronger than the bindings inside the prototype; errors for a missing or wrong prim) and Per-Instance Variation
(a primvar on the instancer, one value per instance from its id or per prototype, Float / Vector3 per component / Color3 blend, a seed; wired into a MaterialX or USD Preview shader input with Replace,
Multiply or Add, the reader inside the shader's own node graph; the primvar takes the input's type; Primvar Only; an error for a shader that cannot read a primvar). With the tab empty the node is the
release before. Env ARRAYTRON_MUTATE=lk_hash|lk_order|lk_keep breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, UsdShade
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.38.3':'v1.34.1','v1.38.2':'v1.34.1','v1.38.1':'v1.34.1','v1.38.0':'v1.34.1','v1.37.0':'v1.34.1','v1.36.0':'v1.34.1','v1.35.0':'v1.34.1'}[VID]          # the version before the Lookdev tab
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_lookdev_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
MATERIALS='''from pxr import UsdShade, Sdf, Gf
stage=hou.pwd().editableStage()
m=UsdShade.Material.Define(stage,'/materials/mx')
g=UsdShade.NodeGraph.Define(stage,'/materials/mx/materialx')
s=UsdShade.Shader.Define(stage,'/materials/mx/materialx/surface');s.CreateIdAttr('ND_standard_surface_surfaceshader')
img=UsdShade.Shader.Define(stage,'/materials/mx/materialx/tex');img.CreateIdAttr('ND_constant_color3');img.CreateInput('value',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.2,0.4,0.6))
s.CreateInput('base_color',Sdf.ValueTypeNames.Color3f).ConnectToSource(img.CreateOutput('out',Sdf.ValueTypeNames.Color3f))
s.CreateInput('specular_roughness',Sdf.ValueTypeNames.Float).Set(0.3)
s.CreateInput('subsurface_color',Sdf.ValueTypeNames.Color3f)
m.CreateSurfaceOutput('mtlx').ConnectToSource(s.CreateOutput('out',Sdf.ValueTypeNames.Token))
p=UsdShade.Material.Define(stage,'/materials/pv');ps=UsdShade.Shader.Define(stage,'/materials/pv/preview');ps.CreateIdAttr('UsdPreviewSurface');ps.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.5,0.5,0.5))
p.CreateSurfaceOutput().ConnectToSource(ps.CreateOutput('surface',Sdf.ValueTypeNames.Token))
v=UsdShade.Material.Define(stage,'/materials/vex');vs=UsdShade.Shader.Define(stage,'/materials/vex/shader');vs.CreateIdAttr('karma:principledshader');vs.CreateInput('basecolor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1,1,1))
UsdShade.Material.Define(stage,'/materials/inner')
stage.DefinePrim('/materials/notamaterial','Xform')
'''
def write_scene():
    path=WORK/'lookdev.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name,size in (('Ball',0.2),('Box',0.4)):
        UsdGeom.Xform.Define(s,'/World/Props/'+name);c=UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name);c.CreateSizeAttr(size)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim')
    lib=st.createNode('pythonscript','materials');lib.setInput(0,n);lib.parm('python').set(MATERIALS)
    inner=st.createNode('pythonscript','inner_binding');inner.setInput(0,lib);inner.parm('python').set("from pxr import UsdShade\nstage=hou.pwd().editableStage()\nUsdShade.MaterialBindingAPI.Apply(stage.GetPrimAtPath('/World/Props/Ball/C')).Bind(UsdShade.Material(stage.GetPrimAtPath('/materials/inner')))")
    return st,inner
def node(stage,source,name='Lk',typ=None,count=200,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(2);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('proto_prim2').set('/World/Props/Box')
    a.parm('mode').set(1);a.parm('area_count').set(count);a.parm('area_sizex').set(8.0);a.parm('area_sizez').set(6.0)
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def all_errors(a):return [e for c in [a]+list(a.allSubChildren()) for e in c.errors()]
def stage_of(a,ok=True):
    s=a.stage();errs=all_errors(a)
    if ok:assert not errs,errs
    return s
def inst(a,s):
    return UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')))
def protos(a,s):
    return {t.name:s.GetPrimAtPath(t) for t in inst(a,s).GetPrototypesRel().GetTargets()}
def bound(prim):
    """The material every mesh under a prototype renders with."""
    return {str(UsdShade.MaterialBindingAPI(q).ComputeBoundMaterial()[0].GetPath()) for q in Usd.PrimRange(prim) if q.IsA(UsdGeom.Gprim)}
def rowmap(a,s):
    """{Prototype Bank row: prototype prim}, independent of the module: the rows come from the source prim each prototype was made from."""
    out={}
    for t in inst(a,s).GetPrototypesRel().GetTargets():
        name=t.name;out[1 if 'Ball' in name else 2 if 'Box' in name else None]=s.GetPrimAtPath(t)
    return out
def primvar(a,s,i=1):
    pi=inst(a,s);pv=UsdGeom.PrimvarsAPI(pi.GetPrim()).GetPrimvar('arraytron_lk%d'%i);return np.array(pv.Get()),str(pv.GetTypeName()),np.array(pi.GetIdsAttr().Get(),dtype=np.int64),np.array(pi.GetProtoIndicesAttr().Get(),dtype=np.int64),pv.GetInterpolation()
def mat_row(a,i,target=0,row=1,mat='/materials/pv',on=1):
    a.parm('lk_mats').set(max(a.evalParm('lk_mats'),i));a.parm('lk_mon%d'%i).set(on);a.parm('lk_target%d'%i).set(target);a.parm('lk_row%d'%i).set(row);a.parm('lk_mat%d'%i).set(mat)
def var_row(a,i,mat='/materials/mx',shader='materialx/surface',inp='base_color',kind=1,lo=(0,0,0),hi=(1,1,1),by=0,seed=0,wire=0,op=0):
    a.parm('lk_vars').set(max(a.evalParm('lk_vars'),i))
    for k,v in (('lk_vmat',mat),('lk_vshader',shader),('lk_vinput',inp),('lk_vtype',kind),('lk_vby',by),('lk_vseed',seed),('lk_vwire',wire),('lk_vop',op)):a.parm('%s%d'%(k,i)).set(v)
    a.parmTuple('lk_vmin%d'%i).set(lo);a.parmTuple('lk_vmax%d'%i).set(hi)
def mutate(a):
    g=a.hdaModule().lookdev_apply.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='lk_hash':
        good=g['lookdev_hash'];g['lookdev_hash']=lambda keys,seed,salt:good(np.zeros(len(keys),dtype=np.int64),seed,salt)                                  # every instance the same value
    elif MUTATE=='lk_order':
        good=g['lookdev_rows'];g['lookdev_rows']=lambda asset,names:(lambda r:({k:v+1 for k,v in r[0].items()},r[1]))(good(asset,names))                  # the wrong Prototype Bank row
    elif MUTATE=='lk_keep':
        import types
        src=g['lookdev_apply'];code=src.__code__;names=list(code.co_names)                                                                                     # Multiply / Add lose what fed the input: ConnectToSource of in1 does nothing
        g['_lk_orig_connect']=UsdShade.Input.ConnectToSource
        def patched(stage,asset,_orig=src):
            real=UsdShade.Input.ConnectToSource
            def fake(self,*x):
                if self.GetBaseName()=='in1':return True
                return real(self,*x)
            UsdShade.Input.ConnectToSource=fake
            try:return _orig(stage,asset)
            finally:UsdShade.Input.ConnectToSource=real
        g['lookdev_apply']=patched
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def defaults():
    st,src=new_scene('defaults');a=node(st,src);b=node(st,src,'Old',typ=OLD_TYPE)
    assert a.evalParm('lk_on')==1 and a.evalParm('lk_mats')==0 and a.evalParm('lk_vars')==0 and b.parm('lk_on') is None
    sa,sb=stage_of(a),stage_of(b);pa,pb=inst(a,sa),inst(b,sb)
    assert np.allclose(np.array(pa.GetPositionsAttr().Get()),np.array(pb.GetPositionsAttr().Get()),atol=1e-5) and list(pa.GetIdsAttr().Get())==list(pb.GetIdsAttr().Get())
    assert bound(protos(a,sa)['Proto_01_Ball'] if 'Proto_01_Ball' in protos(a,sa) else list(protos(a,sa).values())[0])=={'/materials/inner'}             # nothing bound: the prototype's own binding
    assert 'Nothing to do' in a.evalParm('lk_info')
    names=[t.label() for t in a.parmTemplateGroup().entries() if t.type()==hou.parmTemplateType.Folder and t.folderType()==hou.folderType.Tabs]
    assert names.index('Lookdev')==names.index('Edit')+1 and names.index('Optimize')==names.index('Lookdev')+1,names
    assert a.node('lookdev').inputs()[0].name()==('camera_optimize' if a.node('camera_optimize') else 'transform_distribution') and a.node('OUT_ARRAYTRON').inputs()[0].name() in ('debug_guide','lookdev')
    assert '/materials/mx' in a.hdaModule().lookdev_materials(a)

def assignment():
    st,src=new_scene('assign');a=node(st,src);mat_row(a,1,0,mat='/materials/pv');s=stage_of(a);P=protos(a,s);assert len(P)==2
    for p in P.values():assert bound(p)=={'/materials/pv'},(p.GetPath(),bound(p))                                                                          # all prototypes, stronger than the binding inside
    mat_row(a,2,1,row=2,mat='/materials/mx');s=stage_of(a);rows=rowmap(a,s)
    assert bound(rows[1])=={'/materials/pv'} and bound(rows[2])=={'/materials/mx'}                                                                          # a later row wins, only on its prototype row
    mat_row(a,3,1,row=1,mat='/materials/mx',on=0);s=stage_of(a);assert bound(rowmap(a,s)[1])=={'/materials/pv'}   # a disabled row does nothing
    a.parm('lk_on').set(0);s=stage_of(a);assert bound(list(protos(a,s).values())[0]) in ({'/materials/inner'},set());a.parm('lk_on').set(1)
    a.parm('lk_mats').set(1)
    for bad,word in (('/materials/missing','not in the stream'),('/materials/notamaterial','not a Material'),('','empty')):
        a.parm('lk_mat1').set(bad);stage_of(a,ok=False);errs=' '.join(all_errors(a));assert word in errs,(bad,errs)
    a.parm('lk_mat1').set('/materials/pv');mat_row(a,1,1,row=7);stage_of(a,ok=False);assert 'row 7' in ' '.join(all_errors(a)) and 'rows are 1, 2' in ' '.join(all_errors(a))

def variation():
    st,src=new_scene('variation');a=node(st,src,count=300);var_row(a,1,kind=1,lo=(0.1,0.5,0.0),hi=(0.9,0.5,1.0));s=stage_of(a)
    v,t,ids,pr,interp=primvar(a,s);assert t=='color3f[]' and len(v)==len(ids) and interp=='varying'                                                         # the primvar takes the input's type (base_color is a colour)
    assert np.allclose(v[:,1],0.5) and v[:,0].min()>=0.1-1e-6 and v[:,0].max()<=0.9+1e-6 and v[:,0].std()>0.15 and abs(np.corrcoef(v[:,0],v[:,2])[0,1])<0.3   # per component, Min = Max fixed
    before=dict(zip(ids.tolist(),v.tolist()));a.parm('area_count').set(450);v2,_,ids2,_,_=primvar(a,stage_of(a));after=dict(zip(ids2.tolist(),v2.tolist()))
    assert all(np.allclose(before[i],after[i]) for i in before if i in after) and len(set(before)&set(after))>200                                          # the value follows the id
    a.parm('lk_vseed1').set(3);v3,_,ids3,_,_=primvar(a,stage_of(a));assert not np.allclose(v3,v2)
    a.parm('lk_vtype1').set(2);a.parm('lk_vseed1').set(0);v4,_,_,_,_=primvar(a,stage_of(a));u=(v4-np.array([0.1,0.5,0.0]))/np.array([0.8,1.0,1.0]);assert np.allclose(u[:,0],u[:,2],atol=1e-5)  # Color3: one blend
    var_row(a,1,shader='materialx/surface',inp='specular_roughness',kind=0,lo=(0.2,0,0),hi=(0.6,0,0));v5,t5,_,_,_=primvar(a,stage_of(a));assert t5=='float[]' and v5.min()>=0.2-1e-6 and v5.max()<=0.6+1e-6
    var_row(a,1,by=1,kind=1);v6,_,_,pr6,_=primvar(a,stage_of(a));assert all(len(np.unique(v6[pr6==k],axis=0))==1 for k in np.unique(pr6)) and len(np.unique(v6,axis=0))==len(np.unique(pr6))   # one value per prototype
    m=a.hdaModule();h=m.lookdev_hash(np.arange(20000),0,1);assert abs(h.mean()-0.5)<0.01 and h.min()>=0 and h.max()<1                                       # the hash is uniform

def wiring():
    st,src=new_scene('wiring');a=node(st,src);mat_row(a,1,0,mat='/materials/mx');var_row(a,1,inp='base_color',op=0);s=stage_of(a)
    sh=UsdShade.Shader(s.GetPrimAtPath('/materials/mx/materialx/surface'));c=sh.GetInput('base_color').GetConnectedSource();rd=c[0].GetPrim()
    assert str(rd.GetPath())=='/materials/mx/materialx/arraytron_lk1_reader' and UsdShade.Shader(rd).GetIdAttr().Get()=='ND_geompropvalue_color3' and UsdShade.Shader(rd).GetInput('geomprop').Get()=='arraytron_lk1'   # Replace, inside the node graph
    for op,nid in ((1,'ND_multiply_color3'),(2,'ND_add_color3')):
        var_row(a,1,inp='base_color',op=op);s=stage_of(a);c=UsdShade.Shader(s.GetPrimAtPath('/materials/mx/materialx/surface')).GetInput('base_color').GetConnectedSource();mix=UsdShade.Shader(c[0].GetPrim())
        assert mix.GetIdAttr().Get()==nid;i1=mix.GetInput('in1').GetConnectedSource();i2=mix.GetInput('in2').GetConnectedSource()
        assert i1 and str(i1[0].GetPath())=='/materials/mx/materialx/tex' and i2 and str(i2[0].GetPath()).endswith('arraytron_lk1_reader')            # what fed the input is kept
    var_row(a,1,inp='specular_roughness',kind=0,op=1,lo=(0.5,0,0),hi=(1,0,0));s=stage_of(a);mix=UsdShade.Shader(UsdShade.Shader(s.GetPrimAtPath('/materials/mx/materialx/surface')).GetInput('specular_roughness').GetConnectedSource()[0].GetPrim())
    assert mix.GetIdAttr().Get()=='ND_multiply_float' and abs(mix.GetInput('in1').Get()-0.3)<1e-6                                                          # a constant input: its value is kept
    var_row(a,1,inp='subsurface_color',op=1);s=stage_of(a);mix=UsdShade.Shader(UsdShade.Shader(s.GetPrimAtPath('/materials/mx/materialx/surface')).GetInput('subsurface_color').GetConnectedSource()[0].GetPrim())
    assert tuple(mix.GetInput('in1').Get())==(1,1,1)                                                                                                        # no value: multiply by 1
    var_row(a,1,mat='/materials/pv',shader='preview',inp='diffuseColor',op=0);s=stage_of(a);c=UsdShade.Shader(s.GetPrimAtPath('/materials/pv/preview')).GetInput('diffuseColor').GetConnectedSource()
    assert UsdShade.Shader(c[0].GetPrim()).GetIdAttr().Get()=='UsdPrimvarReader_float3' and UsdShade.Shader(c[0].GetPrim()).GetInput('varname').Get()=='arraytron_lk1'
    var_row(a,1,mat='/materials/pv',shader='preview',inp='diffuseColor',op=1);stage_of(a,ok=False);assert 'MaterialX' in ' '.join(all_errors(a))             # Multiply needs MaterialX
    var_row(a,1,mat='/materials/vex',shader='shader',inp='basecolor',op=0);stage_of(a,ok=False);assert 'Primvar Only' in ' '.join(all_errors(a))
    var_row(a,1,inp='nosuchinput');stage_of(a,ok=False);assert 'base_color' in ' '.join(all_errors(a))                                                    # the error lists the real inputs
    var_row(a,1,mat='/materials/vex',shader='shader',inp='basecolor',wire=1);s=stage_of(a);v,t,ids,_,_=primvar(a,s);assert len(v)==len(ids) and not UsdShade.Shader(s.GetPrimAtPath('/materials/vex/shader')).GetInput('basecolor').GetConnectedSource()
    a.parm('lk_von1').set(0);s=stage_of(a);assert not UsdGeom.PrimvarsAPI(inst(a,s).GetPrim()).GetPrimvar('arraytron_lk1')

def main():
    for name,func in (('Empty: the release before; the Lookdev tab after Edit, before Optimize; the material menu',defaults),
                      ('Material Assignments: all prototypes, one row, later rows win, disabled rows, errors',assignment),
                      ('Per-Instance Variation: per component, follows the id, seed, Color3 blend, Float, per prototype, a uniform hash',variation),
                      ('Wiring: Replace, Multiply, Add inside a MaterialX node graph, USD Preview, errors, Primvar Only, Enable',wiring)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_lookdev_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
