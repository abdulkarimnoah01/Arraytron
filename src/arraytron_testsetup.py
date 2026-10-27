# Test setup (v1.25.0): a new Arraytron node made in the interface starts as a working test: a built-in sphere (a USD file inside the HDA, section builtin_sphere.usda) scattered on a built-in
# ground plane (section builtin_ground.usda, switched on by Built-in Test Ground, Surface mode), so it shows something before real prototypes and surfaces are plugged in. The hook acts only on a node with nothing wired in whose prototype and mode are still at their defaults; hython and scripts that
# create nodes are not touched (the hook runs only when the interface is available). v1.25.1: the check looks at those settings only (not at every parameter), the button Start From Test Setup
# does it on request, and the hook says why it skipped. Appended to the PythonModule.
BUILTIN_SPHERE='builtin_sphere.usda'
TEST_KEYS=('mode','protos','proto_type1','proto_prim1')
TEST_GROUND_PRIM='/World/TestGround'

def builtin_sphere_path(node):
    """The USD path of the sphere that lives in the HDA: opdef:/<node type>?builtin_sphere.usda"""
    return 'opdef:/%s?%s'%(node.type().nameWithCategory(),BUILTIN_SPHERE)

def test_setup(node,force=False):
    """Make a node a test run: Prototype 1 is the built-in sphere, the Distribution Mode is Surface on the built-in test ground plane (30 spheres). Without force it acts only on a node that is new: nothing wired in and the mode and Prototype 1 at their
    defaults. Returns True when it did, False when not."""
    if node.parm('proto_type1') is None:return False
    if not force and (any(node.inputs()) or not all(node.parm(k).isAtDefault() for k in TEST_KEYS)):return False
    if node.evalParm('protos')<1:node.parm('protos').set(1)
    node.parm('proto_type1').set(2);node.parm('proto_file1').set(builtin_sphere_path(node));node.parm('proto_fileprim1').set('')
    if node.parm('copy_test_ground') is not None:node.parm('copy_test_ground').set(1)
    node.parm('surface_prim').set(TEST_GROUND_PRIM);node.parm('surface_countmode').set(0);node.parm('surface_count').set(30);node.parm('mode').set(5)
    return True

def test_setup_button(node):
    """The Start From Test Setup button: the built-in sphere on the built-in ground plane, whatever the node was. Undoable."""
    with hou.undos.group('Arraytron test setup'):test_setup(node,True)
