# Embedded in a Python LOP (TEST_GROUND) inside the Arraytron HDA, a source of the merge in front of everything. With Built-in Test Ground (v1.25.1) it adds a flat 10 x 10 ground plane,
# /World/TestGround/Plane (100 quads, normal up), to the stream, so Surface mode has something to scatter on before a real surface is plugged in. Off: it adds nothing.
# v1.25.2: it also adds nothing once Surface Prim points at another prim (an external source), so the plane never overlaps a real surface.
import hou
from pxr import Gf, UsdGeom, Vt
node=hou.pwd()
asset=node.parent()
stage=node.editableStage()
GROUND_AUTO=True                                                   # v1.25.2: set by the builder; False keeps the older rule (the ground is added whenever the switch is on)
GROUND_PRIM='/World/TestGround'
switch=asset.parm('copy_test_ground')
def ground_in_use():
    """v1.25.2: the plane is only added while Surface Prim still points at it; an external surface (any other prim) leaves the plane out of the stream."""
    surface=asset.parm('surface_prim')
    if not GROUND_AUTO or surface is None:return True
    path=surface.eval().strip().rstrip('/')
    return path==GROUND_PRIM or path.startswith(GROUND_PRIM+'/')
if switch is not None and switch.eval() and ground_in_use():
    UsdGeom.Xform.Define(stage,'/World/TestGround')
    mesh=UsdGeom.Mesh.Define(stage,'/World/TestGround/Plane')
    points=[Gf.Vec3f(x-5.0,0.0,z-5.0) for z in range(11) for x in range(11)]
    indices=[]
    for z in range(10):
        for x in range(10):
            indices+=[z*11+x,(z+1)*11+x,(z+1)*11+x+1,z*11+x+1]                    # counter clockwise seen from +Y: the normal points up
    mesh.CreatePointsAttr(Vt.Vec3fArray(points))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4]*100))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(indices))
    mesh.CreateSubdivisionSchemeAttr('none')
    mesh.CreateDisplayColorAttr([Gf.Vec3f(0.42,0.5,0.4)])
