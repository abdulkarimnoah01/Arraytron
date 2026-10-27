# Embedded in a Python LOP (TEST_GROUND) inside the Arraytron HDA, a source of the merge in front of everything. With Built-in Test Ground (v1.25.1) it adds a flat 10 x 10 ground plane,
# /World/TestGround/Plane (100 quads, normal up), to the stream, so Surface mode has something to scatter on before a real surface is plugged in. Off: it adds nothing.
import hou
from pxr import Gf, UsdGeom, Vt
node=hou.pwd()
asset=node.parent()
stage=node.editableStage()
switch=asset.parm('copy_test_ground')
if switch is not None and switch.eval():
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
