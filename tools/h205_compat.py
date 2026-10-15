"""Houdini 20.5 / 21 helper for the test and build scripts (imported by versions.py when hython is older than 22).

Problem: in Houdini 20.5 and 21, once an HDA whose DialogScript has `bindhandle ... lopxform ...` lines has been unloaded (hou.hipFile.clear, hou.hipFile.load,
uninstallFile) it can never be installed again in the same process: the stale handle bindings make the DialogScript fail ("error binding handle lopxform because its
bindings already exist") and the node type comes back with no parameters at all. Houdini 22 does not have the problem. The suites clear the scene and install the HDA
many times, so installFile here installs a copy without the bindhandle lines (cached in the temp folder) in every suite (scripts named validate_*) and from the second
installation of a type on in any other script. Only the viewport gizmo differs; the shipped HDA is untouched and tests/validate_h205.py installs the real file in a clean session. Artists load the HDA once at startup (package), where this does not arise."""
import hashlib, os, re, shutil, sys, tempfile
import hou
_seen=set()
ALWAYS=os.path.basename(sys.argv[0]).startswith('validate_')          # the suites save and reload HIPs, which unloads the HDA: they always install the copy without bindings
_original=hou.hda.installFile
def _type_names(path):
    return [d.nodeTypeNameWithCategory() if hasattr(d,'nodeTypeNameWithCategory') else d.nodeTypeName() for d in hou.hda.definitionsInFile(path)]
def stripped_copy(path):
    """Path of a copy of the HDA file without bindhandle lines in the DialogScript of its definitions."""
    stamp=hashlib.md5(('%s|%s|%s'%(os.path.abspath(path),os.path.getmtime(path),os.path.getsize(path))).encode()).hexdigest()[:12]
    out=os.path.join(tempfile.gettempdir(),'arraytron_nobind',stamp+'_'+os.path.basename(path))
    if os.path.isfile(out):return out
    os.makedirs(os.path.dirname(out),exist_ok=True)
    folder=out+'_dir'
    if os.path.isdir(folder):shutil.rmtree(folder)
    hou.hda.expandToDirectory(path,folder)
    for root,_dirs,files in os.walk(folder):
        for name in files:
            if name=='DialogScript':
                full=os.path.join(root,name);text=open(full,encoding='utf8').read()
                open(full,'w',encoding='utf8',newline='').write(re.sub(r'^[ \t]*bindhandle .*\r?\n','',text,flags=re.M))
    hou.hda.collapseFromDirectory(out,folder);shutil.rmtree(folder)
    return out
def install_file(path,*args,**kwargs):
    key=tuple(sorted(_type_names(str(path))))
    if key in _seen or ALWAYS:path=stripped_copy(str(path))
    result=_original(str(path),*args,**kwargs)
    _seen.add(key)
    return result
def patch():
    hou.hda.installFile=install_file
