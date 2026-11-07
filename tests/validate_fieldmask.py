"""v1.33.0 in real Houdini: hython tests/validate_fieldmask.py [version]
The Field Stack offers Height, Distance, Exclusion and Mask. The Mask field follows the shape of the node's Mask (here a painted strip along X, 2 each side of Z = 0): Keep Off The Mask removes the points on the
mask (and within a Margin of it), Scatter On The Mask keeps only those, Scatter Around The Mask keeps a ring a Gap off the edge; Softness fades the density at the edges; Mask Effect None leaves the mask's own
effect off so it only gives the shape. Env ARRAYTRON_MUTATE=fm_swap|fm_gap|fm_none|fm_soft breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.34.0':'v1.33.0','v1.33.0':'v1.32.0'}[VID]
TYPE=versions.type_name(VID)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_fieldmask_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'fieldmask.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(versions.hda(VID)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def strip(a,radius=2.0):
    m=a.hdaModule();st=m.maskpaint_data(a)
    for x in np.linspace(-9.0,9.0,19):st,_=m.maskpaint_add(st,0,(float(x),0.0,0.0),radius,1.0,0.0,1.0,0)
    m.maskpaint_apply(a,st)
def node(stage,source,name='Fm',count=20000,mode=1,**field):
    a=stage.createNode(TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('mode').set(1);a.parm('area_count').set(count);a.parm('area_sizex').set(24.0);a.parm('area_sizez').set(16.0)
    a.parm('mask_source').set(4);a.parm('mask_paint_base').set(0.0);a.parm('mask_paint_blur').set(0.0);a.parm('mask_paint_res').set(400);strip(a);a.parm('mask_effect').set(3)       # the paint only gives the shape
    a.parm('fields').set(1);a.parm('field_type1').set(6);a.parm('field_mmode1').set(mode)
    for k,v in field.items():a.parm(k).set(v)
    mutate(a);return a
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def out(a):
    a.stage();errs=all_errors(a);assert not errs,errs;pi=UsdGeom.PointInstancer(a.stage().GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3);ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int);o=np.argsort(ids);return pos[o],ids[o]
def mutate(a):
    g=a.hdaModule().mask_field_value.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='fm_swap':
        good=g['mask_field_value'];g['mask_field_value']=lambda S,mode,grow,gap,ring,soft:good(S,1-mode if mode<2 else mode,grow,gap,ring,soft)                                                # on and off swapped
    elif MUTATE=='fm_gap':
        good=g['mask_field_value'];g['mask_field_value']=lambda S,mode,grow,gap,ring,soft:good(S,mode,grow,0.0,ring,soft)                                                                # the Gap is ignored
    elif MUTATE=='fm_none':
        good=g['sop_mask']
        def bad(geo,asset):
            asset.parm('mask_effect').set(0);good(geo,asset)                                                                                                                          # the mask removes points itself
        g['sop_mask']=bad
    elif MUTATE=='fm_soft':
        good=g['mask_field_value'];g['mask_field_value']=lambda S,mode,grow,gap,ring,soft:good(S,mode,grow,gap,ring,0.0)                                                                 # Softness is ignored
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def dz(pos):return np.abs(pos[np.abs(pos[:,0])<8.0][:,2])                                                                                  # the strip is straight from X = -9 to 9 (round caps beyond): look at the points well inside it

def menu():
    st,sc=new_scene('menu');a=node(st,sc,name='M');p=a.parm('field_type1');t=p.parmTemplate()
    assert tuple(t.menuLabels())==('Height','Distance','Exclusion','Mask'),t.menuLabels();assert tuple(t.menuItems())==('0','4','5','6')
    for token,label in ((0,'Height'),(4,'Distance'),(5,'Exclusion'),(6,'Mask')):
        p.set(token);assert p.eval()==token and t.menuLabels()[t.menuItems().index(str(token))]==label
    assert 'None (shape only)' in a.parm('mask_effect').parmTemplate().menuLabels()
    for k in ('field_mmode1','field_mgrow1','field_mgap1','field_mring1','field_msoft1','field_mlevel1'):assert a.parm(k) is not None,k

def keep_off():
    st,sc=new_scene('off');base=node(st,sc,name='Base',mode=1);a=base;pos,ids=out(a);full=node(st,sc,name='Full');full.parm('fields').set(0);pf,idf=out(full)
    assert len(pf)>15000 and len(pos)<len(pf)*0.8 and len(pos)>len(pf)*0.4,(len(pos),len(pf))                                                  # the strip is 4 of 16 deep: about a quarter goes
    assert dz(pos).min()>1.85,dz(pos).min();assert (dz(pf)<1.8).sum()>2000                                                                    # nothing on the mask (the paint edge is a cell soft), plenty before
    assert np.isin(ids,idf).all()                                                                                                             # the survivors keep their ids
    m=node(st,sc,name='Margin',field_mgrow1=1.0);pm,_=out(m);assert dz(pm).min()>2.85 and len(pm)<len(pos),dz(pm).min()                       # a margin of 1 clears 1 more each side

def on_mask():
    st,sc=new_scene('on');a=node(st,sc,name='On',mode=0);pos,ids=out(a);assert len(pos)>2000 and dz(pos).max()<2.15,dz(pos).max()
    full=node(st,sc,name='Full');full.parm('fields').set(0);assert len(pos)<len(out(full)[0])*0.35
    g=node(st,sc,name='Grow',mode=0,field_mgrow1=1.0);pg,_=out(g);assert dz(pg).max()<3.2 and dz(pg).max()>2.6 and len(pg)>len(pos),(dz(pg).max(),len(pg),len(pos))

def around():
    st,sc=new_scene('around');a=node(st,sc,name='Ring',mode=2,field_mgap1=0.5,field_mring1=1.5);pos,_=out(a)
    assert len(pos)>1500 and dz(pos).min()>2.3 and dz(pos).max()<4.15,(len(pos),dz(pos).min(),dz(pos).max())                                    # the strip edge is at 2: the ring runs from 2.5 to 4 (the painted edge is a fraction of a cell soft)
    assert (dz(pos)<2.9).sum()>200 and (dz(pos)>3.6).sum()>200                                                                                  # the whole ring is filled, both ends
    b=node(st,sc,name='NoGap',mode=2,field_mgap1=0.0,field_mring1=1.5);pb,_=out(b);assert dz(pb).min()>1.85 and dz(pb).min()<2.3 and dz(pb).max()<3.65,(dz(pb).min(),dz(pb).max())   # no gap: the ring starts at the edge

def softness():
    st,sc=new_scene('soft');a=node(st,sc,name='Hard',mode=1);b=node(st,sc,name='Soft',mode=1,field_msoft1=2.0)
    ph,_=out(a);ps,_=out(b);zh=dz(ph);zs=dz(ps)
    bins=np.arange(1.0,5.01,1.0);full=node(st,sc,name='Full');full.parm('fields').set(0);zf=dz(out(full)[0])
    dens=lambda z:np.array([((z>=lo)&(z<lo+1.0)).sum() for lo in bins[:-1]],dtype=float)/np.maximum(np.array([((zf>=lo)&(zf<lo+1.0)).sum() for lo in bins[:-1]],dtype=float),1.0)
    dh,ds=dens(zh),dens(zs);assert dh[0]<0.05 and dh[2]>0.95,dh                                                                                    # hard: gone to 2, all beyond
    assert ds[1]>0.05 and ds[1]<0.95 and ds[0]<ds[1]<=ds[2]+0.05 and ds[3]>0.8,ds                                                                   # soft: a slope over the 2 beyond the edge

def effect_none():
    st,sc=new_scene('none');a=node(st,sc,name='None');pos,_=out(a);g=a.node('USD_COMPILER/MASK_PROCESSOR').geometry();assert g.attribValue('mask_after')==g.attribValue('mask_before'),'the mask removed points itself'
    b=node(st,sc,name='Dens');b.parm('mask_effect').set(0);pb,_=out(b);assert len(pb)<len(pos)*0.6,(len(pb),len(pos))                                  # with Density the mask keeps only the strip, then the field removes the strip: nearly nothing

def needs_mask():
    st,sc=new_scene('nomask');a=node(st,sc,name='NoMask');a.parm('mask_source').set(0);a.stage();errs=all_errors(a);assert any('Mask Source' in str(e) for e in errs),errs

def legacy():
    st,sc=new_scene('legacy');a=node(st,sc,name='Old');a.parm('field_type1').set(0);a.parm('field_hmin1').set(-1.0);a.parm('field_hmax1').set(1.0);pos,_=out(a);assert len(pos)>1000
    a.parm('field_type1').set(2);pos2,_=out(a);assert 1000<len(pos2)<len(pos)*1.001                                                                  # a Noise row (no longer offered) still evaluates

for n,f in (('the Field menu offers Height, Distance, Exclusion and Mask',menu),('Keep Off The Mask with and without a Margin',keep_off),('Scatter On The Mask, with a Margin',on_mask),
            ('Scatter Around The Mask: a ring a Gap off the edge',around),('Softness fades the density at the edges',softness),('Mask Effect None leaves the mask effect off',effect_none),
            ('the Mask field asks for a Mask Source',needs_mask),('Slope, Noise and Image rows made before still evaluate',legacy)):check(n,f)
result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
if not MUTATE:(ROOT/'tests'/('validation_fieldmask_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
print('ALL PASSED %d'%len(checks));print(json.dumps(checks))
