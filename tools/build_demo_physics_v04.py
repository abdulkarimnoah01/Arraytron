"""Build the Physics Settle demo (v0.4.0): hython tools/build_demo_physics_v04.py [stones]
A loose pile of angular gravel (ONE stone prototype) dropped onto a ground plane between and on top of concrete sleepers and two rails (collider prims),
settled with Houdini Bullet inside the HDA, cached next to the HIP, and set up for Karma XPU.
Writes dist/Arraytron_v0.4.0_physics_demo.hip, its arraytron_cache/ folder and the exported render USD."""
from pathlib import Path
import sys, hou, json, time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID='v0.4.0';COUNT=int(sys.argv[1]) if len(sys.argv)>1 else 700
assert versions.resolve(VID)==versions.CURRENT
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'physics');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
hou.hipFile.clear(suppress_save_prompt=True)
versions.ensure_installed(VID)
hou.hipFile.save(str(HIP))     # resolves $HIP for the reference and cache paths
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path)
    n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
stone=reference('reference_stone','/World/Props/Stone',ASSETS+'/stone.usda')
ground=reference('reference_ground','/World/Ground',ASSETS+'/ballast_ground.usda',stone)
track=reference('reference_track','/World/Track',ASSETS+'/track.usda',ground)

pile=stage.createNode(TYPE,'Arraytron_StonePile');pile.setInput(0,track)
pile.parm('outputpath').set('/World/Ballast')
pile.parm('protos').set(1);pile.parm('proto_prim1').set('/World/Props/Stone')
pile.parm('mode').set(1);pile.parm('area_sizex').set(0.9);pile.parm('area_sizez').set(1.4);pile.parm('area_count').set(COUNT);pile.parm('area_seed').set(11)
pile.parmTuple('rotation_random').set((180,180,180))                               # tumbling gravel: every orientation
pile.parm('scale_random_mode').set(1);pile.parm('scale_min').set(0.75);pile.parm('scale_max').set(1.3)
pile.parm('random_seed').set(5)
pile.parm('phys_on').set(1)
pile.parm('phys_drop').set(0.3);pile.parm('phys_seed').set(3)
pile.parm('phys_friction').set(0.8);pile.parm('phys_bounce').set(0.1);pile.parm('phys_duration').set(14)
pile.parm('phys_quality').set(1)
pile.parm('phys_colliders').set('/World/Track')                                    # sleepers and rails: the stones land on and against them
pile.setComment('STONE PILE - Physics Settle. One stone prototype; ground plane at y = 0; /World/Track (sleepers and rails) as colliders. The settled result is cached in $HIP/arraytron_cache. Change anything in Physics Settle, then press Simulate & Cache.')
pile.setGenericFlag(hou.nodeFlag.DisplayComment,True)

def state():
    return pile.stage().GetPrimAtPath('/World/Ballast').GetCustomDataByKey('arraytron:physics')
if state()['state']=='settled':
    print('cache already present for these settings: not simulating again');result=dict(frames=state()['frames'],seconds=0.0,path='(cached)',settled=state()['atRest'])
else:
    t=time.time();result=pile.hdaModule().bake(pile)
    print('baked',{k:v for k,v in result.items() if k not in ('stats','plan')},'in %.1fs'%(time.time()-t))
    print('stones above the rest tolerance per half second window:',[(st[0],st[4]) for st in result['stats'][::3]])
assert result['settled'] and state()['state']=='settled',result

camera=stage.createNode('camera','render_camera');camera.setInput(0,pile)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective')
camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(38);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(100)      # the Houdini default near plane is 1 unit, which would slice a 1 m scene
camera.parmTuple('t').set((0.62,0.62,1.05));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0,0.03,0.05))
def intensity(light,value):
    light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,camera);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.2)
sun.parmTuple('r').set((-48,-35,0))
settings=stage.createNode('karmarendersettings','karma_xpu');settings.setInput(0,sun)
settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(256)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"physics")}.exr')
settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();settings.parmTuple('resolution').set((1600,900))
track.setDisplayFlag(False);pile.setDisplayFlag(True)
renderstage=settings.stage()
errors={n.name():n.errors() for n in (stone,ground,track,pile,camera,dome,sun,settings)}
assert renderstage and not any(errors.values()),errors
assert state()['state']=='settled'
renderstage.Export(str(versions.render_usd(VID,'physics')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu')
render.parm('rendercommand').set('husk --engine xpu')
render.setComment('Render the settled pile with Karma XPU.');render.setGenericFlag(hou.nodeFlag.DisplayComment,True)
stage.layoutChildren()
hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'stones':COUNT,'frames':result['frames'],'seconds':round(result['seconds'],1),'cache':result['path']},indent=2))
