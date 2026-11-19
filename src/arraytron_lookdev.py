# Lookdev tab (v1.35.0): materials on the finished scatter, after everything that places the instances.
#   Material Assignment  a material prim of the stream bound to the prototypes of one Prototype Bank row, or to all of them (later rows win). Every instance of a prototype shows its material.
#   Per-Instance Variation  one value per instance (from its id, or from its prototype) between Min and Max, written as a primvar on the PointInstancer and, with Connect Automatically, wired into
#                       an input of a shader of the material (a MaterialX geompropvalue or a UsdPrimvarReader node is added in front of it): the hue of a colour correct, a roughness, a tint ...
# Appended to the PythonModule; the Python LOP `lookdev` calls lookdev_apply(stage, asset). The pure functions are tested without Houdini.
import re
import numpy as np

LK_TYPES=('float','vector3','color3')
_PROTO_ROW=re.compile(r'Proto_(\d+)')

def lookdev_hash(keys,seed,salt):
    """Three uniform numbers in [0, 1) per key (n, 3), the same for the same key, seed and salt (a splitmix64 hash)."""
    k=np.asarray(keys,dtype=np.int64).astype(np.uint64);out=np.empty((len(k),3))
    with np.errstate(over='ignore'):
        for c in range(3):
            x=k*np.uint64(0x9E3779B97F4A7C15)+np.uint64((int(seed)*1000003+int(salt)*7919+c*104729+1)&0xFFFFFFFFFFFFFFFF)
            x=(x^(x>>np.uint64(30)))*np.uint64(0xBF58476D1CE4E5B9);x=(x^(x>>np.uint64(27)))*np.uint64(0x94D049BB133111EB);x=x^(x>>np.uint64(31))
            out[:,c]=(x>>np.uint64(11)).astype(np.float64)/float(1<<53)
    return out

def lookdev_values(keys,lo,hi,seed,salt,kind):
    """The value of every instance: Min + random x (Max - Min). Vector3: a random number per component (a component with Min = Max is fixed); Color3: one random number, a colour between Min and Max.
    kind 0 float (n,), else (n, 3)."""
    u=lookdev_hash(keys,seed,salt);lo=np.asarray(lo,dtype=np.float64);hi=np.asarray(hi,dtype=np.float64)
    if kind==2:u=np.repeat(u[:,:1],3,axis=1)
    v=lo+u*(hi-lo)
    return v[:,0] if kind==0 else v

def lookdev_proto_row(name):
    """The Prototype Bank row of a prototype prim (Proto_01_... is row 1, its LODs too), or None."""
    m=_PROTO_ROW.search(str(name));return int(m.group(1)) if m else None

def lookdev_reader(shader_id,kind):
    # kind: the type of the input it feeds (0 float, 1 vector3, 2 color3)
    """(info:id, name input, output) of the primvar reader that suits a shader: MaterialX for ND_ shaders, UsdPrimvarReader otherwise; None for shaders that cannot take one (VEX)."""
    sid=str(shader_id or '')
    if sid.startswith('ND_') or sid.startswith('mtlx'):return ('ND_geompropvalue_%s'%LK_TYPES[kind],'geomprop','out')
    if sid.startswith('Usd') or sid=='':return ('UsdPrimvarReader_%s'%('float' if kind==0 else 'float3'),'varname','result')
    return None

# ---------------------------------------------------------------- Houdini side
import hou

def lookdev_primvar(i):return 'arraytron_lk%d'%i

def lookdev_rows(asset,names):
    """{prototype index: Prototype Bank row} for the prototypes of the instancer (names in order). Read from the points (protoindex and proto_id), so prim path, file and Group Children rows all map;
    the LOD prototypes of the camera optimisation take the row of the prototype whose name they extend; Proto_NN names are read as row NN."""
    rows={}
    try:
        g=asset.node('USD_COMPILER/OUT_POINTS').geometry()
        if g.findPointAttrib('proto_id') is not None and g.intrinsicValue('pointcount'):
            pi=np.array(g.pointIntAttribValues('protoindex'));pr=np.array(g.pointIntAttribValues('proto_id'))
            for k in np.unique(pi):rows[int(k)]=int(pr[np.argmax(pi==k)])
    except Exception:pass
    try:bank=[e['row'] for e in resolve(asset)]
    except Exception:bank=[]
    for k,n in enumerate(names):
        if k in rows:continue
        r=lookdev_proto_row(n) if str(n).startswith('Proto_') else None
        if r is None and len(names)>=len(bank) and k<len(bank):r=bank[k]
        if r is None:
            r=next((rows.get(j) for j in range(len(names)) if j!=k and str(n).startswith(str(names[j])+'_') and rows.get(j) is not None),None)
        if r is not None:rows[k]=r
    return rows,set(bank)

def _lk_material(stage,path,what):
    from pxr import UsdShade
    prim=stage.GetPrimAtPath(path) if path else None
    if not path:raise hou.NodeError('%s: Material is empty.'%what)
    if not prim or not prim.IsValid():raise hou.NodeError('%s: %s is not in the stream (wire the material library into the first input).'%(what,path))
    if not prim.IsA(UsdShade.Material):raise hou.NodeError('%s: %s is not a Material prim.'%(what,path))
    return UsdShade.Material(prim)

def lookdev_apply(stage,asset):
    """The Lookdev tab on the stage of the node: material bindings on the prototypes, per-instance primvars and their readers. Returns a short report."""
    from pxr import Sdf,Usd,UsdGeom,UsdShade,Vt,Gf
    report=[]
    if not asset.evalParm('lk_on'):return 'Lookdev is off.'
    root=stage.GetPrimAtPath(asset.evalParm('outputpath'));inst=None
    if root and root.IsValid():
        for p in Usd.PrimRange(root):
            if p.IsA(UsdGeom.PointInstancer):inst=UsdGeom.PointInstancer(p);break
    if inst is None:return 'No instances yet.'
    targets=[stage.GetPrimAtPath(t) for t in inst.GetPrototypesRel().GetTargets()]
    proto_rows,bank=lookdev_rows(asset,[t.name for t in inst.GetPrototypesRel().GetTargets()])
    # ---- material assignment
    for i in range(1,asset.evalParm('lk_mats')+1):
        if not asset.evalParm('lk_mon%d'%i):continue
        what='Material row %d'%i;mat=_lk_material(stage,asset.evalParm('lk_mat%d'%i).strip(),what);everything=asset.evalParm('lk_target%d'%i)==0;row=asset.evalParm('lk_row%d'%i);bound=0
        for k,proto in enumerate(targets):
            if not proto or not proto.IsValid():continue
            if everything or proto_rows.get(k)==row:
                UsdShade.MaterialBindingAPI.Apply(proto).Bind(mat,bindingStrength=UsdShade.Tokens.strongerThanDescendants);bound+=1
        if not bound and not everything and row not in bank:raise hou.NodeError('%s: there is no Prototype Bank row %d (the rows are %s).'%(what,row,', '.join(str(r) for r in sorted(bank)) or 'none'))
        report.append('%s on %s (%d prototype%s)'%(mat.GetPath().name,'all prototypes' if everything else 'row %d'%row,bound,'' if bound==1 else 's'))
    # ---- per-instance variation
    time=Usd.TimeCode.Default();ids=inst.GetIdsAttr().Get(time);proto=inst.GetProtoIndicesAttr().Get(time) or []
    n=len(proto);ids=np.array(list(ids),dtype=np.int64) if ids is not None and len(ids)==n else np.arange(n,dtype=np.int64);proto=np.array(list(proto),dtype=np.int64)
    for i in range(1,asset.evalParm('lk_vars')+1):
        if not asset.evalParm('lk_von%d'%i) or n==0:continue
        what='Variation row %d'%i;kind=asset.evalParm('lk_vtype%d'%i);name=lookdev_primvar(i)
        keys=ids if asset.evalParm('lk_vby%d'%i)==0 else proto
        vals=lookdev_values(keys,asset.evalParmTuple('lk_vmin%d'%i),asset.evalParmTuple('lk_vmax%d'%i),asset.evalParm('lk_vseed%d'%i),i,kind)
        api=UsdGeom.PrimvarsAPI(inst.GetPrim());ptype=kind;rd=inp=None                                           # ptype: the type the primvar is written as (the input's own type when it is wired)
        if asset.evalParm('lk_vwire%d'%i)==0:
            mat=_lk_material(stage,asset.evalParm('lk_vmat%d'%i).strip(),what);sname=asset.evalParm('lk_vshader%d'%i).strip();iname=asset.evalParm('lk_vinput%d'%i).strip()
            spath=Sdf.Path(sname) if sname.startswith('/') else mat.GetPath().AppendPath(sname) if sname else None
            sprim=stage.GetPrimAtPath(spath) if spath else None
            if not sprim or not sprim.IsValid() or not sprim.IsA(UsdShade.Shader):raise hou.NodeError('%s: shader %s is not in material %s.'%(what,sname or '(empty)',mat.GetPath()))
            shader=UsdShade.Shader(sprim);inp=shader.GetInput(iname)
            if not inp:raise hou.NodeError('%s: shader %s has no input %s (inputs: %s).'%(what,sname,iname or '(empty)',', '.join(x.GetBaseName() for x in shader.GetInputs())))
            tname=str(inp.GetTypeName());ptype=2 if tname.startswith('color3') else 0 if tname in ('float','double','half') else 1
            reader=lookdev_reader(shader.GetIdAttr().Get(),ptype)
            if reader is None:raise hou.NodeError('%s: %s is a %s shader, which cannot read a primvar here: use a MaterialX or USD Preview material, or set Connect to Primvar Only and read %s in your shader.'%(what,sname,shader.GetIdAttr().Get(),name))
            rd=UsdShade.Shader.Define(stage,sprim.GetPath().GetParentPath().AppendChild('arraytron_lk%d_reader'%i));rd.CreateIdAttr(reader[0])        # next to the shader it feeds (inside the same MaterialX node graph of a ready-made asset)
            rd.CreateInput(reader[1],Sdf.ValueTypeNames.String if reader[1]=='geomprop' else Sdf.ValueTypeNames.Token).Set(name)
            out=rd.CreateOutput(reader[2],inp.GetTypeName());op=asset.evalParm('lk_vop%d'%i) if asset.parm('lk_vop%d'%i) is not None else 0
            if op==0:inp.ConnectToSource(out)                                                                    # Replace: the input takes the value
            else:                                                                                                  # Multiply / Add: what fed the input (a texture, a constant) is kept and changed by the value
                if not reader[0].startswith('ND_'):raise hou.NodeError('%s: Multiply and Add need a MaterialX shader (%s is %s); use Replace.'%(what,sname,shader.GetIdAttr().Get()))
                t=inp.GetTypeName();mix=UsdShade.Shader.Define(stage,sprim.GetPath().GetParentPath().AppendChild('arraytron_lk%d_%s'%(i,'multiply' if op==1 else 'add')));mix.CreateIdAttr('ND_%s_%s'%('multiply' if op==1 else 'add',LK_TYPES[ptype]))
                in1=mix.CreateInput('in1',t);src=inp.GetConnectedSource()
                if src:in1.ConnectToSource(src[0],src[1])
                elif inp.Get() is not None:in1.Set(inp.Get())
                else:
                    k=1.0 if op==1 else 0.0;in1.Set(k if ptype==0 else Gf.Vec3f(k,k,k))                                  # an input with no value: Multiply by 1 / Add to 0
                mix.CreateInput('in2',t).ConnectToSource(out);inp.ConnectToSource(mix.CreateOutput('out',t))
            report.append('%s.%s varies per %s'%(sprim.GetName(),iname,'instance' if keys is ids else 'prototype'))
        else:report.append('primvar %s written'%name)
        if ptype==0:pv=api.CreatePrimvar(name,Sdf.ValueTypeNames.FloatArray,UsdGeom.Tokens.varying);pv.Set(Vt.FloatArray([float(v) for v in (vals if kind==0 else vals[:,0])]))
        else:
            v3=np.repeat(np.asarray(vals).reshape(-1,1),3,axis=1) if kind==0 else vals
            pv=api.CreatePrimvar(name,Sdf.ValueTypeNames.Color3fArray if ptype==2 else Sdf.ValueTypeNames.Float3Array,UsdGeom.Tokens.varying);pv.Set(Vt.Vec3fArray([Gf.Vec3f(*map(float,v)) for v in v3]))
    return '; '.join(report) if report else 'Nothing to do: add a Material or a Variation row.'

def lookdev_info(asset):
    try:
        g=asset.node('lookdev')
        if g is None:return ''
        text=g.userData('arraytron_lookdev') or ''
        err=g.errors()
        return ('Error: '+err[0]) if err else text
    except Exception as exc:return 'Cannot evaluate: %s'%exc

def lookdev_materials(asset):
    """Menu: the material prims of the stream (path, path)."""
    out=[]
    try:
        from pxr import Usd,UsdShade
        stage=asset.inputs()[0].stage() if asset.inputs() and asset.inputs()[0] is not None else asset.stage()
        for p in stage.Traverse():
            if p.IsA(UsdShade.Material):out+= [str(p.GetPath()),str(p.GetPath())]
            if len(out)>400:break
    except Exception:pass
    return out
