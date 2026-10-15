"""Physics Settle accuracy / performance table for docs/PHYSICS_SETTLE.md: hython tests/bench_physics.py
Reuses the measuring helpers of validate_physics.py (USD read-back, SAT penetration, contact graph) on growing piles and on the three
Collision Quality presets. Writes tests/bench_physics_v0.4.0.json and prints a markdown table."""
import sys, json
__file__=str(__import__('pathlib').Path(__file__).resolve().parent/'validate_physics.py')
src=open(__file__).read()
exec(src[:src.index('# ------------------------------------------------------------------ run')])
rows=[]
def write_pebble():
    """A rounded 6 x 4 x 5 cm stone: the hull of 90 random points on an ellipsoid (about 60 hull vertices), origin at the bottom."""
    rng=np.random.RandomState(8);d=rng.normal(size=(90,3));d/=np.linalg.norm(d,axis=1)[:,None]
    v,f=P.quickhull(d*np.array([0.030,0.018,0.024]));v=v-np.array([0.0,v[:,1].min(),0.0])
    path=WORK/'pebble.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/Pebble');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    m=UsdGeom.Mesh.Define(s,'/Pebble/Shape');m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float,q)) for q in v]));m.CreateFaceVertexCountsAttr(Vt.IntArray([3]*len(f)));m.CreateFaceVertexIndicesAttr(Vt.IntArray([int(i) for i in f.ravel()]))
    s.GetRootLayer().Save();return path.as_posix(),len(v)
PEBBLE,PEBBLE_VERTS=write_pebble()
def run(label,count,quality=1,side=None,duration=20.0,pebble=False):
    side=side or 0.3*math.sqrt(count/160.0)
    if pebble:
        st=new_scene('bench');r=ref(st,'pebble','/World/Props/Pebble',PEBBLE);a=arraytron(st,r,prim='/World/Props/Pebble',phys_on=1,area_count=count,area_sizex=side,area_sizez=side,phys_quality=quality,phys_duration=duration)
    else:
        st,r,a=stone_scene('bench',phys_on=1,area_count=count,area_sizex=side,area_sizez=side,phys_quality=quality,phys_duration=duration)
    res=bake(a);hulls,d=world_hulls(a);worst,low,pairs=measure(hulls);dmin=res['plan']['dmin']
    fl=floating(low,pairs,0.12*dmin+res['plan']['margin'])
    rows.append(dict(label=label,hull_vertices=len(a.hdaModule().proto_proxies(a)[0]['verts']),mesh_vertices=(PEBBLE_VERTS if pebble else 17),stones=count,quality=('Draft','Standard','High')[quality],seconds=round(res['wall'],1),frames=res['frames'],substeps=res['plan']['substeps'],
                     at_rest=bool(res['settled']),still_moving=res['active'],pair_penetration_mm=round(-worst*1000,3),pair_penetration_pct_of_thinnest=round(-worst/dmin*100,2),
                     ground_penetration_mm=round(-min(0,low.min())*1000,3),floating=len(fl),on_top_of_others=int((low>0.5*dmin).sum()),thinnest_mm=round(dmin*1000,1)))
    print(rows[-1]);sys.stdout.flush()
ONLY=__import__('os').environ.get('BENCH_ONLY')=='pebble'
for n in (50,100,200,400,800):
    if not ONLY:run('scaling',n)
for q in (0,1,2):
    if not ONLY:run('quality',200,quality=q)
for q in (0,1,2):run('rounded stone, %d mesh vertices'%PEBBLE_VERTS,200,quality=q,pebble=True)
(ROOT/'tests'/('bench_physics_%s.json'%VID)).write_text(json.dumps(rows,indent=1))
print('| stone | stones | quality | proxy vertices | seconds | frames | at rest | still moving | pair penetration | ground penetration | floating | on top of others |');print('|---|---|---|---|---|---|---|---|---|---|---|---|')
for r in rows:print('| %(mesh_vertices)d-vertex mesh | %(stones)d | %(quality)s | %(hull_vertices)d | %(seconds).1f | %(frames)d | %(at_rest)s | %(still_moving)d | %(pair_penetration_mm).2f mm (%(pair_penetration_pct_of_thinnest).1f%%) | %(ground_penetration_mm).2f mm | %(floating)d | %(on_top_of_others)d |'%r)
shutil.rmtree(WORK,ignore_errors=True)
