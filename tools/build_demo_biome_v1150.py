"""Build the Biome demo (v1.15.0, Effects in v1.16.0): hython tools/build_demo_biome_v1150.py
A hilly terrain with a pond (written once as test_assets/biome_terrain.usda and biome_pond.usda) and four biomes in one Biome node: a Forest of firs on the mid slopes near water (elevation, slope,
moisture and temperature bands with soft edges), stunted Alpine firs where it is cold (high up), Cliff rocks on the steep faces and Shore stones around the pond. The moisture is the distance to the pond,
the temperature falls with the height (a stylised lapse rate). primvars:biome is written and the Biome debug colours are available. Writes dist/Arraytron_<version>_biome_demo.hip or the 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json, math
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'biome');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
from pxr import Usd, UsdGeom, Vt
def height(x,z):
    return (0.4+7.5*math.exp(-((x-4.0)**2+(z+1.0)**2)/(2*5.0**2))+3.6*math.exp(-((x+7.0)**2+(z-6.0)**2)/(2*3.4**2))+1.2*math.sin(x*0.5)*math.cos(z*0.4)*0.5
            -1.1*math.exp(-((x+7.0)**2+(z+6.0)**2)/(2*2.6**2)))
for folder in (ROOT/'dist/test_assets',ROOT/'otls_h205/test_assets'):
    if not folder.exists() or (folder/'biome_terrain.usda').exists():continue
    n=64;xs=np.linspace(-12,12,n+1);st=Usd.Stage.CreateNew(str(folder/'biome_terrain.usda'));root=UsdGeom.Xform.Define(st,'/BiomeTerrain');st.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(st,UsdGeom.Tokens.y)
    pts=[(float(x),float(height(x,z)),float(z)) for z in xs for x in xs];idx=[]
    for j in range(n):
        for i in range(n):a=j*(n+1)+i;idx+=[a,a+n+1,a+n+2,a+1]
    m=UsdGeom.Mesh.Define(st,'/BiomeTerrain/Ground');m.CreatePointsAttr(pts);m.CreateFaceVertexCountsAttr([4]*(n*n));m.CreateFaceVertexIndicesAttr(idx);m.CreateOrientationAttr('rightHanded');m.CreateSubdivisionSchemeAttr('catmullClark')
    m.CreateDisplayColorAttr([(0.34,0.30,0.22)]);st.GetRootLayer().Save()
    ps=Usd.Stage.CreateNew(str(folder/'biome_pond.usda'));pr=UsdGeom.Xform.Define(ps,'/BiomePond');ps.SetDefaultPrim(pr.GetPrim());UsdGeom.SetStageUpAxis(ps,UsdGeom.Tokens.y)
    k=32;cx,cz,cy,rad=-7.0,-6.0,0.05,2.5;disc=[(cx,cy,cz)]+[(cx+rad*math.cos(2*math.pi*t/k),cy,cz+rad*math.sin(2*math.pi*t/k)) for t in range(k)];tri=[]
    for t in range(k):tri+=[0,1+(t+1)%k,1+t]
    pm=UsdGeom.Mesh.Define(ps,'/BiomePond/Water');pm.CreatePointsAttr(disc);pm.CreateFaceVertexCountsAttr([3]*k);pm.CreateFaceVertexIndicesAttr(tri);pm.CreateOrientationAttr('rightHanded');pm.CreateDisplayColorAttr([(0.18,0.35,0.55)]);ps.GetRootLayer().Save()
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
fir=reference('reference_fir','/World/Props/Fir',ASSETS+'/fir.usda');rock=reference('reference_rock','/World/Props/Rock',ASSETS+'/rock.usda',fir);stone=reference('reference_stone','/World/Props/Stone',ASSETS+'/stone.usda',rock)
terrain=reference('reference_terrain','/World/Terrain',ASSETS+'/biome_terrain.usda',stone);pond=reference('reference_pond','/World/Pond',ASSETS+'/biome_pond.usda',terrain)
biome=stage.createNode(TYPE,'Arraytron_Biome');biome.setInput(0,pond);biome.parm('outputpath').set('/World/Biomes');biome.parm('mode').set(10)
biome.parm('protos').set(3);biome.parm('proto_prim1').set('/World/Props/Fir');biome.parm('proto_scale1').set(3.0);biome.parm('proto_prim2').set('/World/Props/Rock');biome.parm('proto_scale2').set(0.8);biome.parm('proto_prim3').set('/World/Props/Stone');biome.parm('proto_scale3').set(18.0)
biome.parm('biome_prim').set('/World/Terrain');biome.parm('biome_seed').set(5);biome.parm('biome_normal').set(1);biome.parm('biome_align').set(0.5)
biome.parm('biome_moist_mode').set(2);biome.parm('biome_water').set('/World/Pond');biome.parm('biome_water_reach').set(16.0);biome.parm('biome_moist_noise').set(0.18);biome.parm('biome_noise_freq').set(0.12)
biome.parm('biome_temp').set(18.0);biome.parm('biome_temp_h').set(0.0);biome.parm('biome_lapse').set(220.0);biome.parm('pv_biome').set(1)
rows=[dict(name='Forest',density=60.0,mix='1',h=(0.4,7.0),he=1.2,s=(0.0,32.0),se=8.0,m=(0.28,1.0),me=0.12,t=(7.0,40.0),te=3.0,scale=(0.8,1.3)),
      dict(name='Alpine (stunted firs)',density=45.0,mix='1',h=(-100.0,100.0),he=0.0,s=(0.0,50.0),se=8.0,m=(0.0,1.0),me=0.0,t=(-50.0,7.0),te=3.0,scale=(0.35,0.7)),
      dict(name='Cliffs (rocks)',density=40.0,mix='2',h=(-100.0,100.0),he=0.0,s=(28.0,90.0),se=8.0,m=(0.0,1.0),me=0.0,t=(-100.0,100.0),te=0.0,scale=(0.6,1.5)),
      dict(name='Shore (stones)',density=130.0,mix='3',h=(-100.0,100.0),he=0.0,s=(0.0,40.0),se=6.0,m=(0.72,1.0),me=0.15,t=(-100.0,100.0),te=0.0,scale=(0.6,1.4),he_=0.0,te_=0.0)]     # the shore stones ignore the elevation and the temperature
biome.parm('biomes').set(len(rows))
for i,r in enumerate(rows,1):
    biome.parm('biome_name%d'%i).set(r['name']);biome.parm('biome_density%d'%i).set(r['density']);biome.parm('biome_mix%d'%i).set(r['mix'])
    biome.parmTuple('biome_hrange%d'%i).set(r['h']);biome.parm('biome_hedge%d'%i).set(r['he']);biome.parmTuple('biome_srange%d'%i).set(r['s']);biome.parm('biome_sedge%d'%i).set(r['se'])
    biome.parmTuple('biome_mrange%d'%i).set(r['m']);biome.parm('biome_medge%d'%i).set(r['me']);biome.parmTuple('biome_trange%d'%i).set(r['t']);biome.parm('biome_tedge%d'%i).set(r['te']);biome.parmTuple('biome_scale%d'%i).set(r['scale'])
    for key,parm in (('he_','biome_heffect'),('se_','biome_seffect'),('me_','biome_meffect'),('te_','biome_teffect')):
        if key in r:biome.parm('%s%d'%(parm,i)).set(r[key])
biome.setComment('BIOME - four biomes on one terrain (Layout tab, Distribution Mode Biome): Forest (mid elevation, gentle slope, near water, not too cold), stunted Alpine firs (cold = high), Cliff rocks (steep slopes) and Shore stones (wet, around the pond). Every condition is a range with a soft edge, so the biomes blend at their borders. Moisture = distance to the pond, temperature falls with height. Debugging tab: Debug Views, Colour Final Points By Biome.')
biome.setGenericFlag(hou.nodeFlag.DisplayComment,True)
camera=stage.createNode('camera','render_camera');camera.setInput(0,biome)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(28);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(400);camera.parmTuple('t').set((-5.0,19.0,27.0));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.8,0.0))
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.6);sun.parmTuple('r').set((-40,35,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"biome")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
biome.setDisplayFlag(True)
errors={n.name():n.errors() for n in (fir,rock,stone,terrain,pond,biome,camera,dome,sun,settings)}
rs=settings.stage();assert rs and not any(n.errors() for n in (biome,settings)),errors
pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/Biomes'));ids=np.array(pi.GetIdsAttr().Get(1));counts=np.bincount(ids//1000000,minlength=4)
assert (counts[:4]>20).all(),counts
print(biome.parm('biome_info').eval());print(counts.tolist())
rs.Export(str(versions.render_usd(VID,'biome')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'instances':counts.tolist()}))
