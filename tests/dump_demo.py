"""Dump what every Arraytron node of a demo HIP writes (hython, any Houdini): hython tests/dump_demo.py <hip> <out.json> [frames, e.g. 1,24,64].
tests/validate_h205.py runs it under Houdini 22 and under 20.5 and compares the two files."""
import json, sys
import hou
from pxr import UsdGeom, Usd
hip,out=sys.argv[1],sys.argv[2]
frames=[float(f) for f in (sys.argv[3] if len(sys.argv)>3 else '1,24,64').split(',')]
hou.hipFile.load(hip,suppress_save_prompt=True,ignore_load_warnings=True)
def arr(v):
    return None if v is None else [[round(float(c),7) for c in x] if hasattr(x,'__len__') else (int(x) if float(x)==int(x) and not hasattr(x,'real') or isinstance(x,int) else float(x)) for x in v]
import os
MUTATE=os.environ.get('ARRAYTRON_H205_MUTATE')     # self-test of the Houdini 20.5 code: normalize | protopath | hide | stage (only meaningful under 20.5; the cross-version suite must then FAIL)
if MUTATE and hou.applicationVersion()[0]<22:
    for a in hou.node('/stage').children():
        if not a.type().name().startswith('arraytron::instancer'):continue
        a.allowEditingOfContents()
        if MUTATE=='normalize':a.node('PROTO_NORMALIZE').bypass(True)
        elif MUTATE=='protopath':
            n=a.node('USD_COMPILER/PROTO_PATH')
            n.parm('python').set(n.parm('python').eval()+"""geo=hou.pwd().geometry()
vals=list(geo.pointStringAttribValues('protopath'))
if vals:geo.setPointStringAttribValues('protopath',vals[1:]+vals[:1])
""")
        elif MUTATE=='hide':
            n=a.node('PROTO_NORMALIZE');code=n.parm('python').eval();assert 'Tokens.invisible' in code;n.parm('python').set(code.replace('Tokens.invisible','Tokens.inherited'))
        elif MUTATE=='stage':
            n=a.node('PROTO_STAGE');n.parm('python').set(n.parm('python').eval().replace("DefinePrim(Sdf.Path(flat))","DefinePrim(Sdf.Path(flat),'Xform')"))
        else:raise SystemExit('unknown ARRAYTRON_H205_MUTATE '+MUTATE)
result={}
for a in hou.node('/stage').children():
    if not a.type().name().startswith('arraytron::instancer'):continue
    entry={'errors':list(a.errors()),'warnings':list(a.warnings()),'frames':{}}
    for f in frames:
        hou.setFrame(f);s=a.stage();path=a.evalParm('outputpath');prim=s.GetPrimAtPath(path)
        if not prim or not prim.IsValid():entry['frames'][str(f)]={'missing':True};continue
        pi=UsdGeom.PointInstancer(prim);t=Usd.TimeCode(f);d={}
        d['positions']=arr(pi.GetPositionsAttr().Get(t))
        q=pi.GetOrientationsAttr().Get(t);d['orientations']=None if q is None else [[round(x.GetReal(),5),*[round(c,5) for c in x.GetImaginary()]] for x in q]
        d['scales']=arr(pi.GetScalesAttr().Get(t))
        for key,getter in (('ids',pi.GetIdsAttr),('protoIndices',pi.GetProtoIndicesAttr),('invisibleIds',pi.GetInvisibleIdsAttr)):
            v=getter().Get(t);d[key]=None if v is None else [int(x) for x in v]
        targets=[x.pathString for x in pi.GetPrototypesRel().GetTargets()];d['targets']=targets
        d['visibility']={p:str(UsdGeom.Imageable(s.GetPrimAtPath(p)).ComputeVisibility(t)) for p in targets}
        d['targetTypes']={p:[s.GetPrimAtPath(p).GetTypeName()]+sorted(c.GetTypeName() for c in s.GetPrimAtPath(p).GetChildren()) for p in targets}
        d['sourceVisibility']={e['path']:str(UsdGeom.Imageable(s.GetPrimAtPath(e['path'])).ComputeVisibility(t)) for e in a.hdaModule().resolve(a)}
        d['prototypeChildren']=[c.GetName() for c in s.GetPrimAtPath(path+'/Prototypes').GetChildren()] if s.GetPrimAtPath(path+'/Prototypes') else None
        pv={}
        for p in UsdGeom.PrimvarsAPI(prim).GetPrimvars():
            v=p.Get(t);pv[p.GetPrimvarName()]=[str(p.GetTypeName()),str(p.GetInterpolation()),None if v is None else [list(map(float,x)) if hasattr(x,'__len__') else float(x) for x in v]]
        d['primvars']=pv
        d['customData']={k:str(v) for k,v in (prim.GetCustomData() or {}).items()}
        d['children']=sorted(c.GetName() for c in prim.GetChildren())
        entry['frames'][str(f)]=d
    result[a.name()]=entry
json.dump(result,open(out,'w'))
print('dumped',len(result),'nodes from',hip)
