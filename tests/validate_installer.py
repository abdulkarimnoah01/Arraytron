"""Installer validation: python tests/validate_installer.py <unpacked Release folder>   (plain Python; it starts PowerShell and hython itself)
Runs the real installer of a release package in a sandbox (a temporary Documents folder and install root, never your own), then asks clean Houdinis
(HOUDINI_USER_PREF_DIR pointing at the sandbox; 22.0, 21.0 and 20.5 when installed on this PC) whether the node type is there, whether it comes from the build
for that Houdini generation (h22 for Houdini 22, h205 for 20.5 and 21), whether the installed demo scene cooks without errors, and, in 20.5 and 21, whether a
second demo opened in the same session keeps its parameters. Checks: no Houdini preferences found (clear message, exit 1), install (only supported Houdini versions get
a package, each with its own build folder, payload complete), update keeps this version and the one before it and removes older ones, uninstall removes the
packages and the files and Houdini no longer finds the node. Prints the result and exits 1 on a failure. HFS_FOR_TEST selects another Houdini 22 install."""
from pathlib import Path
import json, os, shutil, subprocess, sys, tempfile
RELEASE=Path(sys.argv[1]).resolve()
SIDEFX=Path('C:/Program Files/Side Effects Software')
HOUDINI={'22.0':(Path(os.environ.get('HFS_FOR_TEST') or SIDEFX/'Houdini 22.0.368'),'h22','demos','Arraytron_v%s_all_demos.hip'),
         '21.0':(SIDEFX/'Houdini 21.0.440','h205','demos_h205','Arraytron_v%s_H205_all_demos.hip'),
         '20.5':(SIDEFX/'Houdini 20.5.445','h205','demos_h205','Arraytron_v%s_H205_all_demos.hip')}
INSTALLED={label:v for label,v in HOUDINI.items() if (v[0]/'bin'/'hython.exe').is_file()}
info=json.loads((RELEASE/'payload'/'VERSION.json').read_text(encoding='utf8'));VERSION=info['version'];TYPE='arraytron::instancer::'+VERSION
SANDBOX=Path(tempfile.mkdtemp(prefix='arraytron_installer_test_'));DOCS=SANDBOX/'Documents';ROOT=SANDBOX/'Local'/'Arraytron';DOCS.mkdir(parents=True)
failures=[]
def check(name,ok,detail=''):
    print(('PASS ' if ok else 'FAIL ')+name+('' if ok else '  -> '+str(detail)[:400]));sys.stdout.flush()
    if not ok:failures.append(name)
def installer(*args):
    return subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(RELEASE/'install.ps1'),'-Quiet','-Documents',str(DOCS),'-InstallRoot',str(ROOT),*args],capture_output=True,text=True,timeout=300)
def houdini(label,code):
    env=dict(os.environ);env['HOUDINI_USER_PREF_DIR']=str(DOCS/('houdini'+label));env.pop('HOUDINI_PACKAGE_DIR',None);env.pop('HOUDINI_OTLSCAN_PATH',None)
    return subprocess.run([str(INSTALLED[label][0]/'bin'/'hython.exe'),'-c',code],capture_output=True,text=True,timeout=900,env=env,cwd=str(SANDBOX))
LOOK="import hou\nt=hou.nodeType(hou.lopNodeTypeCategory(),%r)\nprint('FOUND' if t is not None else 'MISSING', t.definition().libraryFilePath() if t is not None else '')\n"%TYPE
def cook(label):
    hip=(ROOT/'versions'/VERSION/INSTALLED[label][2]/(INSTALLED[label][3]%VERSION)).as_posix()
    return "import hou\nhou.hipFile.load(%r,suppress_save_prompt=True,ignore_load_warnings=True)\nbad={}\nn_nodes=0\nfor n in hou.node('/stage').children():\n    if n.type().name().startswith('arraytron'):\n        n_nodes+=1\n        try:n.cook(force=True)\n        except hou.OperationFailed:pass\nfor n in hou.node('/stage').allSubChildren():\n    if n.errors():bad[n.path()]=n.errors()\nprint('COOKED',n_nodes,len(bad))\n"%hip
def two_demos(label):
    folder=(ROOT/'versions'/VERSION/INSTALLED[label][2]).as_posix()
    return "import hou\nfor name in ('%s_demo.hip','%s_mask_demo.hip','%s_demo.hip'):\n    hou.hipFile.load(%r+'/'+name,suppress_save_prompt=True,ignore_load_warnings=True)\n    print('PARMS',min(len(n.parms()) for n in hou.node('/stage').children() if n.type().name().startswith('arraytron')))\n"%(('Arraytron_v%s_H205'%VERSION,)*3+(folder,))
r=installer();check('no Houdini preferences: clear message and exit code 1',r.returncode==1 and 'No Houdini' in r.stdout,(r.returncode,r.stdout[-300:]))
for label in ('22.0','21.0','20.5','19.5'):(DOCS/('houdini'+label)).mkdir()
r=installer();check('install succeeds for Houdini 20.5, 21.0 and 22.0',r.returncode==0 and 'is installed for Houdini 20.5, 21.0, 22.0' in r.stdout,(r.returncode,r.stdout[-400:],r.stderr[-300:]))
dest=ROOT/'versions'/VERSION
check('an unsupported Houdini (19.5) gets no package',not (DOCS/'houdini19.5'/'packages'/'arraytron.json').exists())
for label,(hfs,folder,_demos,_hip) in HOUDINI.items():
    pkg=DOCS/('houdini'+label)/'packages'/'arraytron.json';data=json.loads(pkg.read_text(encoding='utf8')) if pkg.is_file() else {}
    low,high=('22.0','23.0') if folder=='h22' else ('20.5','22.0')
    check('Houdini %s: package file is valid and selects the %s build in the installed folder'%(label,folder),data.get('path')=='$ARRAYTRON/'+folder and Path(data.get('env',[{}])[0].get('ARRAYTRON','')).as_posix()==dest.as_posix() and "houdini_version >= '%s'"%low in data.get('enable','') and "< '%s'"%high in data.get('enable',''),data)
need=['h22/otls/Arraytron_v%s.hda'%VERSION,'h205/otls/Arraytron_v%s_H205.hda'%VERSION,'demos/Arraytron_v%s_all_demos.hip'%VERSION,'demos/Arraytron_v%s.hda'%VERSION,'demos/test_assets','demos_h205/Arraytron_v%s_H205_all_demos.hip'%VERSION,'demos_h205/test_assets','docs/USER_GUIDE.md','docs/INDEX.md','VERSION.json','INSTALL.md','CHANGELOG.md']
missing=[n for n in need if not (dest/n).exists()];check('installed payload is complete',not missing,missing)
check('installed.json records the install',json.loads((ROOT/'installed.json').read_text(encoding='utf8'))['version']==VERSION)
for label in INSTALLED:
    folder=INSTALLED[label][1]
    r=houdini(label,LOOK);check('Houdini %s: a clean session finds the HDA from the package (%s build)'%(label,folder),r.stdout.strip().startswith('FOUND') and (dest/folder/'otls').as_posix().lower() in r.stdout.replace('\\','/').lower(),(r.stdout[-300:],r.stderr[-300:]))
    r=houdini(label,cook(label));line=[l for l in r.stdout.splitlines() if l.startswith('COOKED')]
    check('Houdini %s: the installed all-demos scene cooks without errors in a clean session'%label,bool(line) and int(line[-1].split()[1])>=8 and line[-1].split()[2]=='0',(r.stdout[-400:],r.stderr[-400:]))
    if folder=='h205':
        r=houdini(label,two_demos(label));counts=[int(l.split()[1]) for l in r.stdout.splitlines() if l.startswith('PARMS')]
        check('Houdini %s: opening several demos one after another keeps the node parameters'%label,len(counts)==3 and min(counts)>300,(counts,r.stderr[-300:]))
# update: older versions are kept for one release only
for old in ('0.8.0','0.9.0'):(ROOT/'versions'/old).mkdir(parents=True,exist_ok=True);(ROOT/'versions'/old/'x.txt').write_text('old')
r=installer();names=sorted(p.name for p in (ROOT/'versions').iterdir())
check('update keeps this version and the one before it, removes older ones',r.returncode==0 and names==sorted([VERSION,'0.9.0']),names)
r=installer('-Houdini','22.0');check('installing again for one Houdini version works',r.returncode==0)
r=installer('-Uninstall');gone=not any((DOCS/('houdini'+label)/'packages'/'arraytron.json').exists() for label in HOUDINI) and not ROOT.exists()
check('uninstall removes the packages and the files',r.returncode==0 and gone,(r.stdout[-300:],ROOT.exists()))
for label in INSTALLED:
    r=houdini(label,LOOK);check('Houdini %s: after uninstall a clean session no longer finds the HDA'%label,r.stdout.strip().startswith('MISSING'),r.stdout[-200:])
shutil.rmtree(SANDBOX,ignore_errors=True)
print('installer validation: %d failure(s)'%len(failures))
sys.exit(1 if failures else 0)
