"""Build a Physics Settle demo with the CURRENT release: hython tools/build_demo_physics.py <railway|box> [stones]
railway: a loose bed of ballast stones poured onto a ground plane between and on top of concrete sleepers and two rails (collider prims).
box:     stones poured into an open wooden box (floor and four walls as collider prims) until they pile up inside it.
Both use ONE stone prototype. The simulation runs once here (Simulate & Cache), the result is cached in $HIP/arraytron_cache and the
render USD is exported. Writes dist/Arraytron_<version>_physics_<kind>_demo.hip, then render it with tools/render_demo.py <version> physics_<kind>."""
from pathlib import Path
import sys, hou, json, time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
KIND=sys.argv[1] if len(sys.argv)>1 else 'railway';assert KIND in ('railway','box'),KIND
VID=versions.BUILD;TYPE=versions.type_name(VID);NAME='physics_'+KIND
COUNT=int(sys.argv[2]) if len(sys.argv)>2 else (1100 if KIND=='railway' else 1500)
HIP=versions.demo(VID,NAME);ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
stone=reference('reference_stone','/World/Props/Stone',ASSETS+'/stone.usda')
if KIND=='railway':
    ground=reference('reference_ground','/World/Ground',ASSETS+'/ballast_ground.usda',stone);scene=reference('reference_track','/World/Track',ASSETS+'/track.usda',ground);collider='/World/Track'
else:
    ground=reference('reference_ground','/World/Ground',ASSETS+'/ballast_ground.usda',stone);scene=reference('reference_box','/World/Box',ASSETS+'/box.usda',ground);collider='/World/Box'
pile=stage.createNode(TYPE,'Arraytron_StonePile' if KIND=='railway' else 'Arraytron_BoxFill');pile.setInput(0,scene)
pile.parm('outputpath').set('/World/Ballast' if KIND=='railway' else '/World/Fill');OUT=pile.evalParm('outputpath')
pile.parm('protos').set(1);pile.parm('proto_prim1').set('/World/Props/Stone')
pile.parm('mode').set(1)
if KIND=='railway':
    pile.parm('area_sizex').set(0.9);pile.parm('area_sizez').set(1.4);pile.parm('area_seed').set(11);pile.parm('phys_drop').set(0.3);pile.parm('phys_seed').set(3);pile.parm('phys_duration').set(14)
else:
    pile.parm('area_sizex').set(0.42);pile.parm('area_sizez').set(0.42);pile.parm('area_seed').set(6);pile.parm('phys_drop').set(0.55);pile.parm('phys_seed').set(2);pile.parm('phys_duration').set(16)
pile.parm('area_count').set(COUNT)
pile.parmTuple('rotation_random').set((180,180,180))
pile.parm('scale_random_mode').set(1);pile.parm('scale_min').set(0.75);pile.parm('scale_max').set(1.3);pile.parm('random_seed').set(5)
pile.parm('phys_on').set(1);pile.parm('phys_friction').set(0.9);pile.parm('phys_bounce').set(0.1);pile.parm('phys_quality').set(1);pile.parm('phys_colliders').set(collider)
pile.setComment(('STONE PILE - Physics Settle on a railway bed: one stone prototype, ground plane at y = 0, sleepers and rails (/World/Track) as colliders.' if KIND=='railway' else 'STONES IN A BOX - Physics Settle: one stone prototype poured from above into an open wooden box (/World/Box: floor and four walls as colliders).')+' The settled result is cached in $HIP/arraytron_cache. Change anything in Physics Settle, then press Simulate & Cache.')
pile.setGenericFlag(hou.nodeFlag.DisplayComment,True)
def state():return pile.stage().GetPrimAtPath(OUT).GetCustomDataByKey('arraytron:physics')
if state()['state']=='settled':
    print('cache already present for these settings: not simulating again');result=dict(frames=state()['frames'],seconds=0.0,settled=state()['atRest'])
else:
    t=time.time();result=pile.hdaModule().bake(pile);print('baked',{k:v for k,v in result.items() if k not in ('stats','plan')},'in %.1fs'%(time.time()-t))
assert result['settled'] and state()['state']=='settled',result
camera=stage.createNode('camera','render_camera');camera.setInput(0,pile)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(38 if KIND=='railway' else 40);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(100)
if KIND=='railway':camera.parmTuple('t').set((0.62,0.62,1.05));camera.parmTuple('lookatposition').set((0,0.03,0.05))
else:camera.parmTuple('t').set((0.3,1.25,0.5));camera.parmTuple('lookatposition').set((0,0.1,0))
camera.parm('lookatenable').set(1)
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.2);sun.parmTuple('r').set((-48,-35,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(256)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,NAME)}.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(1600,900))
scene.setDisplayFlag(False);pile.setDisplayFlag(True)
renderstage=settings.stage();errors={n.name():n.errors() for n in (stone,ground,scene,pile,camera,dome,sun,settings)};assert renderstage and not any(errors.values()),errors
assert state()['state']=='settled'
renderstage.Export(str(versions.render_usd(VID,NAME)))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'kind':KIND,'stones':COUNT,'frames':result['frames'],'seconds':round(result['seconds'],1)}))
