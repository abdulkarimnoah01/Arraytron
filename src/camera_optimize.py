# Embedded in a Python LOP (camera_optimize), after the Bounds Transform. Camera-aware optimisation of the PointInstancer, reversible and USD-native:
# instances are hidden through invisibleIds (merged with the ones Grow hides) and level of detail is a switch of protoIndices to LOD prototypes.
# Nothing is deleted; with Camera off this node does not touch the stage and does not depend on time. See src/arraytron_camera.py for the maths.
import hou
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, Vt
node=hou.pwd()
asset=node.parent()
stage=node.editableStage()
if asset.evalParm('cam_on'):
    m=asset.hdaModule();frame=asset.evalParm('cam_frame');time=Usd.TimeCode(frame)                     # cam_frame is the frame number (the time dependency), read only while Camera is on
    root=Sdf.Path(asset.evalParm('outputpath'));prim=stage.GetPrimAtPath(root)
    camera_path=asset.evalParm('cam_prim').strip()
    cam_prim=stage.GetPrimAtPath(camera_path) if camera_path else None
    if not cam_prim or not cam_prim.IsValid() or not cam_prim.IsA(UsdGeom.Camera):
        raise hou.NodeError('Camera Prim %s is not a camera in the stream: wire a Camera LOP into the first input and pick it.'%(camera_path or '(empty)'))
    if prim and prim.IsValid():
        pi=UsdGeom.PointInstancer(prim)
        pos=np.array(pi.GetPositionsAttr().Get(time) or [],dtype=np.float64).reshape(-1,3);n=len(pos)
        if n:
            ids=np.array(pi.GetIdsAttr().Get(time) or np.arange(n),dtype=np.int64);proto=np.array(pi.GetProtoIndicesAttr().Get(time) or np.zeros(n),dtype=np.int64)
            scales=np.array(pi.GetScalesAttr().Get(time) or [],dtype=np.float64).reshape(-1,3) if pi.GetScalesAttr().Get(time) else np.ones((n,3))
            xc=UsdGeom.XformCache(time);M=np.array(xc.GetLocalToWorldTransform(prim),dtype=np.float64).reshape(4,4);world=np.column_stack([pos,np.ones(n)])@M;world=world[:,:3]
            wscale=float(np.linalg.norm(M[0,:3]))
            # bounding radius of every prototype (half the diagonal of its bounding box, about the prototype origin), times the instance scale
            targets=pi.GetPrototypesRel().GetTargets();cache=UsdGeom.BBoxCache(time,[UsdGeom.Tokens.default_,UsdGeom.Tokens.render]);rad=np.zeros(max(len(targets),1))
            for k,t in enumerate(targets):
                tp=stage.GetPrimAtPath(t)
                if tp and tp.IsValid():
                    box=cache.ComputeUntransformedBound(tp).ComputeAlignedRange();lo,hi=np.array(box.GetMin()),np.array(box.GetMax())
                    if np.all(np.isfinite(lo)) and np.all(np.isfinite(hi)) and not box.IsEmpty():rad[k]=float(max(np.linalg.norm(lo),np.linalg.norm(hi),0.5*np.linalg.norm(hi-lo)))
            radius=rad[np.minimum(proto,len(rad)-1)]*scales.max(axis=1)*wscale
            gcam=UsdGeom.Camera(cam_prim).GetCamera(time);fr=gcam.frustum;view=np.array(fr.ComputeViewMatrix(),dtype=np.float64).reshape(4,4);proj=np.array(fr.ComputeProjectionMatrix(),dtype=np.float64).reshape(4,4)
            ortho=gcam.projection==Gf.Camera.Orthographic;v=m.view_space(world,view);depth=-v[:,2];dist=np.linalg.norm(v,axis=1);near,far=gcam.clippingRange.min,gcam.clippingRange.max
            hx,hy=1.0/proj[0,0],1.0/proj[1,1]                                                         # tangent of the half field of view (half extents for an orthographic camera)
            hidden=np.zeros(n,dtype=bool);why={'frustum':0,'far':0,'density':0,'behind':0}
            def hide(mask,key):
                fresh=mask&~hidden;why[key]+=int(fresh.sum());hidden[mask]=True                    # in place: no global needed
            behind=depth<=0.0
            if asset.evalParm('cam_behind')!=0:
                keep=np.zeros(n) if asset.evalParm('cam_behind')==2 else np.full(n,asset.evalParm('cam_behind_keep'))
                hide(behind&~(m.scatter_hash(ids,asset.evalParm('cam_seed'),72)<keep),'behind')
            if asset.evalParm('cam_frustum'):
                out=m.frustum_outside(v,radius,hx,hy,near,far,asset.evalParm('cam_margin'),ortho)
                hide(out&~behind if asset.evalParm('cam_behind')!=0 else out,'frustum')
            if asset.evalParm('cam_distcull'):hide(dist-radius>asset.evalParm('cam_maxdist'),'far')
            if asset.evalParm('cam_densityon'):
                keep=m.density_keep(dist,asset.evalParm('cam_dnear'),asset.evalParm('cam_dfar'),asset.evalParm('cam_dmin'))
                hide(~(m.scatter_hash(ids,asset.evalParm('cam_seed'),71)<keep-1e-12),'density')
            existing=pi.GetInvisibleIdsAttr().Get(time) or []
            pi.CreateInvisibleIdsAttr().Set(Vt.Int64Array(m.merged_invisible(existing,ids[hidden])),time)
            data={'total':int(n),'hidden':int(hidden.sum()),'visible':int(n-hidden.sum()),'frustum':why['frustum'],'far':why['far'],'density':why['density'],'behind':why['behind'],'frame':float(frame)}
            level=np.zeros(n,dtype=np.int64)
            if asset.evalParm('cam_lod'):
                table=m.lod_table(asset)
                if asset.evalParm('lod_by')==0:level=m.lod_levels(dist,[asset.evalParm('lod_d1'),asset.evalParm('lod_d2'),asset.evalParm('lod_d3')],False)
                else:level=m.lod_levels(m.screen_fraction(depth,radius,proj[1,1],ortho)*100.0,[asset.evalParm('lod_s1'),asset.evalParm('lod_s2'),asset.evalParm('lod_s3')],True)
                new,applied=m.remap_proto_indices(proto,level,table);pi.CreateProtoIndicesAttr().Set(Vt.IntArray([int(i) for i in new]),time);level=applied
                data['lod']=[int((level==k).sum()) for k in range(4)]
            prim.SetCustomDataByKey('arraytron:camera',data)
            if asset.parm('pv_lod') is not None and asset.evalParm('pv_lod'):
                api=UsdGeom.PrimvarsAPI(prim);pv=api.CreatePrimvar('arraytron_lod',Sdf.ValueTypeNames.IntArray,UsdGeom.Tokens.varying);pv.Set(Vt.IntArray([int(i) for i in level]),time)
