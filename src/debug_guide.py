# Embedded in a Python LOP (debug_guide), last in the Arraytron chain. Visual debugging as GUIDE-purpose prims under <output>/Debug: they show in the Solaris
# viewport and never render in Karma (guides are not a render purpose), so debugging cannot change the final image. With Debug off this node does nothing.
# Views: Generated Points, Rejected Points (generated but gone at the end: masked, thinned, separated, avoided), Final Points coloured by Prototype / Id /
# Weight, Axes (up and forward of every instance), Collision Radius (the Separation spheres), Cluster Centres. Positions are in the space of the points
# (before the Bounds Transform), so the Debug prim, a child of the output prim, moves with the layout.
import hou
import numpy as np
from pxr import Gf, Sdf, UsdGeom, Vt
node=hou.pwd()
asset=node.parent()
stage=node.editableStage()
if asset.evalParm('dbg_on'):
    asset.evalParm('cam_frame')                                                                 # follow the timeline (Grow, animated cameras)
    m=asset.hdaModule();root=Sdf.Path(asset.evalParm('outputpath'));prim=stage.GetPrimAtPath(root)
    if prim and prim.IsValid():
        path=root.AppendChild('Debug');UsdGeom.Scope.Define(stage,path);UsdGeom.Imageable(stage.GetPrimAtPath(path)).CreatePurposeAttr().Set('guide')
        size=asset.evalParm('dbg_size');LIMIT=20000
        def v3(a):return Vt.Vec3fArray([Gf.Vec3f(*[float(x) for x in r]) for r in a])
        def points(name,pos,color,widths=None):
            if not len(pos):return
            p=UsdGeom.Points.Define(stage,path.AppendChild(name));UsdGeom.Imageable(p.GetPrim()).CreatePurposeAttr().Set('guide');pos=np.asarray(pos)[:LIMIT]
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
        if asset.evalParm('dbg_generated') or asset.evalParm('dbg_rejected'):
            gids=np.array(gen.pointIntAttribValues('id'),dtype=np.int64) if gen.intrinsicValue('pointcount') else np.zeros(0,dtype=np.int64);gpos=np.array(gen.pointFloatAttribValues('P')).reshape(-1,3) if gen.intrinsicValue('pointcount') else np.zeros((0,3))
            if asset.evalParm('dbg_generated'):points('Generated',gpos,(0.9,0.9,0.9))
            if asset.evalParm('dbg_rejected'):
                gone=~np.isin(gids,fids);points('Rejected',gpos[gone],(1.0,0.1,0.1))
        if len(fids):
            fpos=np.array(final.pointFloatAttribValues('P')).reshape(-1,3);q=np.array(final.pointFloatAttribValues('orient')).reshape(-1,4)
            colour=asset.evalParm('dbg_color')
            if colour:
                if colour==1:
                    pi=np.array(final.pointIntAttribValues('protoindex'));palette=np.array([[0.2,0.6,1.0],[1.0,0.6,0.1],[0.3,0.9,0.3],[0.9,0.3,0.8],[0.9,0.9,0.2],[0.3,0.9,0.9]]);cols=palette[pi%len(palette)]
                elif colour==2:
                    h=m.scatter_hash(fids,7,81);cols=np.column_stack([0.3+0.7*h,0.3+0.7*m.scatter_hash(fids,7,82),0.3+0.7*m.scatter_hash(fids,7,83)])
                else:
                    w=np.array(final.pointFloatAttribValues('mask'))*np.array(final.pointFloatAttribValues('density')) if final.findPointAttrib('mask') is not None and final.findPointAttrib('density') is not None else np.ones(len(fids))
                    cols=np.column_stack([1.0-w,w,0.1*np.ones(len(w))])
                points('Final',fpos,cols)
            if asset.evalParm('dbg_axes'):
                x,y,z,w=q[:,0],q[:,1],q[:,2],q[:,3]
                up=np.column_stack([2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)]);fwd=np.column_stack([2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y)])
                segs=[];cols=[]
                for p,u,f in zip(fpos,up,fwd):segs+=[[p,p+u*size*4],[p,p+f*size*4]];cols+=[(0.2,1.0,0.2),(0.3,0.5,1.0)]
                lines('Axes',segs,cols)
            if asset.evalParm('dbg_radius'):
                cen,rad=m.instance_spheres_for(asset,final)[1:] if asset.parm('overlap_size') is not None else (fpos,np.full(len(fpos),size))
                ang=np.linspace(0,2*np.pi,25);segs=[np.column_stack([c[0]+r*np.cos(ang),np.full(25,c[1]),c[2]+r*np.sin(ang)]) for c,r in zip(cen,rad)];lines('Radius',segs,[(1.0,0.8,0.1)]*len(segs))
        if asset.evalParm('dbg_centres') and asset.parm('cluster_prim') is not None and asset.evalParm('mode')==7:
            P_,T_,area_,normals_,vn_=m.cluster_surface(asset);centres,_,_=m.surface_points(P_,T_,area_,normals_,vn_,asset.evalParm('cluster_count'),asset.evalParm('cluster_seed'),asset.evalParm('cluster_normal')==1,0.0,180.0,0.0,0.0);points('ClusterCentres',centres,(1.0,1.0,0.1))
