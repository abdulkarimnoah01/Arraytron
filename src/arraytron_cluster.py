# Clustering (v0.8.0): Distribution Mode Cluster. Cluster centres are scattered over a surface (the Cluster Surface prim, or a flat ground rectangle when it is
# empty) exactly like Surface Scatter; each centre gets a group of instances around it, thickest in the middle, projected onto the same surface.
# Appended after the paint module (it reuses scatter_hash, surface_points, normal_alignment, stage_surface, tangent_frame, make_projector).
import numpy as np

CLUSTER_ID_STRIDE=1000                    # ids are cluster * 1000 + member, so adding clusters or members never renames the existing points
CLUSTER_MAX_POINTS=20000

def plane_rect(half_x,half_z,height=0.0):
    """A ground rectangle (the same tuple as triangles_world): two triangles at Y = height, normal +Y."""
    P=np.array([[-half_x,height,-half_z],[half_x,height,-half_z],[half_x,height,half_z],[-half_x,height,half_z]],dtype=np.float64);T=np.array([[0,2,1],[0,3,2]],dtype=np.int64)
    c=np.cross(P[T[:,1]]-P[T[:,0]],P[T[:,2]]-P[T[:,0]]);area=0.5*np.linalg.norm(c,axis=1);normals=c/np.linalg.norm(c,axis=1)[:,None]
    vn=np.tile([0.0,1.0,0.0],(4,1));return P,T,area,normals,vn

def cluster_shape(count,per,jitter,seed):
    """Members and radius factor of every cluster: members = per x (1 +/- jitter), radius factor = 1 +/- jitter, each from the cluster's own hashes."""
    c=np.arange(count);m=np.round(per*(1.0+jitter*(2.0*scatter_hash(c,seed,41)-1.0))).astype(np.int64);m=np.clip(m,1,CLUSTER_ID_STRIDE-1)
    rf=1.0+jitter*(2.0*scatter_hash(c,seed,42)-1.0);return m,np.maximum(rf,0.05)

def member_offsets(ids,radius,falloff,seed):
    """Radial distance and angle of each member from its cluster centre. u^p with p = 0.5 + 1.5 x falloff: falloff 0 fills the disc evenly, 1 packs
    the members towards the centre. radius is a scalar or one value per member."""
    u=scatter_hash(ids,seed,43);a=2.0*np.pi*scatter_hash(ids,seed,44);return np.asarray(radius)*u**(0.5+1.5*falloff),a

def cluster_points(surface,count,per,radius,falloff,jitter,seed,smooth=True):
    """Positions (N,3), normals (N,3), ids (N,) and the cluster number of each member (N,). The centres are surface_points(...) with the same seed, so
    cluster c is always in the same place whatever the Cluster Count is. Members that fall off the surface are dropped."""
    P,T,area,normals,vn=surface
    centres,cn,_=surface_points(P,T,area,normals,vn,count,seed,smooth,0.0,180.0,0.0,0.0)
    if not len(centres):return np.zeros((0,3)),np.zeros((0,3)),np.zeros(0,dtype=np.int64),np.zeros(0,dtype=np.int64)
    members,rf=cluster_shape(len(centres),per,jitter,seed);pos=[];nrm=[];ids=[];cl=[];total=0
    for c in range(len(centres)):
        m=int(min(members[c],max(CLUSTER_MAX_POINTS-total,0)))
        if m<=0:break
        mid=c*CLUSTER_ID_STRIDE+np.arange(m);r=radius*rf[c];dist,ang=member_offsets(mid,r,falloff,seed);u,v=tangent_frame(cn[c])
        cand=centres[c]+np.outer(dist*np.cos(ang),u)+np.outer(dist*np.sin(ang),v)
        project=make_projector((P,T,area,normals,vn),centres[c],r,smooth);p,n,ok=project(cand,cn[c])
        pos.append(p[ok]);nrm.append(n[ok]);ids.append(mid[ok]);cl.append(np.full(int(ok.sum()),c));total+=int(ok.sum())
    return np.vstack(pos),np.vstack(nrm),np.concatenate(ids),np.concatenate(cl)

# ---------------------------------------------------------------- Houdini side
import hou

def cluster_regions(surface,count,per,radius,jitter,seed,smooth=True):
    """The centre (m,3) and the radius (m,) of every cluster, the same numbers cluster_points used: the Falloff fades every cluster to its own boundary (v1.13.0)."""
    P,T,area,normals,vn=surface;centres,cn,_=surface_points(P,T,area,normals,vn,count,seed,smooth,0.0,180.0,0.0,0.0)
    if not len(centres):return np.zeros((0,3)),np.zeros(0)
    members,rf=cluster_shape(len(centres),per,jitter,seed);return centres,radius*rf

def cluster_surface(asset):
    if asset.evalParm('cluster_prim').strip():return stage_surface(asset,'cluster_prim')
    hx,hz=(v*0.5 for v in asset.evalParmTuple('cluster_area'));return plane_rect(hx,hz,0.0)

def sop_cluster(geo,asset):
    """generate_cluster: the cluster members with the normal alignment in p@align and the cluster number in i@cluster."""
    pos,nrm,ids,cl=cluster_points(cluster_surface(asset),asset.evalParm('cluster_count'),asset.evalParm('cluster_per'),asset.evalParm('cluster_radius'),asset.evalParm('cluster_falloff'),asset.evalParm('cluster_jitter'),asset.evalParm('cluster_seed'),asset.evalParm('cluster_normal')==1)
    pos=pos+nrm*asset.evalParm('cluster_offset');geo.clear();geo.addAttrib(hou.attribType.Point,'id',0);geo.addAttrib(hou.attribType.Point,'align',(0.0,0.0,0.0,1.0));geo.addAttrib(hou.attribType.Point,'cluster',0)
    geo.addAttrib(hou.attribType.Point,'ccentre',(0.0,0.0,0.0));geo.addAttrib(hou.attribType.Point,'cradius',1.0)                      # the cluster the member belongs to: its centre and radius (the Falloff fades to this boundary)
    if not len(pos):return
    geo.createPoints([tuple(v) for v in pos.tolist()]);geo.setPointIntAttribValues('id',ids.tolist());geo.setPointIntAttribValues('cluster',cl.tolist())
    geo.setPointFloatAttribValues('align',normal_alignment(nrm,asset.evalParm('cluster_align')).ravel().tolist())
    centres,radii=cluster_regions(cluster_surface(asset),asset.evalParm('cluster_count'),asset.evalParm('cluster_per'),asset.evalParm('cluster_radius'),asset.evalParm('cluster_jitter'),asset.evalParm('cluster_seed'),asset.evalParm('cluster_normal')==1)
    geo.setPointFloatAttribValues('ccentre',centres[cl].ravel().tolist());geo.setPointFloatAttribValues('cradius',radii[cl].tolist())

def cluster_info(asset):
    try:
        pos,nrm,ids,cl=cluster_points(cluster_surface(asset),asset.evalParm('cluster_count'),asset.evalParm('cluster_per'),asset.evalParm('cluster_radius'),asset.evalParm('cluster_falloff'),asset.evalParm('cluster_jitter'),asset.evalParm('cluster_seed'),asset.evalParm('cluster_normal')==1)
    except hou.Error as exc:return 'Cannot read the surface: %s'%exc
    return '%d clusters, %d instances (about %d per cluster).'%(len(np.unique(cl)),len(ids),round(len(ids)/max(len(np.unique(cl)),1)))
