# Houdini 20.5 / 21 support: appended to the PythonModule only in the otls_h205 build (see docs/PORT_HOUDINI_205.md).
# Houdini 22 has the pointinstancer LOP, which keeps the prototype order and puts them at <output>/Prototypes/<name>. Houdini 20.5 / 21 only
# have the older instancer LOP, which sorts the prototype list and mirrors the full source path. The build therefore feeds the instancer a
# second stage whose top-level prims (flat_paths) specialize the bank prims, picks the prototype per point by that path (point attribute
# protopath, set by sop_protopath), and a Python LOP (proto_normalize.py) puts the targets back in bank order, so the USD result has the
# same prototype paths and the same protoIndices as the Houdini 22 build. Everything else in the module is shared.
def flat_paths(asset):
    """Top-level prim path of every prototype of pattern(asset) (bank order, then LOD / proxy prims): the name Houdini 22 gives the copy,
    '/Rock' and '/Rock2' for two sources called Rock. A source that already sits at the top level keeps its own path."""
    sources=pattern(asset).split()
    taken={s.lstrip('/') for s in sources if s.count('/')==1}
    out=[]
    for s in sources:
        if s.count('/')==1:out.append(s);continue
        leaf=s.rsplit('/',1)[1];name=leaf;k=2
        while name in taken:name='%s%d'%(leaf,k);k+=1
        taken.add(name);out.append('/'+name)
    return out

def sop_protopath(geo,asset):
    """PROTO_PATH: the instancer picks each point's prototype by the string attribute protopath = the flat path of prototype protoindex."""
    paths=flat_paths(asset);n=len(paths)
    geo.addAttrib(hou.attribType.Point,'protopath','')
    if geo.findPointAttrib('protoindex') is None or not geo.points():return
    idx=geo.pointIntAttribValues('protoindex')
    geo.setPointStringAttribValues('protopath',[paths[min(max(int(i),0),n-1)] for i in idx])
