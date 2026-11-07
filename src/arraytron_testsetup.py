# Test setup (v1.25.0): a new Arraytron node made in the interface starts as a working test: a built-in sphere (a USD file inside the HDA, section builtin_sphere.usda) scattered on a built-in
# ground plane (section builtin_ground.usda, switched on by Built-in Test Ground, Surface mode), so it shows something before real prototypes and surfaces are plugged in. The hook acts only on a node with nothing wired in whose prototype and mode are still at their defaults; hython and scripts that
# create nodes are not touched (the hook runs only when the interface is available). v1.25.1: the check looks at those settings only (not at every parameter), the button Start From Test Setup
# does it on request, and the hook says why it skipped. v1.25.2: the plane is left out as soon as Surface Prim points at an external surface (src/test_ground.py), and wiring an input
# into a node that still uses the plane switches it off (test_ground_input_changed, the OnInputChanged handler). Appended to the PythonModule.
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

def stamp_setup(node):
    """Arraytron Stamp (OnCreated, interface only): a new Stamp node gets the built-in sphere as Prototype 1 and is in Instance Place mode, so Start Placing works at once. Acts only on a new node (nothing wired in, Prototype 1 at its default). Returns True when it did."""
    if node.parm('proto_type1') is None or any(node.inputs()) or not node.parm('proto_type1').isAtDefault():return False
    if node.evalParm('protos')<1:node.parm('protos').set(1)
    node.parm('proto_type1').set(2);node.parm('proto_file1').set(builtin_sphere_path(node));node.parm('proto_fileprim1').set('');node.parm('mode').set(9)
    return True

def test_ground_input_changed(node):
    """OnInputChanged (v1.25.2): an external source was wired into a node that still scatters on the built-in test ground: switch the ground off and point Surface Prim back at its default
    (/World/Terrain) so the plane does not lie under the real surface. A node whose Surface Prim already points elsewhere is left alone (the ground script leaves the plane out by itself). Returns True when it changed the node."""
    if node.parm('copy_test_ground') is None or node.parm('surface_prim') is None or not node.evalParm('copy_test_ground') or not any(node.inputs()):return False
    path=node.evalParm('surface_prim').strip().rstrip('/')
    if path!=TEST_GROUND_PRIM and not path.startswith(TEST_GROUND_PRIM+'/'):return False
    node.parm('copy_test_ground').set(0);node.parm('surface_prim').set(node.parm('surface_prim').parmTemplate().defaultValue()[0])
    return True

def test_setup_button(node):
    """The Start From Test Setup button: the built-in sphere on the built-in ground plane, whatever the node was. Undoable."""
    with hou.undos.group('Arraytron test setup'):test_setup(node,True)
