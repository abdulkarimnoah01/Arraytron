"""v1.32.0 in real Houdini: hython tests/validate_maskfade.py [version]
Edge Fade: the edge of ANY mask (the painted mask and the Houdini paint included) is re-faded with a Fade Width, Grow / Shrink, Fade Level and Fade Curve of your own, whatever softness it was painted with;
and the instances follow the mask: the density is the weight, the scale is Min Scale + (1 - Min Scale) x weight, or a Scale Response curve of it. Env ARRAYTRON_MUTATE=mf_off|mf_signed|mf_curve|mf_scale
breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.38.3':'v1.38.2','v1.38.2':'v1.38.1','v1.38.1':'v1.38.0','v1.38.0':'v1.37.0','v1.37.0':'v1.36.0','v1.36.0':'v1.35.0','v1.35.0':'v1.34.1','v1.34.1':'v1.34.0','v1.34.0':'v1.33.0','v1.33.0':'v1.32.0','v1.32.0':'v1.31.1'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_maskfade_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'maskfade.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def area(stage,source,name='Mf',typ=None,count=20000,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('mode').set(1);a.parm('area_count').set(count);a.parm('area_sizex').set(24.0);a.parm('area_sizez').set(16.0)
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    a.stage();errs=all_errors(a);assert not errs,errs;pi=UsdGeom.PointInstancer(a.stage().GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    d=dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),scale=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3)[:,0]);o=np.argsort(d['ids']);return {k:v[o] for k,v in d.items()}
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def mutate(a):
    g=a.hdaModule().mask_fade.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='mf_off':g['mask_fade']=lambda asset,P:g['_mask_values_raw'](asset,P,np.arange(len(P)))                                                                                      # Edge Fade does nothing
    elif MUTATE=='mf_signed':
        good=g['mask_signed_field'];g['mask_signed_field']=lambda w,level,cell,reach=None:np.abs(good(w,level,cell))                                                                      # no inside / outside
    elif MUTATE=='mf_curve':
        good=g['falloff_curve'];g['falloff_curve']=lambda t,kind,inner=0.0:good(t,0,inner)                                                                                              # the Fade Curve is ignored
    elif MUTATE=='mf_scale':g['mask_scale_response']=lambda asset,w:w                                                                                                                    # the Scale Response curve is ignored
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def strip(a,radius,feather,curve=0,xs=np.linspace(-9.0,9.0,19)):
    m=a.hdaModule();st=m.maskpaint_data(a)
    for x in xs:st,_=m.maskpaint_add(st,0,(float(x),0.0,0.0),radius,1.0,feather,1.0,curve)
    m.maskpaint_apply(a,st)
def paintedmask(a):a.parm('mask_source').set(4);a.parm('mask_paint_base').set(0.0);a.parm('mask_paint_blur').set(0.0);a.parm('mask_paint_res').set(400)
def probe(a,zs=np.linspace(-6.0,6.0,121),x=0.0):
    G=np.stack([np.full(len(zs),x),np.zeros(len(zs)),zs],1);return a.hdaModule().mask_values(a,G,np.arange(len(G)))
def at(zs,w,z):return float(np.interp(z,zs,w))
def edge_of(zs,w):
    k=zs>=0;return float(np.interp(-0.5,-w[k],zs[k]))
def fade(a,width=3.0,grow=0.0,curve=1,level=0.5):
    a.parm('mask_fade_on').set(1);a.parm('mask_fade_width').set(width);a.parm('mask_fade_grow').set(grow);a.parm('mask_fade_curve').set(curve);a.parm('mask_fade_level').set(level)

def independent():
    st,sc=new_scene('indep');zs=np.linspace(-6.0,6.0,121)
    hard=area(st,sc,name='Hard');paintedmask(hard);strip(hard,2.0,0.0);soft=area(st,sc,name='Soft');paintedmask(soft);strip(soft,3.6,0.9)                                                      # a hard strip 2 wide each side, and a very soft one with its 0.5 contour at the same place
    wh0,ws0=probe(hard,zs),probe(soft,zs);eh,es=edge_of(zs,wh0),edge_of(zs,ws0);assert abs(eh-2.0)<0.2 and at(zs,wh0,eh-0.3)>0.98 and at(zs,wh0,eh+0.3)<0.02                                                  # the hard paint: a crisp edge
    assert at(zs,ws0,es-1.0)<0.97 and at(zs,ws0,es+0.5)>0.05 and at(zs,wh0,eh+0.3)<0.02,'the soft paint has a long soft slope, the hard one a crisp edge'
    fade(hard);fade(soft);wh,ws=probe(hard,zs),probe(soft,zs)
    for o in (-2.0,-1.0,0.0,1.0,2.0):assert abs(at(zs,wh,eh+o)-at(zs,ws,es+o))<0.12,(o,at(zs,wh,eh+o),at(zs,ws,es+o))                                                                       # after Edge Fade they are the same mask around their own edges: it does not depend on the brush softness
    assert at(zs,wh,0.0)>0.97 and abs(at(zs,wh,eh)-0.5)<0.1 and at(zs,wh,eh+1.8)<0.04 and at(zs,wh,eh-1.8)>0.96 and at(zs,wh,5.8)<0.01                                                          # 1 inside, 0.5 on the edge, 0 beyond a half width
    w2=area(st,sc,name='Wide');paintedmask(w2);strip(w2,2.0,0.0);fade(w2,width=6.0);ww=probe(w2,zs);assert 0.6<at(zs,ww,eh-1.0)<0.95 and 0.05<at(zs,ww,eh+1.0)<0.4 and abs(at(zs,ww,eh)-0.5)<0.1    # a wide fade is a long slope across the same edge
    n=area(st,sc,name='Narrow');paintedmask(n);strip(n,2.0,0.9,xs=np.linspace(-9,9,19));fade(n,width=0.4);wn=probe(n,zs);en=edge_of(zs,probe(n,zs));assert at(zs,wn,en-0.4)>0.9 and at(zs,wn,en+0.4)<0.1                                  # a narrow fade is a crisp edge, also on a soft paint

def grow_shrink():
    st,sc=new_scene('grow');zs=np.linspace(-7.0,7.0,141);a=area(st,sc,name='G');paintedmask(a);strip(a,2.0,0.0);fade(a,width=2.0,grow=1.0);w=probe(a,zs,0.0)
    assert abs(at(zs,w,3.0)-0.5)<0.12 and at(zs,w,1.0)>0.9 and at(zs,w,4.2)<0.05                                                                                                           # Grow 1: the edge is at 3
    b=area(st,sc,name='S');paintedmask(b);strip(b,2.0,0.0);fade(b,width=2.0,grow=-1.0);w=probe(b,zs);assert abs(at(zs,w,1.0)-0.5)<0.12 and at(zs,w,0.0)>0.9 and at(zs,w,2.2)<0.05                    # Shrink 1: the edge is at 1
    c=area(st,sc,name='L');paintedmask(c);strip(c,3.6,0.9);fade(c,width=2.0,level=0.2);wl=probe(c,zs);lc=area(st,sc,name='L2');paintedmask(lc);strip(lc,3.6,0.9);fade(lc,width=2.0,level=0.8);wh=probe(lc,zs)
    el=lambda w:zs[(zs>0)][np.argmin(np.abs(w[zs>0]-0.5))];assert el(wl)>el(wh)+0.5,(el(wl),el(wh))                                                                                         # a lower Fade Level puts the edge farther out

def curves():
    st,sc=new_scene('curves');zs=np.linspace(-6.0,6.0,241);res={}
    for k,name in enumerate(('Linear','Smooth','Gaussian')):
        a=area(st,sc,name=name);paintedmask(a);strip(a,2.0,0.0);fade(a,width=4.0,curve=k);res[k]=at(zs,probe(a,zs),2.0+1.0)                                                                   # a quarter of the width inside the edge... outside by 1 of 4: t = 0.75
    assert abs(res[0]-0.25)<0.07 and abs(res[1]-0.156)<0.07 and abs(res[2]-0.0)<0.15 and res[0]>res[1]>res[2]-0.2,res                                                                    # Linear 0.25, Smooth 0.156, Gaussian lower still: different shapes of the same fade

def houdini_paint():
    st,sc=new_scene('hp');a=area(st,sc,name='Hp');m=a.hdaModule();gx=np.linspace(-14,14,200);gz=np.linspace(-9,9,130);X,Z=np.meshgrid(gx,gz);Pm=np.stack([X.ravel(),np.zeros(X.size),Z.ravel()],1)
    soft=np.exp(-(Pm[:,2]/1.5)**2*1.0);grid,spec=m.hpaint_grid(Pm,soft,0.0,200);a.parm('mask_hpaint_data').set(m.hpaint_encode(grid,spec));a.parm('mask_source').set(5)
    zs=np.linspace(-6.0,6.0,121);raw=probe(a,zs);edge=float(np.sqrt(-np.log(0.5))*1.5);assert at(zs,raw,0.0)>0.97 and abs(at(zs,raw,edge)-0.5)<0.08                                                          # a bell shaped Houdini paint: 0.5 at its edge
    fade(a,width=1.0);wf=probe(a,zs);assert at(zs,wf,edge-0.8)>0.95 and at(zs,wf,edge+0.8)<0.05 and abs(at(zs,wf,edge)-0.5)<0.12                                                                  # re-faded to a 1 unit slope on the same edge, from the Houdini paint
    fade(a,width=5.0);wide=probe(a,zs);assert at(zs,wide,edge+1.0)>0.1 and at(zs,wide,edge-1.0)<0.9 and abs(at(zs,wide,edge)-0.5)<0.12                                                                                          # or a 5 unit one
    a.parm('mask_effect').set(2);a.parm('mask_minscale').set(0.0);o=out(a);r=np.abs(o['pos'][:,2]);assert len(o['ids'])>100 and (r<edge+3.2).all()                                                     # the scatter follows it

def follow():
    st,sc=new_scene('follow');a=area(st,sc,name='F',count=30000);paintedmask(a);strip(a,4.0,0.9);a.parm('mask_effect').set(2);a.parm('mask_minscale').set(0.0);m=a.hdaModule();o=out(a)
    w=m.mask_weights(a,m.mask_values(a,o['pos'],o['ids']));assert len(o['ids'])>1000 and np.abs(o['scale']-w).max()<1e-3,(np.abs(o['scale']-w).max())                                           # the scale IS the weight (Min Scale 0)
    base=area(st,sc,name='B',count=30000);bw=m.mask_weights(a,m.mask_values(a,np.array(base.hdaModule().mask_values.__globals__ and out(base)['pos']),np.arange(1)) if False else None) if False else None
    b=area(st,sc,name='Bd',count=30000);b.parm('mask_source').set(0);ob=out(b);wb=m.mask_weights(a,m.mask_values(a,ob['pos'],ob['ids']));zs=np.abs(ob['pos'][:,2])
    for lo,hi in ((0.0,1.5),(1.5,2.5),(2.5,3.2),(3.2,4.0)):
        sel=(zs>=lo)&(zs<hi);kept=np.isin(ob['ids'][sel],o['ids']).mean();want=wb[sel].mean();assert abs(kept-want)<0.06,(lo,hi,kept,want)                                                    # the density is the weight: the share of points kept follows the mask
    a.parm('mask_fade_on').set(1);fade(a,width=4.0);o2=out(a);w2=m.mask_weights(a,m.mask_values(a,o2['pos'],o2['ids']));assert np.abs(o2['scale']-w2).max()<1e-3 and len(o2['ids'])!=len(o['ids'])      # with Edge Fade: they follow the re-faded mask
    a.parm('mask_fade_on').set(0);a.parm('mask_minscale').set(0.2);o3=out(a);assert np.abs(o3['scale']-(0.2+0.8*w)).max()<1e-3                                                                 # Min Scale lifts the floor
    a.parm('mask_minscale').set(0.0);a.parm('mask_scale_curve_on').set(1);a.parm('mask_scale_curve').set(hou.Ramp((hou.rampBasis.Linear,hou.rampBasis.Linear),(0.0,1.0),(1.0,0.0)));o4=out(a)
    assert np.array_equal(o4['ids'],o['ids']) and np.abs(o4['scale']-(1.0-w)).max()<2e-3,(np.abs(o4['scale']-(1.0-w)).max())                                                             # the Scale Response curve: the scale on its own curve, the density unchanged
    a.parm('mask_scale_curve').set(hou.Ramp((hou.rampBasis.Linear,hou.rampBasis.Linear,hou.rampBasis.Linear),(0.0,0.5,1.0),(0.0,0.0,1.0)));o5=out(a);ws=np.where(w<0.5,0.0,(w-0.5)*2.0);assert np.abs(o5['scale']-ws).max()<2e-3     # a hinge: nothing below 0.5, then up

def sources():
    st,sc=new_scene('src');n=area(st,sc,name='N',count=9000);n.parm('mask_source').set(1);n.parm('mask_noise_freq').set(0.3);n.parm('mask_effect').set(0);o0=out(n);fade(n,width=1.5);o1=out(n);assert len(o0['ids'])>500 and len(o1['ids'])>500 and not np.array_equal(o0['ids'],o1['ids'])   # a noise mask: re-faded
    P=np.array([[0.0,0.0,0.0],[5.0,0.0,0.0]]);w=n.hdaModule().mask_values(n,P,np.arange(2));assert np.all((w>=0.0)&(w<=1.0))
    z=area(st,sc,name='Z');z.parm('mask_fade_on').set(1);assert len(out(z)['ids'])==20000                                                                                                    # no mask source: Edge Fade does nothing
    old=area(st,sc,name='Old',typ=OLD_TYPE,count=9000);old.parm('mask_source').set(1);old.parm('mask_noise_freq').set(0.3);old.parm('mask_effect').set(0);oo=out(old)
    n2=area(st,sc,name='N2',count=9000);n2.parm('mask_source').set(1);n2.parm('mask_noise_freq').set(0.3);n2.parm('mask_effect').set(0);o2=out(n2);assert np.array_equal(o2['ids'],oo['ids']) and np.abs(o2['pos']-oo['pos']).max()<1e-9      # Edge Fade off: the previous release exactly

def interface():
    st,sc=new_scene('ui');a=area(st,sc,name='Ui');g=a.parmTemplateGroup();d=lambda n:g.find(n).defaultValue()
    for n in ('mask_fade_on','mask_fade_width','mask_fade_grow','mask_fade_curve','mask_fade_level','mask_fade_res','mask_scale_curve_on','mask_scale_curve'):assert g.find(n) is not None,n
    assert d('mask_fade_on')==False and d('mask_fade_width')==(2.0,) and d('mask_fade_grow')==(0.0,) and d('mask_fade_curve')==1 and d('mask_fade_level')==(0.5,) and d('mask_fade_res')==(256,) and d('mask_scale_curve_on')==False
    assert g.find('mask_fade_curve').menuLabels()==('Linear','Smooth','Gaussian');hide=lambda n:g.find(n).conditionals().get(hou.parmCondType.HideWhen);assert '{ mask_fade_on == 0 }' in hide('mask_fade_width') and '{ mask_source == 0 }' in hide('mask_fade_on') and '{ mask_scale_curve_on == 0 }' in hide('mask_scale_curve')
    tabs=dict((t.label(),[x.name() for x in t.parmTemplates()]) for t in g.entries() if t.type()==hou.parmTemplateType.Folder);sc_=tabs['Scatter']
    assert all(n in sc_ for n in ('mask_fade_on','mask_fade_width','mask_fade_grow','mask_fade_curve','mask_scale_curve_on')) and sc_.index('mask_high')<sc_.index('mask_fade_on')<sc_.index('mask_fade_width')<sc_.index('mask_minscale')<sc_.index('mask_scale_curve_on')<sc_.index('fields')
    assert g.find('mask_fade_level') is not None and 'mask_fade_level' not in sc_ and 'mask_fade_res' not in sc_                                                                                    # the level and the resolution are in Mask Details
    for n in ('mask_fade','mask_scale_response','_mask_values_raw'):assert hasattr(a.hdaModule(),n),n
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('def mask_fade(')[1].split('def falloff_mask_t')[0]

def main():
    for name,func in (('Edge Fade: the fade no longer depends on the paint softness (hard and soft paints give the same mask), the width, a narrow and a wide fade',independent),
                      ('Grow / Shrink and Fade Level move the edge',grow_shrink),
                      ('Fade Curve: Linear, Smooth, Gaussian',curves),
                      ('Edge Fade on the Houdini paint (a bell shaped map), narrow and wide, and the scatter follows it',houdini_paint),
                      ('The instances follow the mask: the density is the weight, the scale is the weight (Min Scale), a Scale Response curve, with Edge Fade',follow),
                      ('Other sources: a noise mask, no source, and Edge Fade off is the previous release exactly',sources),
                      ('Interface: parameters, defaults, conditionals, the order in the Scatter tab, module functions, no dollar signs',interface)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_maskfade_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
