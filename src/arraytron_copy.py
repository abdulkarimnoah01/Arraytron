# Copy settings (v1.23.0): copy the parameters of one Arraytron node onto another (any versions), from code or with the Import Settings button (Prototypes tab, Copy Settings). The parameters are
# matched by name; a parameter the other node does not have is reported, never an error. Multiparm counters (the Prototype Bank, the override table ...) are set first so their rows exist.
# A node of the first releases has one Prototype parameter instead of the bank: it becomes row 1 of the bank. Appended to the PythonModule; the functions need no other module.
COPY_ALIASES=(('prototype','proto_prim1','protos'),)           # (name in the old node, name in the new one, the counter that must be at least 1)
COPY_OWN=('copy_source','copy_info')                           # this section is not a setting
COPY_MULTIPARMS=(hou.folderType.MultiparmBlock,hou.folderType.ScrollingMultiparmBlock,hou.folderType.TabbedMultiparmBlock)
COPY_TYPES=(hou.parmTemplateType.Int,hou.parmTemplateType.Float,hou.parmTemplateType.String,hou.parmTemplateType.Toggle,hou.parmTemplateType.Menu,hou.parmTemplateType.Ramp)

def copy_is_setting(parm):
    """True for a parameter that holds a setting: not a button, label, folder, this section, or a read-out (those have a default expression)."""
    t=parm.parmTemplate()
    if t.type() not in COPY_TYPES or parm.name() in COPY_OWN or parm.name().startswith('tab_'):return False
    if t.type() in (hou.parmTemplateType.Int,hou.parmTemplateType.Float,hou.parmTemplateType.String) and any(t.defaultExpression()):return False
    return True

def copy_counters(node):
    """The names of the multiparm counters of a node (Prototype Bank, override table ...)."""
    names=[]
    def walk(templates):
        for t in templates:
            if t.type()==hou.parmTemplateType.Folder:
                if t.folderType() in COPY_MULTIPARMS:names.append(t.name())
                walk(t.parmTemplates())
    walk(node.parmTemplateGroup().entries());return names

def copy_set(dst_parm,src_parm,report):
    """One parameter: animation (keyframes) or the value; a toggle that became a slider keeps its 0 / 1 as 0 / 0.5 only for the old Stagger tick."""
    name=dst_parm.name()
    try:
        keys=src_parm.keyframes()
        if keys:
            dst_parm.deleteAllKeyframes()
            for k in keys:dst_parm.setKeyframe(k)
        elif src_parm.parmTemplate().type()==hou.parmTemplateType.Ramp:dst_parm.set(src_parm.evalAsRamp())
        else:
            value=src_parm.eval()
            if src_parm.parmTemplate().type()==hou.parmTemplateType.Toggle and dst_parm.parmTemplate().type()==hou.parmTemplateType.Float:value=0.5*float(value)     # the Stagger Rows tick of v1.17.0 and older
            dst_parm.set(value)
        report['copied'].append(name)
    except hou.Error as exc:report['failed'].append((name,str(exc).strip().splitlines()[0] if str(exc).strip() else 'cannot set'))

def copy_settings(dst,src,only_changed=False):
    """Copy the settings of the Arraytron node src onto the Arraytron node dst (nodes or paths). only_changed copies just the parameters that are not at their default on src.
    Returns {'copied': [names], 'missing': [names dst does not have], 'failed': [(name, reason)]}. Undoable as one step."""
    dst=hou.node(dst) if isinstance(dst,str) else dst;src=hou.node(src) if isinstance(src,str) else src
    if dst is None or src is None:raise hou.OperationFailed('Copy settings: node not found')
    if dst==src:raise hou.OperationFailed('Copy settings: the source is the node itself')
    report={'copied':[],'missing':[],'failed':[]}
    with hou.undos.group('Arraytron copy settings'):
        for name in copy_counters(src):
            sp,dp=src.parm(name),dst.parm(name)
            if sp is None:continue
            if dp is None:report['missing'].append(name)
            else:dp.set(sp.eval());report['copied'].append(name)
        renamed=set()
        for old,new,counter in COPY_ALIASES:
            sp=src.parm(old)
            if sp is None or src.parm(new) is not None:continue
            renamed.add(old);cp=dst.parm(counter)
            if cp is not None and cp.eval()<1:cp.set(1)
            dp=dst.parm(new)
            if dp is None:report['missing'].append(old)
            else:dp.set(sp.eval());report['copied'].append(old+' > '+new)
        for sp in src.parms():
            if not copy_is_setting(sp) or (only_changed and sp.isAtDefault() and not sp.keyframes()):continue
            if sp.name() in renamed:continue
            dp=dst.parm(sp.name())
            if dp is None or not copy_is_setting(dp):report['missing'].append(sp.name());continue
            copy_set(dp,sp,report)
    return report

def copy_version(node):
    """The version of an Arraytron node as a tuple: arraytron::instancer::1.22.0 is (1, 22, 0); 0.15 is (0, 15)."""
    match=re.search(r'::(\d+(?:\.\d+)*)\Z',node.type().name());return tuple(int(x) for x in match.group(1).split('.')) if match else (0,)

def copy_find_source(node):
    """The Arraytron node to import from: the Source Node parameter when set, else another Arraytron node in the same network, preferring one wired to the same input, then the one with the most changed parameters (a node still at its defaults has nothing to import), then the newest version, then the name."""
    path=node.evalParm('copy_source') if node.parm('copy_source') is not None else ''
    if path:
        src=node.node(path)
        if src is None:raise hou.OperationFailed('Import Settings: %s does not exist'%path)
        return src
    others=[n for n in node.parent().children() if n!=node and n.type().name().startswith('arraytron::instancer')]
    if not others:raise hou.OperationFailed('Import Settings: there is no other Arraytron node in %s. Set Source Node.'%node.parent().path())
    wired=node.inputs()[0] if node.inputs() else None
    return sorted(others,key=lambda n:(not (wired is not None and n.inputs() and n.inputs()[0]==wired),-sum(1 for p in n.parms() if not p.isAtDefault()),tuple(-x for x in copy_version(n)),n.name()))[0]

def copy_text(src,report):
    text='Imported from %s (%s): %d settings copied'%(src.path(),src.type().name().split('::')[-1],len(report['copied']))
    if report['missing']:text+='; no counterpart on this node: '+', '.join(report['missing'][:12])+(' ...' if len(report['missing'])>12 else '')
    if report['failed']:text+='; failed: '+', '.join('%s (%s)'%f for f in report['failed'][:6])
    return text+'.'

def import_settings(node,source=None):
    """The Import Settings button: copy the settings of the Source Node (or the automatically found Arraytron node) onto this node and write what happened into the read-out. Returns the report."""
    node=hou.node(node) if isinstance(node,str) else node
    src=hou.node(source) if isinstance(source,str) else (source or copy_find_source(node))
    report=copy_settings(node,src);text=copy_text(src,report)
    if node.parm('copy_info') is not None:node.parm('copy_info').set(text)
    if hou.isUIAvailable():hou.ui.setStatusMessage(text)
    return report
