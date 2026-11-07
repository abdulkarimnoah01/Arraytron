"""Arraytron Stamp installer and updater validation: python tests/validate_stamp_installer.py <unpacked Release folder> [<update folder: the zip and version.json>]
Plain Python (it starts PowerShell and hython itself). Runs the real installer of the package in a sandbox (a temporary Documents folder and install root, never your own), then asks clean Houdinis
(HOUDINI_USER_PREF_DIR pointing at the sandbox; 22.0, 21.0 and 20.5 when installed on this PC) whether the node type is there, whether it comes from the build for that Houdini generation (h22 for
Houdini 22, h205 for 20.5 and 21), whether the installed demo cooks without errors and writes its 11, 67 and 300 stamps, and, in 20.5 and 21, whether a demo opened several times in one session keeps its parameters.
Installer: no Houdini preferences (clear message, exit 1), install (only supported Houdini versions get a package, each with its own build folder, payload complete), update keeps this version and the one before
it, uninstall removes the packages and the files and Houdini no longer finds the node; the package does not touch Arraytron's own folder or package. Updater (stamp_update.py of the payload): the manifest, the
version comparison, the Houdini range, the name guard (Arraytron's own version.json is refused), the checksum (a changed zip is refused), the install of the zip in a sandbox, the update source order.
Prints the result and exits 1 on a failure. HFS_FOR_TEST selects another Houdini 22 install."""
from pathlib import Path
import importlib.util, json, os, shutil, subprocess, sys, tempfile, zipfile
RELEASE=Path(sys.argv[1]).resolve();UPDATE=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else None
SIDEFX=Path('C:/Program Files/Side Effects Software')
info=json.loads((RELEASE/'payload'/'VERSION.json').read_text(encoding='utf8'));VERSION=info['version'];TYPE='arraytron::stamp::'+VERSION
HOUDINI={'22.0':(Path(os.environ.get('HFS_FOR_TEST') or SIDEFX/'Houdini 22.0.368'),'h22','demos','Arraytron_Stamp_v%s_demo.hip'%VERSION),
         '21.0':(SIDEFX/'Houdini 21.0.440','h205','demos_h205','Arraytron_Stamp_v%s_H205_demo.hip'%VERSION),
         '20.5':(SIDEFX/'Houdini 20.5.445','h205','demos_h205','Arraytron_Stamp_v%s_H205_demo.hip'%VERSION)}
INSTALLED={label:v for label,v in HOUDINI.items() if (v[0]/'bin'/'hython.exe').is_file()}
SANDBOX=Path(tempfile.mkdtemp(prefix='arraytron_stamp_installer_test_'));DOCS=SANDBOX/'Documents';ROOT=SANDBOX/'Local'/'ArraytronStamp';DOCS.mkdir(parents=True)
failures=[]
def check(name,ok,detail=''):
    print(('PASS ' if ok else 'FAIL ')+name+('' if ok else '  -> '+str(detail)[:400]));sys.stdout.flush()
    if not ok:failures.append(name)
def crashed(label,r):
    """Houdini 21.0.440's hython crashes on start with a clean preferences folder on this PC (the same for Arraytron's own installer test): not a result about the package. The same h205 build is tested in clean Houdini 20.5
    sessions here and in a normal Houdini 21 session by tests/validate_stamplite.py."""
    if label=='21.0' and r.returncode!=0 and not r.stdout.strip() and 'TRACEBACK' in r.stderr:
        print('SKIP Houdini 21.0: hython crashes with a clean preferences folder on this PC (environmental, not a package problem)');return True
    return False
def installer(*args,script=None,docs=None,root=None):
    return subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script or RELEASE/'install.ps1'),'-Quiet','-Documents',str(docs or DOCS),'-InstallRoot',str(root or ROOT),*args],capture_output=True,text=True,timeout=300)
def houdini(label,code):
    env=dict(os.environ);env['HOUDINI_USER_PREF_DIR']=str(DOCS/('houdini'+label));env.pop('HOUDINI_PACKAGE_DIR',None);env.pop('HOUDINI_OTLSCAN_PATH',None)
    return subprocess.run([str(INSTALLED[label][0]/'bin'/'hython.exe'),'-c',code],capture_output=True,text=True,timeout=900,env=env,cwd=str(SANDBOX))
LOOK="import hou\nt=hou.nodeType(hou.lopNodeTypeCategory(),%r)\nprint('FOUND' if t is not None else 'MISSING', t.definition().libraryFilePath() if t is not None else '')\nif t is not None:\n    s=t.definition().sections();print('SECTIONS', all(k in s for k in ('ViewerStateModule','StampPanel.py','PythonModule','Icon.svg','Help')))\n"%TYPE
def cook(label):
    hip=(ROOT/'versions'/VERSION/INSTALLED[label][2]/(INSTALLED[label][3])).as_posix()
    return ("import hou\nfrom pxr import UsdGeom\nhou.hipFile.load(%r,suppress_save_prompt=True,ignore_load_warnings=True)\nbad={}\ncounts=[]\nfor n in hou.node('/stage').children():\n    if n.type().name().startswith('arraytron::stamp'):\n"
            "        try:n.cook(force=True)\n        except hou.OperationFailed:pass\n        if n.errors():bad[n.path()]=n.errors()\n        else:\n            pi=UsdGeom.PointInstancer(n.stage().GetPrimAtPath(n.evalParm('outputpath')));counts.append(len(pi.GetPositionsAttr().Get()))\nprint('COOKED',len(counts),len(bad),sorted(counts))\n")%hip
def several(label):
    folder=(ROOT/'versions'/VERSION/INSTALLED[label][2]).as_posix();name=INSTALLED[label][3]
    return "import hou\nfor k in range(3):\n    hou.hipFile.load(%r+'/'+%r,suppress_save_prompt=True,ignore_load_warnings=True)\n    print('PARMS',min(len(n.parms()) for n in hou.node('/stage').children() if n.type().name().startswith('arraytron::stamp')))\n"%(folder,name)
# ---- the installer
r=installer();check('no Houdini preferences: clear message and exit code 1',r.returncode==1 and 'No Houdini' in r.stdout,(r.returncode,r.stdout[-300:]))
for label in ('22.0','21.0','20.5','19.5'):(DOCS/('houdini'+label)).mkdir()
r=installer();check('install succeeds for Houdini 20.5, 21.0 and 22.0',r.returncode==0 and 'is installed for Houdini 20.5, 21.0, 22.0' in r.stdout and 'Arraytron Stamp %s'%VERSION in r.stdout,(r.returncode,r.stdout[-400:],r.stderr[-300:]))
dest=ROOT/'versions'/VERSION
check('an unsupported Houdini (19.5) gets no package',not (DOCS/'houdini19.5'/'packages'/'arraytron_stamp.json').exists())
for label,(hfs,folder,_demos,_hip) in HOUDINI.items():
    pkg=DOCS/('houdini'+label)/'packages'/'arraytron_stamp.json';data=json.loads(pkg.read_text(encoding='utf8')) if pkg.is_file() else {}
    low,high=('22.0','23.0') if folder=='h22' else ('20.5','22.0')
    check('Houdini %s: package file is valid and selects the %s build in the installed folder'%(label,folder),data.get('path')=='$ARRAYTRON_STAMP/'+folder and Path(data.get('env',[{}])[0].get('ARRAYTRON_STAMP','')).as_posix()==dest.as_posix() and "houdini_version >= '%s'"%low in data.get('enable','') and "< '%s'"%high in data.get('enable',''),data)
check('Arraytron\'s own package file and folder are not touched',not any((DOCS/('houdini'+l)/'packages'/'arraytron.json').exists() for l in HOUDINI) and not (SANDBOX/'Local'/'Arraytron').exists())
need=['h22/otls/Arraytron_Stamp_v%s.hda'%VERSION,'h205/otls/Arraytron_Stamp_v%s_H205.hda'%VERSION,'h22/toolbar/arraytron_stamp.shelf','h205/toolbar/arraytron_stamp.shelf','demos/Arraytron_Stamp_v%s_demo.hip'%VERSION,'demos_h205/Arraytron_Stamp_v%s_H205_demo.hip'%VERSION,'demos/Arraytron_Stamp_v%s_paint_falloff_demo.hip'%VERSION,'demos_h205/Arraytron_Stamp_v%s_H205_paint_falloff_demo.hip'%VERSION,
      'docs/ARRAYTRON_STAMP.md','icon/Arraytron-Stamp.svg','updater/stamp_update.py','updater/stamp_update_ui.py','update_source.txt','VERSION.json','INSTALL.md','CHANGELOG.md']
missing=[n for n in need if not (dest/n).exists()];check('installed payload is complete',not missing,missing)
check('installed.json records the install',json.loads((ROOT/'installed.json').read_text(encoding='utf8'))['version']==VERSION)
check('the shelf names the Stamp\'s own variable and updater',all(s in (dest/'h22'/'toolbar'/'arraytron_stamp.shelf').read_text(encoding='utf8') for s in ('ARRAYTRON_STAMP','stamp_update_ui')) and 'arraytron_update' not in (dest/'h22'/'toolbar'/'arraytron_stamp.shelf').read_text(encoding='utf8'))
for label in INSTALLED:
    folder=INSTALLED[label][1]
    r=houdini(label,LOOK)
    if crashed(label,r):continue
    check('Houdini %s: a clean session finds the HDA from the package (%s build) with its viewer state, pane, icon and help'%(label,folder),r.stdout.strip().startswith('FOUND') and (dest/folder/'otls').as_posix().lower() in r.stdout.replace('\\','/').lower() and 'SECTIONS True' in r.stdout,(r.stdout[-300:],r.stderr[-300:]))
    r=houdini(label,cook(label));line=[l for l in r.stdout.splitlines() if l.startswith('COOKED')]
    check('Houdini %s: the installed demo cooks without errors in a clean session (11, 67 and 300 stamps)'%label,bool(line) and line[-1].split()[1]=='3' and line[-1].split()[2]=='0' and '[11, 67, 300]' in line[-1],(r.stdout[-400:],r.stderr[-400:]))
    if folder=='h205':
        r=houdini(label,several(label));counts=[int(l.split()[1]) for l in r.stdout.splitlines() if l.startswith('PARMS')]
        check('Houdini %s: opening the demo three times in one session keeps the node parameters'%label,len(counts)==3 and min(counts)>40,(counts,r.stderr[-300:]))
# update: older versions are kept for one release only
for old in ('0.6.0','0.7.0'):(ROOT/'versions'/old).mkdir(parents=True,exist_ok=True);(ROOT/'versions'/old/'x.txt').write_text('old')
r=installer();names=sorted(p.name for p in (ROOT/'versions').iterdir())
check('update keeps this version and the one before it, removes older ones',r.returncode==0 and names==sorted([VERSION,'0.7.0']),names)
r=installer('-Houdini','22.0');check('installing again for one Houdini version works',r.returncode==0)
r=installer('-Uninstall');gone=not any((DOCS/('houdini'+label)/'packages'/'arraytron_stamp.json').exists() for label in HOUDINI) and not ROOT.exists()
check('uninstall removes the packages and the files',r.returncode==0 and gone,(r.stdout[-300:],ROOT.exists()))
for label in INSTALLED:
    r=houdini(label,LOOK)
    if crashed(label,r):continue
    check('Houdini %s: after uninstall a clean session no longer finds the HDA'%label,r.stdout.strip().startswith('MISSING'),r.stdout[-200:])
# ---- the updater
spec=importlib.util.spec_from_file_location('stamp_update',RELEASE/'payload'/'updater'/'stamp_update.py');su=importlib.util.module_from_spec(spec);spec.loader.exec_module(su)
check('versions compare',su.is_newer('0.8.0','0.7.1') and su.is_newer('0.10.0','0.9.9') and not su.is_newer('0.8.0','0.8.0') and su.parse_version('v0.8.0')==(0,8,0))
check('the baked update source is the rolling stamp-latest release, not Arraytron\'s latest',(RELEASE/'payload'/'update_source.txt').read_text(encoding='utf8').strip().endswith('/releases/download/stamp-latest/') and 'releases/latest' not in (RELEASE/'payload'/'update_source.txt').read_text(encoding='utf8'))
env0={k:os.environ.get(k) for k in ('ARRAYTRON_STAMP_UPDATE_SOURCE','ARRAYTRON_UPDATE_SOURCE')};os.environ.pop('ARRAYTRON_STAMP_UPDATE_SOURCE',None);os.environ['ARRAYTRON_UPDATE_SOURCE']='C:/arraytron/own'
prefs=SANDBOX/'prefs';home=SANDBOX/'home';home.mkdir();(home/'update_source.txt').write_text('C:/baked\n');prefs.mkdir()
check('update source: Arraytron\'s own variable is ignored, the baked address is used',su.update_source(str(prefs),str(home))=='C:/baked')
su.save_update_source(str(prefs),'C:/mine');check('update source: the artist\'s own choice beats the baked one (arraytron_stamp_update.json)',su.update_source(str(prefs),str(home))=='C:/mine' and (prefs/'arraytron_stamp_update.json').is_file() and not (prefs/'arraytron_update.json').exists())
os.environ['ARRAYTRON_STAMP_UPDATE_SOURCE']='C:/env';check('update source: ARRAYTRON_STAMP_UPDATE_SOURCE beats both',su.update_source(str(prefs),str(home))=='C:/env')
for k,v in env0.items():
    if v is None:os.environ.pop(k,None)
    else:os.environ[k]=v
if UPDATE is not None:
    manifest=su.read_manifest(str(UPDATE));zip_path=UPDATE/manifest['zip']
    check('version.json: the Stamp, this version, its zip, a valid checksum and notes',manifest['name']=='Arraytron Stamp' and manifest['version']==VERSION and zip_path.is_file() and manifest['sha256']==__import__('hashlib').sha256(zip_path.read_bytes()).hexdigest() and manifest['size']==zip_path.stat().st_size and len(manifest['notes'])>=3,manifest)
    check('an older install is offered this version, the same version is up to date',su.check(str(UPDATE),'0.7.0',(22,0))['version']==VERSION and su.check(str(UPDATE),VERSION,(22,0)) is None and su.check(str(UPDATE),'0.99.0',(22,0)) is None)
    for h in ((20,5),(21,0),(22,0)):check('Houdini %s.%s is inside the supported range'%h,su.supports_houdini(manifest,h))
    try:su.check(str(UPDATE),'0.7.0',(19,5));check('an unsupported Houdini is told so',False)
    except su.UpdateError as e:check('an unsupported Houdini is told so',True)
    other=SANDBOX/'arraytron_manifest';other.mkdir();(other/'version.json').write_text(json.dumps(dict(manifest,name='Arraytron')),encoding='utf-8')
    try:su.read_manifest(str(other));check('Arraytron\'s own version.json is refused (name guard)',False)
    except su.UpdateError as e:check('Arraytron\'s own version.json is refused (name guard)','not for Arraytron Stamp' in str(e),str(e))
    bad=SANDBOX/'tampered';shutil.copytree(UPDATE,bad);data=bytearray((bad/manifest['zip']).read_bytes());data[len(data)//2]^=0xFF;(bad/manifest['zip']).write_bytes(bytes(data))
    try:su.download(str(bad),su.read_manifest(str(bad)),str(SANDBOX));check('a changed zip is refused before anything is unpacked',False)
    except su.UpdateError as e:check('a changed zip is refused before anything is unpacked','checksum' in str(e),str(e))
    got=su.download(str(UPDATE),manifest,str(SANDBOX));docs2=SANDBOX/'Documents2';root2=SANDBOX/'Local2'/'ArraytronStamp';(docs2/'houdini22.0').mkdir(parents=True);(docs2/'houdini20.5').mkdir()
    ok,output=su.install(got,['-Documents',str(docs2),'-InstallRoot',str(root2)])
    check('the update zip installs through the installer inside it (sandbox)',ok and json.loads((root2/'installed.json').read_text(encoding='utf8'))['version']==VERSION and (docs2/'houdini22.0'/'packages'/'arraytron_stamp.json').is_file() and (root2/'versions'/VERSION/'h205'/'otls').is_dir(),output[-300:])
    r=installer('-Uninstall',docs=docs2,root=root2);check('and uninstalls',r.returncode==0 and not root2.exists())
shutil.rmtree(SANDBOX,ignore_errors=True)
print('Arraytron Stamp installer validation: %d failure(s)'%len(failures))
sys.exit(1 if failures else 0)
