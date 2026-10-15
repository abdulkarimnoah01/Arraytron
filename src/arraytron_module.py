# Embedded in the Arraytron HDA as its PythonModule (node.hdaModule()). Pure bookkeeping for the Prototype Bank:
# it turns the bank rows into prototype prim paths. The Source Resolver LOP, the PointInstancer's prototype pattern
# and the read-only summary all call these functions, so they cannot disagree. No point generation happens here.
import re
import hou
from pxr import Sdf, Usd, UsdGeom

SOP_SLOTS=4                      # sopimport stagers pre-built in the HDA
TYPE_STREAM,TYPE_INPUT,TYPE_FILE,TYPE_SOP=range(4)
TYPE_NAMES=('Prim Path','Input Connection','USD File','SOP Geometry')

def bank_rows(asset):
    """1-based multiparm row numbers of the enabled prototype entries, in bank order."""
    return [r for r in range(1,asset.evalParm('protos')+1) if asset.evalParm('proto_on%d'%r)]

def sources_root(asset):
    return asset.evalParm('outputpath').rstrip('/')+'_Sources'

def clean(name):
    return re.sub(r'\W+','_',name).strip('_') or 'proto'

def sop_rows(asset):
    return [r for r in bank_rows(asset) if asset.evalParm('proto_type%d'%r)==TYPE_SOP]

def sop_slot(asset,k):
    """(row, SOP path) for the k-th (0-based) enabled SOP Geometry entry, or (0, '') if there is none."""
    rows=sop_rows(asset)
    if k<len(rows):return rows[k],asset.evalParm('proto_sop%d'%rows[k])
    return 0,''

def staged_path(asset,row):
    """Prim path a File or SOP entry is staged at (hidden, outside the output prim)."""
    t=asset.evalParm('proto_type%d'%row)
    if t==TYPE_FILE:
        leaf=clean(re.split(r'[\\/]',asset.evalParm('proto_file%d'%row))[-1].rsplit('.',1)[0])
    else:
        leaf=clean(asset.evalParm('proto_sop%d'%row).rstrip('/').split('/')[-1])
    return '%s/Proto_%02d_%s'%(sources_root(asset),row,leaf)

def auto_prim(stage):
    """The prim to instance when an Input Connection gives no explicit Prim Path: descend from the only top-level prim
    through single-child chains until a component/assembly or a gprim, or a group with several children."""
    tops=[p for p in stage.GetPseudoRoot().GetChildren() if p.GetName()!='HoudiniLayerInfo']
    if not tops:raise hou.NodeError('The connected input has no primitives.')
    if len(tops)>1:raise hou.NodeError('The connected input has several top-level primitives ('+', '.join(p.GetName() for p in tops[:4])+'): type the Prim Path.')
    cur=tops[0]
    while True:
        if Usd.ModelAPI(cur).GetKind() in ('component','assembly') or cur.IsA(UsdGeom.Gprim):return cur
        kids=cur.GetChildren()
        if len(kids)!=1:return cur
        cur=kids[0]

def input_stage(asset,row):
    index=asset.evalParm('proto_input%d'%row)+1          # menu 0..2 = Input 2..4 = HDA input index 1..3 (0 is the main stream)
    inputs=asset.inputs()
    node=inputs[index] if index<len(inputs) else None
    if node is None:raise hou.NodeError('Prototype %d uses Input %d, which is not connected.'%(row,index+1))
    stage=node.stage()
    if stage is None:raise hou.NodeError('Prototype %d: Input %d has no stage.'%(row,index+1))
    return stage

def resolve(asset):
    """Resolve every enabled bank row to a prototype prim path. Raises hou.NodeError with the row number on bad setup."""
    entries=[]
    for r in bank_rows(asset):
        t=asset.evalParm('proto_type%d'%r)
        e=dict(row=r,type=t,file='',fileprim='')
        if t==TYPE_STREAM:
            e['path']=asset.evalParm('proto_prim%d'%r).strip()
            if not e['path']:raise hou.NodeError('Prototype %d: Prim Path is empty.'%r)
        elif t==TYPE_INPUT:
            stage=input_stage(asset,r)
            typed=asset.evalParm('proto_inprim%d'%r).strip()
            if typed:
                prim=stage.GetPrimAtPath(typed)
                if not prim:raise hou.NodeError('Prototype %d: %s does not exist in Input %d.'%(r,typed,asset.evalParm('proto_input%d'%r)+2))
            else:
                try:prim=auto_prim(stage)
                except hou.NodeError as exc:raise hou.NodeError('Prototype %d: %s'%(r,exc.instanceMessage() if hasattr(exc,'instanceMessage') else exc))
            e['path']=prim.GetPath().pathString
        elif t==TYPE_FILE:
            e['file']=asset.evalParm('proto_file%d'%r).strip();e['fileprim']=asset.evalParm('proto_fileprim%d'%r).strip()
            if not e['file']:raise hou.NodeError('Prototype %d: USD File is empty.'%r)
            e['path']=staged_path(asset,r)
        else:
            if not asset.evalParm('proto_sop%d'%r).strip():raise hou.NodeError('Prototype %d: SOP Path is empty.'%r)
            if r not in sop_rows(asset)[:SOP_SLOTS]:raise hou.NodeError('Prototype %d: at most %d SOP Geometry entries are supported.'%(r,SOP_SLOTS))
            e['path']=staged_path(asset,r)
        entries.append(e)
    if not entries:raise hou.NodeError('The Prototype Bank has no enabled prototypes.')
    seen={}
    for e in entries:
        if e['path'] in seen:raise hou.NodeError('Prototypes %d and %d resolve to the same prim %s: change the source of one of them, or disable it.'%(seen[e['path']],e['row'],e['path']))
        seen[e['path']]=e['row']
    return entries

def pattern(asset):
    """Space separated prototype prim paths in bank order: the PointInstancer's prototype pattern. LOD / Proxy prims (v0.9.0) follow the heroes."""
    entries=resolve(asset);paths=[e['path'] for e in entries]
    if 'lod_entries' in globals():
        check_lod_paths(asset,entries);paths+=lod_pattern_extra(asset)
    return ' '.join(paths)

def summary(asset):
    """Read-only text for the Prototype Bank: what each enabled row resolved to."""
    try:entries=resolve(asset)
    except hou.NodeError as exc:return 'Cannot resolve the bank: %s'%exc.instanceMessage() if hasattr(exc,'instanceMessage') else str(exc)
    except Exception as exc:return 'Cannot resolve the bank: %s'%exc
    lines=[]
    for ordinal,e in enumerate(entries):
        label=TYPE_NAMES[e['type']]
        if e['type']==TYPE_INPUT:label+=' (Input %d)'%(asset.evalParm('proto_input%d'%e['row'])+2)
        lines.append('%d  [row %d] %s  %s  (weight %g)'%(ordinal,e['row'],label,e['path'],asset.evalParm('proto_weight%d'%e['row'])))
        if 'lod_entries' in globals():
            for row,level,path in lod_entries(asset):
                if row==e['row']:lines.append('      %s  %s'%(LOD_LEVELS[level-1],path))
    return '\n'.join(lines)
