# Test setup (v1.25.0): a new Arraytron node made in the interface starts as a working test: a built-in sphere (a USD file inside the HDA, section builtin_sphere.usda) scattered on a Grid, so it
# shows something before real prototypes and surfaces are plugged in. Only for a node with nothing wired in that is still at its defaults; hython and scripts that create nodes are not touched
# (the hook runs only when the interface is available). Appended to the PythonModule.
BUILTIN_SPHERE='builtin_sphere.usda'

def builtin_sphere_path(node):
    """The USD path of the sphere that lives in the HDA: opdef:/<node type>?builtin_sphere.usda"""
    return 'opdef:/%s?%s'%(node.type().nameWithCategory(),BUILTIN_SPHERE)

def test_setup(node):
    """Make a new node a test run: Prototype 1 is the built-in sphere, the Distribution Mode is Grid. Returns True when it did, False when the node is not new (something is wired in, or a setting was changed)."""
    if node.parm('proto_type1') is None or any(node.inputs()):return False
    if not all(p.isAtDefault() for p in node.parms() if p.name() not in ('copy_info',) and not p.name().startswith('viz_ramp')):return False          # the points of the Custom Gradient ramp are not at a default
    node.parm('proto_type1').set(2);node.parm('proto_file1').set(builtin_sphere_path(node));node.parm('proto_fileprim1').set('');node.parm('mode').set(2)
    return True
