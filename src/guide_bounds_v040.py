# Embedded in a Python LOP. Authors a guide-purpose preview of the Line/Area/Grid/Circle bounds
# in the distribution's local space, so the Bounds Transform moves it with the instances.
# With Scale Instances off the USD transform carries no scale, so the Bounds curves are scaled about the Pivot here.
# Guides never render in Karma; point generation itself stays in VEX.
import hou
from pxr import Gf, Sdf, UsdGeom, Vt
node=hou.pwd()
asset=node.parent()
stage=node.editableStage()
root=Sdf.Path(asset.evalParm('outputpath'))
group=root.AppendChild('Bounds_Guide')
V=Gf.Vec3d
# Physics Settle state, readable from the stage by pipeline tools: state is settled | missing | invalid | empty.
instancer=stage.GetPrimAtPath(root)
if instancer and instancer.IsValid():
    if asset.evalParm('phys_on'):
        g=asset.node('USD_COMPILER/PHYSICS_APPLY').geometry()
        instancer.SetCustomDataByKey('arraytron:physics',{'state':g.attribValue('phys_state'),'key':g.attribValue('phys_key'),'frames':int(g.attribValue('phys_frames')),'atRest':bool(g.attribValue('phys_settled')),'stones':int(g.attribValue('phys_count'))})
    else:
        instancer.ClearCustomDataByKey('arraytron:physics')
if not asset.evalParm('show_bounds'):
    existing=stage.GetPrimAtPath(group)
    if existing:
        existing.SetActive(False)
else:
    mode=asset.evalParm('mode')
    segments=[]
    if mode==0:
        axis=asset.evalParm('line_axis')
        length=max(0.0,asset.evalParm('line_length'))
        bysp=asset.evalParm('line_spacemode')==1
        if bysp:
            step=max(0.001,asset.evalParm('line_spacing'))
            count=min(10000,max(1,int(length/step+1e-6)+1))
        else:
            count=min(10000,max(1,asset.evalParm('line_count')))
            step=length/(count-1) if count>1 else 0.0
        if axis<3:
            direction=V(0,0,0);direction[axis]=1
        else:
            direction=V(*asset.evalParmTuple('line_direction'))
            direction=direction.GetNormalized() if direction.GetLength()>1e-6 else V(1,0,0)
        reference=V(0,1,0) if abs(direction[1])<.99 else V(0,0,1)
        side=Gf.Cross(direction,reference).GetNormalized()
        size=max(length*.05,.15)
        centered=asset.evalParm('line_center')
        first=-0.5*(count-1)*step if centered else 0.0
        if count>1:
            start=direction*first
            end=start+direction*((count-1)*step)
            span=(count-1)*step
            segments.append([start,end])
            head=min(size*2,span*.25)
            segments.append([end-direction*head+side*head*.5,end,end-direction*head-side*head*.5])
            ticks=min(size*.5,step*.5) if step>0 else size*.5
            if bysp and length>0:
                # Length limits (the points stop at the last whole step inside them).
                lo=-length*.5 if centered else 0.0
                for t in (lo,lo+length):
                    p=direction*t
                    segments.append([p-side*ticks*1.6,p+side*ticks*1.6])
            if count<=256:
                for i in range(count):
                    p=start+direction*(i*step)
                    segments.append([p-side*ticks,p+side*ticks])
            else:
                for p in (start,end):
                    segments.append([p-side*ticks,p+side*ticks])
        else:
            segments.append([V(-size*.5,0,0),V(size*.5,0,0)])
            segments.append([V(0,0,-size*.5),V(0,0,size*.5)])
        color=Gf.Vec3f(1,.72,.1)
    elif mode==1:
        hx=max(0.0,asset.evalParm('area_sizex'))*.5
        hz=max(0.0,asset.evalParm('area_sizez'))*.5
        segments.append([V(-hx,0,-hz),V(hx,0,-hz),V(hx,0,hz),V(-hx,0,hz),V(-hx,0,-hz)])
        size=max(min(hx,hz)*.1,.15)
        color=Gf.Vec3f(.2,.85,1)
    elif mode==2:
        size3=[max(0.0,x) for x in asset.evalParmTuple('grid_size')]
        spacing3=[max(0.001,x) for x in asset.evalParmTuple('grid_spacing')]
        bysp=asset.evalParm('grid_spacemode')==1
        counts=[];steps=[]
        for a,name in enumerate(('x','y','z')):
            if bysp:
                counts.append(min(100,max(1,int(size3[a]/spacing3[a]+1e-6)+1)));steps.append(spacing3[a])
            else:
                c=min(100,max(1,asset.evalParm('grid_count'+name)));counts.append(c)
                steps.append(size3[a]/(c-1) if c>1 else 0.0)
        centered=asset.evalParm('grid_center')
        lo=[(-0.5*(counts[a]-1)*steps[a] if centered else 0.0) for a in range(3)]
        hi=[lo[a]+(counts[a]-1)*steps[a] for a in range(3)]
        seen=set()
        for ax in (0,1,2):
            for u in (0,1):
                for w in (0,1):
                    others=[b for b in (0,1,2) if b!=ax]
                    a0=[0,0,0];a1=[0,0,0]
                    for b,pick in zip(others,(u,w)):
                        a0[b]=a1[b]=(hi if pick else lo)[b]
                    a0[ax]=lo[ax];a1[ax]=hi[ax]
                    key=(tuple(round(x,6) for x in a0),tuple(round(x,6) for x in a1))
                    if a0!=a1 and key not in seen:
                        seen.add(key);segments.append([V(*a0),V(*a1)])
        total=counts[0]*counts[1]*counts[2]
        positive=[s for s in steps if s>0]
        tick=max(min(positive)*.15,.02) if positive else .1
        if total<=256:
            for k in range(counts[2]):
                for j in range(counts[1]):
                    for i in range(counts[0]):
                        p=V(lo[0]+i*steps[0],lo[1]+j*steps[1],lo[2]+k*steps[2])
                        for d in (V(tick,0,0),V(0,tick,0),V(0,0,tick)):
                            segments.append([p-d,p+d])
        extent=[hi[a]-lo[a] for a in range(3) if hi[a]>lo[a]]
        size=max(min(extent)*.05,.15) if extent else .15
        color=Gf.Vec3f(.55,1,.35)
    else:
        import math
        radius=max(0.0,asset.evalParm('circle_radius'))
        count=min(10000,max(1,asset.evalParm('circle_count')))
        start=math.radians(asset.evalParm('circle_start'))
        arc=min(360.0,max(0.0,asset.evalParm('circle_arc')))
        plane=asset.evalParm('circle_plane')
        u,v=((V(1,0,0),V(0,0,-1)),(V(1,0,0),V(0,1,0)),(V(0,1,0),V(0,0,1)))[plane]
        full=arc>=359.9999
        step=(2*math.pi/count if full else math.radians(arc)/(count-1)) if count>1 else 0.0
        def at(t,r=radius):return (u*math.cos(t)+v*math.sin(t))*r
        # the circle or arc itself, 72 segments per full turn at least
        sweep=2*math.pi if full else math.radians(arc)
        segments_n=max(2,int(72*sweep/(2*math.pi))+1)
        segments.append([at(start+sweep*k/(segments_n-1)) for k in range(segments_n)])
        size=max(radius*.05,.15)
        tick=min(size*.6,max(radius*.1,.05))
        if count<=256:
            for i in range(count):
                t=start+i*step
                longer=1.6 if i==0 else 1.0           # the first point (Start angle) gets a longer tick
                segments.append([at(t,radius-tick*longer),at(t,radius+tick*longer)])
        else:
            for t in (start,start+(count-1)*step):
                segments.append([at(t,radius-tick),at(t,radius+tick)])
        color=Gf.Vec3f(1,.45,.9)
    pivot=V(*asset.evalParmTuple('bound_p'))
    pivot_marker=[[pivot-V(size,0,0),pivot+V(size,0,0)],
                  [pivot-V(0,size,0),pivot+V(0,size,0)],
                  [pivot-V(0,0,size),pivot+V(0,0,size)]]
    top=UsdGeom.Xform.Define(stage,group)
    top.GetPurposeAttr().Set(UsdGeom.Tokens.guide)
    top.GetPrim().SetActive(True)
    def curves(name,paths,rgb,width):
        c=UsdGeom.BasisCurves.Define(stage,group.AppendChild(name))
        c.CreateTypeAttr(UsdGeom.Tokens.linear);c.CreateWrapAttr(UsdGeom.Tokens.nonperiodic)
        c.CreateCurveVertexCountsAttr(Vt.IntArray([len(p) for p in paths]))
        c.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(v) for p in paths for v in p]))
        c.CreateWidthsAttr(Vt.FloatArray([width]));c.SetWidthsInterpolation(UsdGeom.Tokens.constant)
        c.GetDisplayColorPrimvar().Set(Vt.Vec3fArray([rgb]))
        c.GetPurposeAttr().Set(UsdGeom.Tokens.guide)
    physics=asset.evalParm('phys_on')
    if not asset.evalParm('bound_scale_instances') or physics:
        scale=V(*[max(0.0001,x) for x in asset.evalParmTuple('bound_s')])
        segments=[[pivot+V(*[(q[k]-pivot[k])*scale[k] for k in range(3)]) for q in path] for path in segments]
    if physics:
        # Physics Settle simulates in world space: the PointInstancer transform is identity, so Rotation and Position are applied here.
        m=hou.hmath.buildTransform({'rotate':tuple(asset.evalParmTuple('bound_r')),'translate':tuple(asset.evalParmTuple('bound_t')),'pivot':tuple(pivot)},transform_order='srt',rotate_order='xyz')
        def world(q):
            r=hou.Vector3(*q)*m
            return V(r[0],r[1],r[2])
        segments=[[world(q) for q in path] for path in segments]
        pivot_marker=[[world(q) for q in path] for path in pivot_marker]
    curves('Bounds',segments,color,size*.04)
    curves('Pivot',pivot_marker,Gf.Vec3f(1,.2,.8),size*.04)
    if physics:
        # The lowest stones start at the spawn bounds lifted by Drop Height; the ground plane is drawn wider than the spawn so the pour can be judged.
        lift=asset.evalParm('phys_drop')
        curves('Drop',[[V(q[0],q[1]+lift,q[2]) for q in path] for path in segments],Gf.Vec3f(1,.9,.3),size*.025)
        if asset.evalParm('phys_ground'):
            xs=[q[0] for path in segments for q in path];zs=[q[2] for path in segments for q in path]
            cx,cz=0.5*(min(xs)+max(xs)),0.5*(min(zs)+max(zs));hx,hz=0.5*(max(xs)-min(xs))*1.3+0.15,0.5*(max(zs)-min(zs))*1.3+0.15
            gy=asset.evalParm('phys_ground_height')
            curves('Ground',[[V(cx-hx,gy,cz-hz),V(cx+hx,gy,cz-hz),V(cx+hx,gy,cz+hz),V(cx-hx,gy,cz+hz),V(cx-hx,gy,cz-hz)]],Gf.Vec3f(.75,.5,.25),size*.03)
