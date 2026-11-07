"""Build the full mask brush demo (v1.27.0): hython tools/build_demo_maskfull_v1270.py
Three hilly patches (Python LOP terrains, one Arraytron node each, spheres of the built-in test setup, Surface mode). The paint is written the way the viewport brush writes it (maskpaint_stamps_for +
maskpaint_mirrors + maskpaint_add, one stamp per dab), so the file shows what a painting session with the full operations produces:
  A  Symmetry and Smooth: one blob painted with Symmetry X (about the middle of the patch, so it appears twice), then a Smooth stroke over both - soft borders on a hard painting.
  B  Fill, Erase, Multiply, Minimum: Fill Mask (Foreground 1: a full scatter), a clearing erased, a band thinned with Multiply 0.4 and a corner capped with Minimum 0.6.
  C  Foreground and Background: a stripe painted with Paint (Foreground 1), a stripe with Paint Background (0.35), Maximum 0.7 lifting a patch of the thin stripe.
Asserts what the picture should show. Writes dist/Arraytron_<version>_maskfull_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'maskfull')
TERRAINS='''from pxr import Gf, UsdGeom, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
n=40;size=20.0
for name,x0 in (('TerrainA',0.0),('TerrainB',24.0),('TerrainC',48.0)):
    mesh=UsdGeom.Mesh.Define(stage,'/World/'+name)
    points=[]
    for j in range(n+1):
        for i in range(n+1):
            x=x0+size*i/n;z=-size/2+size*j/n
            points.append(Gf.Vec3f(x,0.8*math.sin(x*0.4)*math.cos(z*0.35)+0.25*math.sin(z*1.1),z))
    indices=[]
    for j in range(n):
        for i in range(n):
            indices+=[j*(n+1)+i,(j+1)*(n+1)+i,(j+1)*(n+1)+i+1,j*(n+1)+i+1]
    mesh.CreatePointsAttr(Vt.Vec3fArray(points))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(indices))
    mesh.CreateSubdivisionSchemeAttr('none')
    mesh.CreateDisplayColorAttr([Gf.Vec3f(0.35,0.5,0.3)])
'''
def node(stage,terrain,name,prim,out,comment,**values):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.parm('outputpath').set(out);a.setInput(0,terrain)
    assert a.evalParm('copy_test_ground')==0
    a.parm('surface_prim').set(prim);a.parm('surface_count').set(1800);a.parm('scale_min').set(0.25);a.parm('scale_max').set(0.4)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
def session(m,rows,fg=1.0,bg=0.0,sym=(False,False,(0.0,0.0))):
    """The paint of a session: rows of (menu entry, x, z, radius, strength, feather, curve, foreground override) added the way the brush adds them: through the menu entry, the symmetry and maskpaint_add."""
    data=np.zeros((0,m.MASKPAINT_COLUMNS))
    for menu,x,z,r,s,f,c,*over in rows:
        what=m.maskpaint_stamp_for(menu,over[0] if over else fg,bg)
        for p in m.maskpaint_mirrors((x,0.0,z),sym[0],sym[1],sym[2]):data,_=m.maskpaint_add(data,what[0],p,r,s,f,what[1],c)
    return data

hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage');terrain=stage.createNode('pythonscript','external_terrains');terrain.parm('python').set(TERRAINS)
terrain.setComment('Three hilly patches (Python LOP): /World/TerrainA, B and C.');terrain.setGenericFlag(hou.nodeFlag.DisplayComment,True)
probe=stage.createNode(TYPE,'probe');m=probe.hdaModule();probe.destroy()
blob=[(0,x,z,2.2,1.0,0.7,1) for x,z in ((3.0,-2.0),(4.2,-0.6),(5.0,1.0),(4.4,2.6))]                                                     # A: a blob painted on the left half, Symmetry X about the middle (x 10)
soft=[(4,x,z,3.2,1.0,0.8,1) for x,z in ((3.2,-2.0),(4.5,0.2),(4.6,2.4),(16.8,-2.0),(15.5,0.2),(15.4,2.4))]                          # ... and a Smooth stroke over both
symA=(True,False,(10.0,0.0));a_stamps=np.vstack([session(m,blob,sym=symA),session(m,soft,sym=(False,False,(0.0,0.0)))])
b_rows=[(1,34.0,0.0,2.8,1.0,0.5,1)]+[(5,24.0+x,-6.0,2.4,1.0,0.7,1,0.4) for x in np.linspace(1.0,19.0,10)]+[(7,24.0+x,z,2.5,1.0,0.7,1,0.6) for x,z in ((17.0,7.0),(19.0,8.0),(15.0,8.5))]  # B: a clearing, a thinned band, a capped corner
b_stamps=np.vstack([session(m,[(1,34.0,0.0,2.8,1.0,0.5,1)]),session(m,b_rows[1:11],fg=0.4),session(m,b_rows[11:],fg=0.6)])
bg_rows=[(8,48.0+x,3.5,2.6,1.0,0.8,1) for x in np.linspace(2.0,18.0,12)]                                                              # C: a thin stripe (Background 0.35) ...
fg_rows=[(0,48.0+x,-4.0,2.6,1.0,0.8,1) for x in np.linspace(2.0,18.0,12)]                                                              # ... a full stripe (Foreground 1) ...
lift=[(6,48.0+x,3.5,2.2,1.0,0.8,1,0.7) for x in (6.0,7.5,9.0)]                                                                       # ... and Maximum 0.7 lifting a patch of the thin stripe
c_stamps=np.vstack([session(m,bg_rows,bg=0.35),session(m,fg_rows),session(m,lift)])
a=node(stage,terrain,'Arraytron_A_SymmetrySmooth','/World/TerrainA','/World/ArraytronA','A: Symmetry X mirrors the blob about x = 10, then a Smooth stroke softens the borders of both.',mask_source=4,mask_sym_x=1,mask_sym_center=(10.0,0.0),mask_paint_data=m.maskpaint_encode(a_stamps))
b=node(stage,terrain,'Arraytron_B_FillErase','/World/TerrainB','/World/ArraytronB','B: Fill Mask (a full scatter), a clearing erased, a band thinned with Multiply 0.4 and a corner capped with Minimum 0.6.',mask_source=4,mask_paint_base=1.0,mask_paint_data=m.maskpaint_encode(b_stamps))
c=node(stage,terrain,'Arraytron_C_ForegroundBackground','/World/TerrainC','/World/ArraytronC','C: a full stripe (Paint, Foreground 1), a thin stripe (Paint Background 0.35) and Maximum 0.7 lifting a patch of the thin one.',mask_source=4,mask_brush_bg=0.35,mask_paint_data=m.maskpaint_encode(c_stamps))
merge=stage.createNode('merge','merge_all')
for k,n in enumerate((a,b,c)):merge.setInput(k,n)
merge.setDisplayFlag(True)
for n in (a,b,c):assert not n.errors(),(n.name(),n.errors())
def pos(n):
    s=n.stage();return np.array(UsdGeom.PointInstancer(s.GetPrimAtPath(n.evalParm('outputpath'))).GetPositionsAttr().Get(hou.frame())).reshape(-1,3)
pa,pb,pc=pos(a),pos(b),pos(c)
left=pa[:,0]<10.0;assert len(pa)>150 and left.sum()>40 and (~left).sum()>40 and abs(left.sum()-(~left).sum())<0.4*len(pa)                                   # A: two mirrored blobs of about the same size
gx,gz=np.meshgrid(np.linspace(24.0,44.0,201),np.linspace(-10.0,10.0,201));cellarea=400.0/201**2                                          # regions measured on a grid over the patch, so the densities are per unit of area
def region(x,z):return (np.hypot(x-34.0,z)<2.0,(np.hypot(x-34.0,z)>4.5)&(np.abs(z+6.0)>2.0)&(z<5.0),np.abs(z+6.0)<1.5)
hole_g,away_g,band_g=region(gx,gz);hole,away,band=region(pb[:,0],pb[:,2]);dens=lambda sel,grid:sel.sum()/(grid.sum()*cellarea)
assert len(pb)>700 and dens(hole,hole_g)<0.35*dens(away,away_g),(dens(hole,hole_g),dens(away,away_g))                                   # B: the clearing is far thinner than the rest
assert dens(band,band_g)<0.7*dens(away,away_g),(dens(band,band_g),dens(away,away_g))                                                   # B: the band is thinner than the rest
thin=np.abs(pc[:,2]-3.5)<1.5;full=np.abs(pc[:,2]+4.0)<1.5;assert full.sum()>2.0*thin.sum()>0 and len(pc)>100                                           # C: the full stripe is denser than the thin one
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A':len(pa),'A_left_right':[int(left.sum()),int((~left).sum())],'B':len(pb),'C':len(pc),'C_full_thin':[int(full.sum()),int(thin.sum())]}))
