# Embedded in the Arraytron HDA as its PythonModule (node.hdaModule()). Pure bookkeeping for the Prototype Bank:
# it turns the bank rows into prototype prim paths. The Source Resolver LOP, the PointInstancer's prototype pattern
# and the read-only summary all call these functions, so they cannot disagree. No point generation happens here.
import re
import hou
from pxr import Sdf, Usd, UsdGeom

SOP_SLOTS=4                      # sopimport stagers pre-built in the HDA
TYPE_STREAM,TYPE_INPUT,TYPE_FILE,TYPE_SOP,TYPE_GROUP=range(5)
TYPE_NAMES=('Prim Path','Input Connection','USD File','SOP Geometry','Group Children')      # v1.29.0: Group Children (a row that stands for every child prim of a group)

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

def stream_stage(asset):
    """The stage the Prototype Bank looks into: everything that reaches the Source Resolver (the main input, the merged Prototype Inputs, the staged SOPs)."""
    node=asset.node('SOURCE_RESOLVER');inputs=node.inputs() if node is not None else ()
    stage=inputs[0].stage() if inputs and inputs[0] is not None else None
    if stage is None:raise hou.NodeError('The incoming stage is not available.')
    return stage

def group_children(asset,row,text):
    """The child prims a Group Children row stands for, in stage order: the prim path `text` is a group (/Group, or /Group/*) or a group with a name pattern (/Group/rock*, with * and ? as wildcards). Only active
    prims that can be drawn (Imageable) count; a child that holds the Output Prim of this node, or is it, is skipped (the scatter must not instance itself)."""
    import fnmatch
    text=text.strip().rstrip('/')
    if not text:raise hou.NodeError('Prototype %d: Prim Path is empty.'%row)
    parent,_,last=text.rpartition('/')
    if not any(c in last for c in '*?['):parent,last=text,'*'
    stage=stream_stage(asset);group=stage.GetPrimAtPath(parent or '/')
    if not group:raise hou.NodeError('Prototype %d: the group %s does not exist in the incoming stage.'%(row,parent or '/'))
    dest=Sdf.Path(asset.evalParm('outputpath'));out=[]
    for child in group.GetChildren():
        path=child.GetPath()
        if not fnmatch.fnmatchcase(child.GetName(),last) or not child.IsActive() or not child.IsA(UsdGeom.Imageable) or dest==path or dest.HasPrefix(path) or child.GetName()=='HoudiniLayerInfo':continue
        out.append(path.pathString)
    if not out:raise hou.NodeError('Prototype %d: no active prim under %s matches %s.'%(row,group.GetPath(),last))
    return out

def resolve(asset):
    """Resolve every enabled bank row to a prototype prim path. Raises hou.NodeError with the row number on bad setup. A Group Children row (v1.29.0) gives one entry per child prim of its group, all with the row
    number of that row (so its Weight, Scale, Rotation ... apply to each child) and group=True."""
    entries=[]
    for r in bank_rows(asset):
        t=asset.evalParm('proto_type%d'%r)
        e=dict(row=r,type=t,file='',fileprim='')
        if t==TYPE_GROUP:
            for k,path in enumerate(group_children(asset,r,asset.evalParm('proto_prim%d'%r))):
                entries.append(dict(row=r,type=t,file='',fileprim='',path=path,group=True,child=k))
            continue
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

SCATTER_TEXT={}                                   # node path -> the last text of scatter_info

def scatter_info(asset):
    """Read-only text of the Scattered counter (Layout tab): how many instances the node makes, how many points were generated before Mask / Falloff / Thin / Separation / Avoid removed some, and how many
    use each prototype. It never cooks anything (it is evaluated whenever the node is selected): while the points are out of date it shows the last count, marked as old."""
    key=asset.path()
    try:
        out=asset.node('USD_COMPILER/OUT_POINTS');gen=asset.node('USD_COMPILER/DISTRIBUTION_GENERATOR')
        if out is None or gen is None:return 'The node is not built.'
        if out.needsToCook() or gen.needsToCook():
            last=SCATTER_TEXT.get(key);return (last+'\n(old: the node has changed, the count updates when it cooks)') if last else 'Not cooked yet: the count appears after the first cook.'
        og=out.geometry();gg=gen.geometry()
        if og is None or gg is None:return SCATTER_TEXT.get(key,'No points: see the error on the node.')
        final=int(og.intrinsicValue('pointcount'));made=int(gg.intrinsicValue('pointcount'))
        text='%s instances'%format(final,',')
        ask=globals().get('SURFACE_REQUEST',{}).get(key) if asset.evalParm('mode')==5 else None                                  # Surface mode: a limit cut the number
        if ask and ask[0]>ask[1] and ask[1]==final:text+=' - LIMITED: the settings ask for %s, the Point Limit is %s'%(format(ask[0],','),format(ask[1],','))
        if made!=final:text+=' (%s generated, %s removed by Mask, Falloff, Thin, Separation or Avoid)'%(format(made,','),format(made-final,','))
        if final and og.findPointAttrib('protoindex') is not None:
            counts=np.bincount(np.array(og.pointIntAttribValues('protoindex'),dtype=np.int64));names=[]
            try:names=[e['path'].rstrip('/').split('/')[-1] for e in resolve(asset)]
            except Exception:pass
            parts=['%s %s'%(names[i] if i<len(names) else 'prototype %d'%i,format(int(c),',')) for i,c in enumerate(counts) if c]
            if len(parts)>1:text+='\n'+',  '.join(parts[:8])+(' ...' if len(parts)>8 else '')
    except Exception as exc:
        return SCATTER_TEXT.get(key,'Cannot count: %s'%exc)
    SCATTER_TEXT[key]=text;return text

def summary(asset):
    """Read-only text for the Prototype Bank: what each enabled row resolved to."""
    try:entries=resolve(asset)
    except hou.NodeError as exc:return 'Cannot resolve the bank: %s'%exc.instanceMessage() if hasattr(exc,'instanceMessage') else str(exc)
    except Exception as exc:return 'Cannot resolve the bank: %s'%exc
    lines=[]
    for ordinal,e in enumerate(entries):
        label=TYPE_NAMES[e['type']]
        if e['type']==TYPE_INPUT:label+=' (Input %d)'%(asset.evalParm('proto_input%d'%e['row'])+2)
        if e.get('group'):label+=' (child %d)'%(e['child']+1)
        lines.append('%d  [row %d] %s  %s  (weight %g)'%(ordinal,e['row'],label,e['path'],asset.evalParm('proto_weight%d'%e['row'])))
        if 'lod_entries' in globals():
            for row,level,path in lod_entries(asset):
                if row==e['row']:lines.append('      %s  %s'%(LOD_LEVELS[level-1],path))
    return '\n'.join(lines)
