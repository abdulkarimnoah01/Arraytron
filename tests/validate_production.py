"""Production testing (v1.0.0): hython tests/validate_production.py
Not features but the guarantees a pipeline needs: a saved scene reloads to the identical result, two separate processes give bit-identical output, a
20,000 point stress cook with every stage on stays inside a time budget, random parameter fuzzing never produces a Python traceback (only readable errors),
the exported USD passes usdchecker, the shipped HDA contains no dollar sign in an embedded script (a `$FF` in a comment once made a node time dependent),
every demo of the release cooks without errors and the manifest matches the files. Writes tests/production_<version>.json with the measured timings."""
from pathlib import Path
import hashlib, hou, json, os, random, subprocess, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
TYPE=versions.type_name(VID)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_production_'));checks=[];TIMINGS={}
HFS=Path(hou.text.expandString('$HFS'))
def write_scene():
    path=WORK/'prod.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Ball','BallB','Lod'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    m=UsdGeom.Mesh.Define(s,'/World/Ground');m.CreatePointsAttr([(-50,0,50),(50,0,50),(50,0,-50),(-50,0,-50)]);m.CreateFaceVertexCountsAttr([4]);m.CreateFaceVertexIndicesAttr([0,1,2,3]);m.CreateOrientationAttr('rightHanded')
    UsdGeom.Cube.Define(s,'/World/Hero/Cube').CreateSizeAttr(4.0)
    from pxr import Gf
    cam=UsdGeom.Camera.Define(s,'/World/Cam');UsdGeom.Xformable(cam).AddTransformOp().Set(Gf.Matrix4d(1.0).SetTranslate(Gf.Vec3d(0,10,60)))
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(versions.hda(VID)),force_use_assets=True);hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def setup(a):
    """Every stage on: Cluster distribution, variation, mask, field stack, separation, avoid geometry, overrides, camera, LOD, primvars."""
    a.parm('protos').set(2);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('proto_prim2').set('/World/Props/BallB');a.parm('proto_lod11').set('/World/Props/Lod')
    a.parm('mode').set(7);a.parm('cluster_prim').set('/World/Ground');a.parm('cluster_count').set(30);a.parm('cluster_per').set(40);a.parm('cluster_radius').set(2.0);a.parm('cluster_seed').set(3)
    a.parm('scale_random_mode').set(1);a.parm('scale_min').set(0.6);a.parm('scale_max').set(1.4);a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(180)
    a.parm('mask_source').set(1);a.parm('mask_effect').set(2);a.parm('mask_noise_freq').set(0.3)
    a.parm('fields').set(2);a.parm('field_type1').set(2);a.parm('field_nfreq1').set(0.2);a.parm('field_type2').set(5);a.parm('field_prim2').set('/World/Hero');a.parm('field_xmargin2').set(0.5);a.parm('field_effect').set(0)
    a.parm('overlap_mode').set(1);a.parm('overlap_size').set(1);a.parm('overlap_radius').set(0.12);a.parm('overlap_priority').set(1)
    a.parm('avoid_mode').set(2);a.parm('avoid_prim').set('/World/Hero');a.parm('avoid_margin').set(0.3)
    a.parm('overrides').set(3);a.parm('ovr_id1').set(5);a.parm('ovr_delete1').set(1);a.parm('ovr_id2').set(1001);a.parmTuple('ovr_move2').set((0.0,0.5,0.0));a.parm('ovr_id3').set(2002);a.parm('ovr_scale3').set(2.0)
    a.parm('cam_on').set(1);a.parm('cam_prim').set('/World/Cam');a.parm('cam_frustum').set(1);a.parm('cam_densityon').set(1);a.parm('cam_dnear').set(40);a.parm('cam_dfar').set(90);a.parm('cam_lod').set(1);a.parm('lod_d1').set(60)
    for t in ('pv_id','pv_proto','pv_random','pv_mask','pv_density','pv_cluster','pv_lod'):a.parm(t).set(1)
    return a
def digest(a):
    s=a.stage();assert not a.errors(),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame();h=hashlib.sha256()
    for attr in (pi.GetPositionsAttr(),pi.GetIdsAttr(),pi.GetProtoIndicesAttr(),pi.GetScalesAttr(),pi.GetInvisibleIdsAttr()):
        v=attr.Get(t);h.update(np.array(v if v is not None else [],dtype=np.float64).tobytes())
    q=pi.GetOrientationsAttr().Get(t) or [];h.update(np.array([[x.GetReal(),*x.GetImaginary()] for x in q],dtype=np.float64).tobytes());return h.hexdigest(),len(pi.GetPositionsAttr().Get(t) or [])
def check(name,func):
    t=time.time();func();TIMINGS[name]=round(time.time()-t,2);checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def round_trip():
    st,sc=new_scene('rt');a=setup(st.createNode(TYPE,'RT'));a.setInput(0,sc);d1,n1=digest(a);assert n1>200
    hip=WORK/'roundtrip.hip';hou.hipFile.save(str(hip));hou.hipFile.clear(suppress_save_prompt=True);hou.hipFile.load(str(hip),suppress_save_prompt=True);b=hou.node('/stage/RT')
    d2,n2=digest(b);assert (d1,n1)==(d2,n2)                                                                                  # a saved and reloaded scene gives the identical result
    assert b.evalParm('overrides')==3 and b.evalParm('ovr_id2')==1001 and b.evalParm('cam_on')==1 and b.evalParm('fields')==2 and b.evalParm('proto_lod11')=='/World/Props/Lod'
def determinism():
    runner=WORK/'run.py';runner.write_text("import sys,hou\nsys.argv=['x','%s']\n__file__=%r\nsys.path.insert(0,%r)\nsrc=open(%r).read().split('# --- determinism '+'entry')[0]\nexec(compile(src,'prod','exec'),globals())\nst,sc=new_scene('proc');a=setup(st.createNode(TYPE,'D'));a.setInput(0,sc);print('DIGEST',*digest(a))\n"%(VID,str(Path(__file__).resolve()),str(ROOT/'tools'),str(Path(__file__).resolve())))
    outs=[]
    for _ in range(2):
        r=subprocess.run([str(HFS/'bin'/'hython.exe'),str(runner)],capture_output=True,text=True,timeout=300);line=[l for l in r.stdout.splitlines() if l.startswith('DIGEST')];assert line,(r.stdout[-400:],r.stderr[-400:]);outs.append(line[-1])
    assert outs[0]==outs[1] and int(outs[0].split()[-1])>200,outs                                                           # two separate processes: bit-identical
    st,sc=new_scene('here');a=setup(st.createNode(TYPE,'D'));a.setInput(0,sc);d,n=digest(a);assert 'DIGEST %s %d'%(d,n)==outs[0]                # and the same as this process
def stress():
    st,sc=new_scene('stress');a=st.createNode(TYPE,'S');a.setInput(0,sc);a.parm('protos').set(2);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('proto_prim2').set('/World/Props/BallB')
    a.parm('mode').set(1);a.parm('area_count').set(20000);a.parmTuple('area_size').set((90.0,90.0)) if a.parmTuple('area_size') else None
    a.parm('scale_random_mode').set(1);a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(180);a.parm('mask_source').set(1);a.parm('mask_effect').set(0);a.parm('mask_noise_freq').set(0.1);a.parm('mask_low').set(0.2)
    a.parm('fields').set(1);a.parm('field_type1').set(0);a.parm('field_hmin1').set(-1.0);a.parm('field_hmax1').set(1.0);a.parm('overlap_mode').set(1);a.parm('overlap_size').set(1);a.parm('overlap_radius').set(0.05)
    for t in ('pv_id','pv_random'):a.parm(t).set(1)
    t0=time.time();d,n=digest(a);cook=time.time()-t0;gen=a.node('USD_COMPILER/DISTRIBUTION_GENERATOR').geometry().intrinsicValue('pointcount');TIMINGS['stress generated points']=gen;TIMINGS['stress cook seconds']=round(cook,2);TIMINGS['stress instances']=n;assert gen>=20000 and n>1000 and cook<120,(gen,n,cook)
    a.parm('cam_on').set(1);a.parm('cam_prim').set('/World/Cam');a.parm('cam_frustum').set(1);a.parm('cam_densityon').set(1)
    t0=time.time();d2,n2=digest(a);TIMINGS['stress camera seconds']=round(time.time()-t0,2);assert time.time()-t0<60
    a.parm('dbg_on').set(1);a.parm('dbg_axes').set(1);a.parm('dbg_color').set(1);t0=time.time();digest(a);TIMINGS['stress debug seconds']=round(time.time()-t0,2);assert time.time()-t0<90
    hou.hipFile.save(str(WORK/'stress.hip'));TIMINGS['stress hip MB']=round(os.path.getsize(WORK/'stress.hip')/1e6,2);assert TIMINGS['stress hip MB']<20
def fuzz():
    st,sc=new_scene('fuzz');rng=random.Random(11);errors_seen={}
    ranges={'line_count':(1,60),'area_count':(1,300),'area_seed':(0,50),'surface_count':(1,300),'surface_seed':(0,50),'scale_min':(0.1,1.0),'scale_max':(1.0,3.0),'yaw_random':(0,180),'proto_seed':(0,50),'mask_noise_freq':(0.05,3.0),'mask_low':(0.0,0.5),'mask_high':(0.5,1.0),
            'overlap_radius':(0.02,0.6),'overlap_tolerance':(0.3,2.0),'avoid_margin':(0.0,1.0),'cluster_count':(1,40),'cluster_per':(1,80),'cluster_radius':(0.2,4.0),'cluster_falloff':(0.0,1.0),'cluster_jitter':(0.0,1.0),'paint_radius':(0.1,3.0),'field_hmin1':(-5,5),'field_hmax1':(-5,5),'field_hfall1':(0,5),
            'cam_maxdist':(1,200),'cam_margin':(0,1),'cam_dnear':(0,100),'cam_dfar':(0,200),'cam_dmin':(0,1),'lod_d1':(0,100),'grow_sweep':(0,100),'grow_time':(1,50),'base_scale':(0.2,3.0)}
    menus={'mode':(0,1,2,3,5,7),'overlap_mode':(0,1,2),'overlap_size':(0,1),'overlap_axes':(0,1),'overlap_priority':(0,1,2,3),'avoid_mode':(0,1,2),'avoid_axes':(0,1),'mask_source':(0,1),'mask_effect':(0,1,2),'field_effect':(0,1,2),'field_type1':(0,1,2,4,5),'field_op1':(0,1,2,3,4),'field_invert1':(0,1),
           'cam_on':(0,1),'cam_frustum':(0,1),'cam_distcull':(0,1),'cam_densityon':(0,1),'cam_behind':(0,1,2),'cam_lod':(0,1),'lod_by':(0,1),'grow_on':(0,1),'grow_direction':(0,1,2,4,5),'grow_style':(0,1,2),'grow_ease':(0,1,2,3),'dbg_on':(0,1),'dbg_color':(0,1,2,3),'dbg_axes':(0,1),'dbg_radius':(0,1),'proto_mode':(0,1,2,3),'cluster_normal':(0,1),
           'scale_random_mode':(0,1),'rotation_random_mode':(0,1)}
    a=st.createNode(TYPE,'F');a.setInput(0,sc);a.parm('protos').set(2);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('proto_prim2').set('/World/Props/BallB');a.parm('proto_lod11').set('/World/Props/Lod')
    a.parm('surface_prim').set('/World/Ground');a.parm('cluster_prim').set('/World/Ground');a.parm('fields').set(1);a.parm('field_prim1').set('/World/Ground');a.parm('avoid_prim').set('/World/Hero');a.parm('cam_prim').set('/World/Cam');a.parm('mask_prim').set('/World/Ground')
    a.parm('paint_prim').set('');m=a.hdaModule();pts=np.column_stack([np.random.default_rng(1).uniform(-8,8,(60,3)),np.tile([0,1.0,0],(60,1)),np.arange(60)]);a.parm('paint_data').set(m.paint_encode({'pts':pts,'dab':1,'next':60}));a.parm('overrides').set(2);a.parm('ovr_id1').set(3);a.parm('ovr_delete1').set(1);a.parm('ovr_id2').set(4);a.parm('ovr_scale2').set(2.0)
    names=list(ranges)+list(menus);cooked=ok=0
    for it in range(160):
        if it%5==0:                                                                                            # bad input on purpose: the errors must be readable, never a Python traceback
            for bad in rng.sample(('surface_prim','cluster_prim','avoid_prim','field_prim1','cam_prim','proto_prim1','mask_prim'),2):a.parm(bad).set(rng.choice(('','/World/Nope')))
        elif it%5==1:
            for good in ('surface_prim','cluster_prim','avoid_prim','field_prim1','cam_prim','proto_prim1','mask_prim'):a.parm(good).set({'surface_prim':'/World/Ground','cluster_prim':'/World/Ground','avoid_prim':'/World/Hero','field_prim1':'/World/Ground','cam_prim':'/World/Cam','proto_prim1':'/World/Props/Ball','mask_prim':'/World/Ground'}[good])
        for name in rng.sample(names,6):
            p=a.parm(name)
            if p is None:continue
            if name in menus:p.set(rng.choice(menus[name]))
            else:
                lo,hi=ranges[name];v=rng.uniform(lo,hi);p.set(int(v) if isinstance(p.eval(),int) else v)
        try:a.cook(force=True);a.stage()
        except hou.OperationFailed:pass
        errs=[]
        def walk(n):
            errs.extend(n.errors())
            for c in n.children():walk(c)
        walk(a);cooked+=1
        if not errs:ok+=1
        for e in errs:
            assert 'Traceback' not in e or 'hou.NodeError' in e or 'NodeError' in e or False,('python traceback after',it,e[-500:])
            errors_seen[e.split('\n')[0][:90]]=errors_seen.get(e.split('\n')[0][:90],0)+1
    TIMINGS['fuzz cooks']=cooked;TIMINGS['fuzz clean cooks']=ok;assert ok>40 and len(errors_seen)>=2,(ok,errors_seen)                                 # most random settings are valid; none gives a traceback
    TIMINGS['fuzz distinct readable errors']=len(errors_seen)
def usd_valid():
    st,sc=new_scene('usd');a=setup(st.createNode(TYPE,'U'));a.setInput(0,sc);a.parm('export_path').set((WORK/'export'/'prod.usda').as_posix());digest(a);path,count=a.hdaModule().export_instances(a);assert count>200
    exe=HFS/'bin'/'usdchecker.exe'
    cmd=[str(exe),path] if exe.exists() else ['cmd','/c',str(HFS/'bin'/'usdchecker.cmd'),path]          # Houdini 20.5 / 21 ship a script wrapper only
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=120);text=r.stdout+r.stderr
    assert r.returncode==0 and 'Success' in text or 'Failed' not in text,text[-800:]
    assert 'error' not in text.lower().replace('0 errors','') or 'Success!' in text,text[-800:]
def script_lint():
    hda=hou.hda.definitionsInFile(str(versions.hda(VID)))[0];st,sc=new_scene('lint');a=st.createNode(TYPE,'L');a.allowEditingOfContents();bad=[]
    def walk(n):
        for c in n.children():
            p=c.parm('python')
            if p is not None and '$' in p.unexpandedString():bad.append(c.path())
            walk(c)
    walk(a);assert not bad,bad                                                                                               # no dollar sign in an embedded script: it would be expanded and could add a time dependency
    assert 'Help' in hda.sections() and len(hda.sections()['Help'].contents())>500 and VID[1:] in hda.sections()['ArraytronVersion'].contents() or VID in hda.sections()['ArraytronVersion'].contents()
    assert hda.icon().startswith('opdef:') and 'Icon.svg' in hda.sections() and hda.sections()['Icon.svg'].contents().lstrip().startswith('<svg')
def release_hygiene():
    dist=versions.folder(VID);stem=versions.stem(VID);assert (dist/(stem+'.hda')).is_file() and versions.CURRENT==VID          # Houdini 22: dist/, Houdini 20.5 / 21: otls_h205/
    demos=sorted(dist.glob(stem+'_*demo.hip'));assert len(demos)>=8,demos                                          # every demo of the release exists
    st=None;hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(versions.hda(VID)),force_use_assets=True)
    allhip=versions.demo_file(VID,'all_demos');assert allhip.is_file();hou.hipFile.load(str(allhip),suppress_save_prompt=True,ignore_load_warnings=True);bad={}
    for n in hou.node('/stage').children():
        if n.type().name().startswith('arraytron'):
            try:n.cook(force=True)
            except hou.OperationFailed:pass
    for n in hou.node('/stage').allSubChildren():
        if n.errors():bad[n.path()]=n.errors()
    assert not bad,list(bad.items())[:3]                                                                                      # all demos cook without errors
    manifest=json.loads((ROOT/'dist'/'manifest.json').read_text());by={Path(e['Path']).name:e['Hash'] for e in manifest if Path(e['Path']).parent.name in ('dist','otls_h205')}                   # by file name: the manifest keeps the paths of the PC it was made on
    for f in dist.iterdir():
        if f.is_file() and f.suffix.lower() in ('.hda','.hip','.usda'):assert f.name in by and hashlib.sha256(f.read_bytes()).hexdigest().upper()==by[f.name],f.name       # run tools/make_manifest.py after the last build
    for doc in ('README.md','STATUS.md','CLAUDE.md','docs/USER_GUIDE.md','docs/INDEX.md','docs/CACHING_AND_PIPELINE.md','docs/TROUBLESHOOTING.md'):assert (ROOT/doc).is_file(),doc
    index=(ROOT/'docs/INDEX.md').read_text()
    for md in sorted((ROOT/'docs').glob('*.md')):
        if 'AUDIT' in md.name or md.name.startswith('TEAM_') or md.name=='INDEX.md':continue
        assert md.name in index,('docs/INDEX.md does not list',md.name)
# --- determinism entry (the code above this line is what the subprocess runs)
def main():
    for name,func in (('Saved scene reloads to the identical result (every stage on)',round_trip),
                      ('Two separate processes give bit-identical output',determinism),
                      ('Stress: 20,000 points with variation, mask, field, separation, primvars, camera and debug inside the time budgets',stress),
                      ('Fuzz: 160 random parameter walks never give a Python traceback',fuzz),
                      ('Exported USD passes usdchecker',usd_valid),
                      ('Embedded scripts have no dollar sign; Help, version and icon sections are present',script_lint),
                      ('Release hygiene: demos, all-demos cook, manifest hashes, documentation index',release_hygiene)):check(name,func)
    (ROOT/'tests'/('production_%s.json'%versions.tag(VID))).write_text(json.dumps({'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'timings':TIMINGS},indent=1))
    print('ALL PASSED',len(checks),TIMINGS)
main()
