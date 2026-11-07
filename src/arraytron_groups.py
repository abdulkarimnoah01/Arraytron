
# ---- Group Children prototypes (src/arraytron_groups.py): a Prototype Bank row whose Source Type is Group Children stands for every child prim of a group (Prim Path /Group/* or /Group), one prototype per child.
# resolve() (arraytron_module.py) expands the row into one entry per child, all carrying the row number, so the Weight, Scale, Scale Random and Rotation of the row apply to each child and the PointInstancer gets one
# prototype per child. The prototype assignment (vex_v1290) works through the entries, not through the rows: this Python SOP tells it which bank row every prototype belongs to (the detail array pe_row, one
# number per entry in prototype order). A Group Children row has no LOD prims of its own; a Biome mix, Instance Place and Overrides that name the row take its first child.
def sop_proto_expand(geo, asset):
    """PROTO_EXPAND: write the detail integer array pe_row = the bank row of every prototype entry, in prototype order (empty when the bank cannot be resolved: the Source Resolver reports why)."""
    geo.addArrayAttrib(hou.attribType.Global, 'pe_row', hou.attribData.Int, 1)
    try:
        rows = [int(e['row']) for e in resolve(asset)]
    except hou.NodeError:
        rows = []
    geo.setGlobalAttribValue('pe_row', rows)
