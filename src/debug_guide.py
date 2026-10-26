# Embedded in a Python LOP (debug_guide), last in the Arraytron chain. Visual debugging as GUIDE-purpose prims next to the instancer (<output>_View, a sibling: Hydra does not draw the children of a PointInstancer that are not prototypes; before v1.22.0 a child <output>/Debug): they show in the Solaris
# viewport and never render in Karma (guides are not a render purpose), so debugging cannot change the final image. With Debug off this node does nothing.
# Views: Generated Points, Rejected Points (generated but gone at the end: masked, thinned, separated, avoided), Final Points coloured by Prototype / Id /
# Weight, Axes (up and forward of every instance), Collision Radius (the Separation spheres), Cluster Centres. Positions are in the space of the points
# (before the Bounds Transform), so the Debug prim, a child of the output prim, moves with the layout.
import hou
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, Vt
node=hou.pwd()
asset=node.parent()
stage=node.editableStage()
vt=asset.evalParm('viz_target') if asset.parm('viz_target') is not None else 0;vw=asset.evalParm('viz_what') if asset.parm('viz_what') is not None else 0
if vt==0 and asset.parm('mask_viz') is not None and asset.evalParm('mask_viz')>0:vt,vw=asset.evalParm('mask_viz'),0                          # the Visualize toggles of the Mask and Noise sections
if vt==0 and asset.parm('noise_viz') is not None and asset.evalParm('noise_viz')>0:vt,vw=2,3
viz=vt>0                                                                                         # Visualize (v1.24.0): the Mask / Field Stack / noise as colour on the scattering surface and the instances
dbg=bool(asset.evalParm('dbg_on'));vm=asset.evalParm('view_mode') if asset.parm('view_mode') is not None else 0;view=vm>0               # view: Points Only (v1.22.0), the instances are hidden and the points shown
if dbg or view or viz:
    asset.evalParm('cam_frame')                                                                 # follow the timeline (Grow, animated cameras)
    m=asset.hdaModule();root=Sdf.Path(asset.evalParm('outputpath'));prim=stage.GetPrimAtPath(root)
    if prim and prim.IsValid():
        if asset.parm('view_mode') is not None:                                                    # v1.22.0 and newer: NEXT to the instancer, with its transform
            path=root.GetParentPath().AppendChild(root.name+'_View');view_xf=UsdGeom.Xform.Define(stage,path);view_xf.AddTransformOp().Set(UsdGeom.Xformable(prim).GetLocalTransformation(Usd.TimeCode.Default()))
        else:path=root.AppendChild('Debug');UsdGeom.Scope.Define(stage,path)
        UsdGeom.Imageable(stage.GetPrimAtPath(path)).CreatePurposeAttr().Set('guide');vpath=path
        size=asset.evalParm('dbg_size');LIMIT=20000
        PALETTES=(((0,0.2,1),(1,1,0)),                                                              # 0 Blue to Yellow (the first Visualize colours)
                  ((0,0,0),(0.7,0,0),(1,0.7,0),(1,1,1)),                                            # 1 Heat
                  ((0.267,0.005,0.329),(0.23,0.322,0.546),(0.128,0.567,0.551),(0.37,0.789,0.383),(0.993,0.906,0.144)),   # 2 Viridis
                  ((0,0,0.015),(0.317,0.072,0.485),(0.716,0.215,0.475),(0.987,0.535,0.382),(0.987,0.991,0.749)),         # 3 Magma
                  ((0.19,0.07,0.23),(0.28,0.41,0.93),(0.1,0.82,0.66),(0.64,0.99,0.24),(0.97,0.74,0.22),(0.75,0.2,0.05),(0.48,0.02,0.01)),   # 4 Rainbow (turbo like)
                  ((0,0,0),(1,1,1)),                                                                  # 5 Grayscale
                  ((1,0,0),(1,1,0),(0,1,0)),                                                          # 6 Red Yellow Green
                  ((0.23,0.3,0.75),(0.87,0.87,0.87),(0.71,0.016,0.15)),                              # 7 Cool to Warm
                  ((0.1,0.25,0.6),(0.2,0.6,0.3),(0.85,0.8,0.4),(0.55,0.4,0.3),(1,1,1)))              # 8 Terrain
        pal=asset.evalParm('viz_palette') if asset.parm('viz_palette') is not None else 0;LUT_N=256;xs_=np.linspace(0.0,1.0,LUT_N)
        if pal>=len(PALETTES) and asset.parm('viz_ramp') is not None:                                  # 9 Custom: the Custom Gradient ramp
            ramp_=asset.parm('viz_ramp').evalAsRamp();LUT=np.array([list(ramp_.lookup(float(x)))[:3] for x in xs_])
        else:
            stops=np.array(PALETTES[min(pal,len(PALETTES)-1)],dtype=np.float64);LUT=np.column_stack([np.interp(xs_,np.linspace(0.0,1.0,len(stops)),stops[:,c]) for c in range(3)])
        vlo,vhi=(asset.evalParmTuple('viz_range') if asset.parmTuple('viz_range') is not None else (0.0,1.0))
        def heat(w):                                                                                  # a value 0..1 (after the Range) to a colour of the palette
            w=np.clip((np.asarray(w,dtype=np.float64)-vlo)/max(vhi-vlo,1e-9),0.0,1.0)*(LUT_N-1);k=np.minimum(np.floor(w).astype(int),LUT_N-2);f=(w-k)[:,None];return LUT[k]*(1.0-f)+LUT[k+1]*f
        def v3(a):return Vt.Vec3fArray([Gf.Vec3f(*[float(x) for x in r]) for r in a])
        def points(name,pos,color,widths=None,where=None):
            if not len(pos):return
            p=UsdGeom.Points.Define(stage,(where or path).AppendChild(name));UsdGeom.Imageable(p.GetPrim()).CreatePurposeAttr().Set('guide');pos=np.asarray(pos)[:LIMIT]
            p.CreatePointsAttr(v3(pos));p.CreateWidthsAttr(Vt.FloatArray([float(size)]*len(pos)))
            colors=np.asarray(color,dtype=np.float64);colors=np.tile(colors,(len(pos),1)) if colors.ndim==1 else colors[:len(pos)]
            pv=p.CreateDisplayColorPrimvar(UsdGeom.Tokens.vertex);pv.Set(v3(colors))
        def lines(name,segments,colors):
            if not len(segments):return
            segments=np.asarray(segments)[:LIMIT];c=UsdGeom.BasisCurves.Define(stage,path.AppendChild(name));UsdGeom.Imageable(c.GetPrim()).CreatePurposeAttr().Set('guide')
            c.CreateTypeAttr('linear');c.CreateCurveVertexCountsAttr(Vt.IntArray([len(s) for s in segments]));c.CreatePointsAttr(v3(np.vstack(segments)));c.CreateWidthsAttr(Vt.FloatArray([float(size)*0.15]));c.SetWidthsInterpolation(UsdGeom.Tokens.constant)
            pv=c.CreateDisplayColorPrimvar(UsdGeom.Tokens.uniform);pv.Set(v3(np.asarray(colors)[:LIMIT]))
        final=asset.node('USD_COMPILER/OUT_POINTS').geometry();gen=asset.node('USD_COMPILER/DISTRIBUTION_GENERATOR').geometry()
        if final is None or gen is None:raise hou.NodeError('Debug Views: the points could not be generated (see the error of the node above); fix that first.')
        fids=np.array(final.pointIntAttribValues('id'),dtype=np.int64) if final.intrinsicValue('pointcount') else np.zeros(0,dtype=np.int64)
        if dbg and (asset.evalParm('dbg_generated') or asset.evalParm('dbg_rejected')):
            gids=np.array(gen.pointIntAttribValues('id'),dtype=np.int64) if gen.intrinsicValue('pointcount') else np.zeros(0,dtype=np.int64);gpos=np.array(gen.pointFloatAttribValues('P')).reshape(-1,3) if gen.intrinsicValue('pointcount') else np.zeros((0,3))
            if asset.evalParm('dbg_generated'):points('Generated',gpos,(0.9,0.9,0.9))
            if asset.evalParm('dbg_rejected'):
                gone=~np.isin(gids,fids);points('Rejected',gpos[gone],(1.0,0.1,0.1))
        if len(fids):
            fpos=np.array(final.pointFloatAttribValues('P')).reshape(-1,3);q=np.array(final.pointFloatAttribValues('orient')).reshape(-1,4);icols=None
            if viz and vt in (2,3):
                what=vw
                def pattr(name):return np.array(final.pointFloatAttribValues(name)) if final.findPointAttrib(name) is not None else np.ones(len(fids))
                if what==0:val=pattr('maskweight')
                elif what==1:val=pattr('fieldweight')
                elif what==2:val=pattr('maskweight')*pattr('fieldweight')
                else:
                    amp=np.linalg.norm(asset.evalParmTuple('noise_amp')) if asset.parmTuple('noise_amp') is not None else 0.0
                    val=np.linalg.norm(np.array(final.pointFloatAttribValues('noise_disp')).reshape(-1,3),axis=1)/max(amp,1e-9) if final.findPointAttrib('noise_disp') is not None else np.zeros(len(fids))
                icols=heat(val)
                if vm==0:points('VizInstances',fpos,icols)
            colour=asset.evalParm('dbg_color')
            if colour and vm<2 and icols is None:
                if colour==1:
                    pi=np.array(final.pointIntAttribValues('protoindex'));palette=np.array([[0.2,0.6,1.0],[1.0,0.6,0.1],[0.3,0.9,0.3],[0.9,0.3,0.8],[0.9,0.9,0.2],[0.3,0.9,0.9]]);cols=palette[pi%len(palette)]
                elif colour==2:
                    h=m.scatter_hash(fids,7,81);cols=np.column_stack([0.3+0.7*h,0.3+0.7*m.scatter_hash(fids,7,82),0.3+0.7*m.scatter_hash(fids,7,83)])
                elif colour==4 and final.findPointAttrib('biome') is not None:
                    bi=np.array(final.pointIntAttribValues('biome'));palette=np.array([[0.2,0.7,0.25],[0.95,0.8,0.2],[0.3,0.55,1.0],[0.85,0.3,0.25],[0.7,0.4,0.9],[0.3,0.85,0.8],[0.95,0.55,0.2],[0.6,0.6,0.6]]);cols=palette[(bi-1)%len(palette)]
                elif colour==4:cols=np.tile([0.5,0.5,0.5],(len(fids),1))
                else:
                    w=np.array(final.pointFloatAttribValues('mask'))*np.array(final.pointFloatAttribValues('density')) if final.findPointAttrib('mask') is not None and final.findPointAttrib('density') is not None else np.ones(len(fids))
                    cols=np.column_stack([1.0-w,w,0.1*np.ones(len(w))])
                points('Final',fpos,cols,where=vpath if vm==1 else None)
            elif vm==1:points('Final',fpos,icols if icols is not None else (0.35,1.0,0.55),where=vpath)
            if dbg and asset.evalParm('dbg_axes'):
                x,y,z,w=q[:,0],q[:,1],q[:,2],q[:,3]
                up=np.column_stack([2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)]);fwd=np.column_stack([2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y)])
                segs=[];cols=[]
                for p,u,f in zip(fpos,up,fwd):segs+=[[p,p+u*size*4],[p,p+f*size*4]];cols+=[(0.2,1.0,0.2),(0.3,0.5,1.0)]
                lines('Axes',segs,cols)
            if dbg and asset.evalParm('dbg_radius'):
                cen,rad=m.instance_spheres_for(asset,final)[1:] if asset.parm('overlap_size') is not None else (fpos,np.full(len(fpos),size))
                ang=np.linspace(0,2*np.pi,25);segs=[np.column_stack([c[0]+r*np.cos(ang),np.full(25,c[1]),c[2]+r*np.sin(ang)]) for c,r in zip(cen,rad)];lines('Radius',segs,[(1.0,0.8,0.1)]*len(segs))
        if dbg and asset.evalParm('dbg_centres') and asset.parm('cluster_prim') is not None and asset.evalParm('mode')==7:
            P_,T_,area_,normals_,vn_=m.cluster_surface(asset);centres,_,_=m.surface_points(P_,T_,area_,normals_,vn_,asset.evalParm('cluster_count'),asset.evalParm('cluster_seed'),asset.evalParm('cluster_normal')==1,0.0,180.0,0.0,0.0);points('ClusterCentres',centres,(1.0,1.0,0.1))
        if view:                                                                                  # Points Only: every id is invisible (the instancer itself stays, so its guide children show)
            pi=UsdGeom.PointInstancer(prim)
            if pi:
                attr=pi.CreateInvisibleIdsAttr();ids=set(int(i) for i in (pi.GetIdsAttr().Get() or [])) or set(int(i) for i in fids)
                for time in [Usd.TimeCode.Default()]+[Usd.TimeCode(t) for t in attr.GetTimeSamples()]:
                    attr.Set(Vt.Int64Array(sorted(ids|set(int(i) for i in (attr.Get(time) or [])))),time)
            if vm>=2:                                                                              # Boxes / Spheres: one guide shape per instance, from the bound of its prototype
                base=vpath.AppendChild('Proxy');inst=UsdGeom.PointInstancer.Define(stage,base);UsdGeom.Imageable(inst.GetPrim()).CreatePurposeAttr().Set('guide')
                cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),[UsdGeom.Tokens.default_,UsdGeom.Tokens.render,UsdGeom.Tokens.proxy]);palette=[(0.2,0.6,1.0),(1.0,0.6,0.1),(0.3,0.9,0.3),(0.9,0.3,0.8),(0.9,0.9,0.2),(0.3,0.9,0.9)];targets=pi.GetPrototypesRel().GetTargets();shapes=[]
                for i,target in enumerate(targets):
                    box=cache.ComputeLocalBound(stage.GetPrimAtPath(target)).ComputeAlignedRange();lo,hi=box.GetMin(),box.GetMax()
                    if box.IsEmpty():lo,hi=Gf.Vec3d(-0.05),Gf.Vec3d(0.05)
                    centre=(lo+hi)*0.5;ext=hi-lo;shape_path=base.AppendChild('P%d'%i)
                    if vm==2:shape=UsdGeom.Cube.Define(stage,shape_path);shape.CreateSizeAttr(1.0);scale=Gf.Vec3f(ext[0],ext[1],ext[2])
                    else:shape=UsdGeom.Sphere.Define(stage,shape_path);shape.CreateRadiusAttr(1.0);scale=Gf.Vec3f(*([0.5*ext.GetLength()]*3))   # the bounding sphere
                    UsdGeom.Xformable(shape).AddTranslateOp().Set(Gf.Vec3d(centre));UsdGeom.Xformable(shape).AddScaleOp().Set(scale)
                    UsdGeom.Imageable(shape.GetPrim()).CreatePurposeAttr().Set('guide');shape.CreateDisplayColorAttr([Gf.Vec3f(*palette[i%len(palette)])]);shapes.append(shape_path)
                inst.CreatePrototypesRel().SetTargets(shapes);t=Usd.TimeCode(hou.frame())
                if icols is not None:UsdGeom.PrimvarsAPI(inst).CreatePrimvar('displayColor',Sdf.ValueTypeNames.Color3fArray,UsdGeom.Tokens.varying).Set(v3(icols))   # one colour per instance
                for attr in ('ProtoIndices','Positions','Orientations','Scales','Ids'):
                    src=getattr(pi,'Get%sAttr'%attr)().Get(t)
                    if src is not None:getattr(inst,'Create%sAttr'%attr)().Set(src)
        if viz and vt in (1,3) and vw<3:                                                              # the value over the scattering surface: vertex colours on a copy of it, and / or dots
            mode=asset.evalParm('mode');tri=None
            try:
                if mode==5:tri=m.stage_surface(asset)
                elif mode==6:tri=m.paint_surface(asset)
                elif mode==7:tri=m.cluster_surface(asset)
                elif mode==1:tri=m.plane_rect(0.5*asset.evalParm('area_sizex'),0.5*asset.evalParm('area_sizez'),0.0)
            except hou.Error:tri=None
            if tri is not None:
                P_,T_,area_,normals_,vn_=tri;what=vw;style=asset.evalParm('viz_style') if asset.parm('viz_style') is not None else 1;budget=asset.evalParm('viz_res') if asset.parm('viz_res') is not None else 20000
                def surface_values(pos):
                    ids_=np.arange(len(pos));ones=np.ones(len(pos))
                    mw=m.mask_weights(asset,m.mask_values(asset,pos,ids_)) if asset.parm('mask_source') is not None and asset.evalParm('mask_source')!=0 else ones
                    fw=m.stack_weights(asset,pos,ids_) if asset.parm('fields') is not None else None;fw=ones if fw is None else fw
                    return (mw,fw,mw*fw)[what]
                if style in (0,2):                                                                    # a copy of the surface cut into small triangles, a colour on every corner
                    tris=np.asarray(P_)[np.asarray(T_)]
                    while len(tris)*4<=budget:                                                        # every triangle into four, until the budget of triangles is used
                        a_,b_,c_=tris[:,0],tris[:,1],tris[:,2];ab,bc,ca=(a_+b_)*0.5,(b_+c_)*0.5,(c_+a_)*0.5
                        tris=np.concatenate([np.stack([a_,ab,ca],1),np.stack([ab,b_,bc],1),np.stack([ca,bc,c_],1),np.stack([ab,bc,ca],1)])
                    corners=tris.reshape(-1,3);nrm=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]);nrm=nrm/np.maximum(np.linalg.norm(nrm,axis=1),1e-12)[:,None]
                    lifted=corners+np.repeat(nrm,3,axis=0)*size*0.3
                    cols=heat(surface_values(corners));mesh=UsdGeom.Mesh.Define(stage,path.AppendChild('VizSurface'));UsdGeom.Imageable(mesh.GetPrim()).CreatePurposeAttr().Set('guide')
                    mesh.CreatePointsAttr(v3(lifted));mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3]*len(tris)));mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(list(range(len(corners)))));mesh.CreateDoubleSidedAttr(True)
                    mesh.CreateDisplayColorPrimvar(UsdGeom.Tokens.vertex).Set(v3(cols))
                    UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('displayOpacity',Sdf.ValueTypeNames.FloatArray,UsdGeom.Tokens.constant).Set(Vt.FloatArray([float(asset.evalParm('viz_opacity')) if asset.parm('viz_opacity') is not None else 1.0]))
                if style in (1,2):                                                                    # dots on the surface
                    pos,nrm,_=m.surface_points(P_,T_,area_,normals_,vn_,max(100,min(LIMIT,asset.evalParm('viz_count'))),1,False,0.0,180.0,0.0,0.0)
                    points('VizSurface' if style==1 else 'VizSurfaceDots',pos+nrm*size*0.6,heat(surface_values(pos)))
