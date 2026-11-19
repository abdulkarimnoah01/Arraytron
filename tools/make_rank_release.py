"""Rank_Array and Rank_Stamp: Arraytron and Arraytron Stamp released under new names, nothing else changed.

    python tools/make_rank_release.py stage   array|stamp     copy the tracked sources into build_rank_<array|stamp>/ and rename them
    python tools/make_rank_release.py build   array|stamp     build the HDAs there (hython 22 and 20.5)
    python tools/make_rank_release.py demos   array           build the demo scenes there (hython 22 and 20.5), the all-demos scene included
    python tools/make_rank_release.py package array|stamp     the update zip + version.json (array) or make_stamp_release.py (stamp), with the installer checks
    python tools/make_rank_release.py publish array|stamp     the GitHub releases (rank-array-v<ver> + rank-array-latest, rank-stamp-v<ver> + rank-stamp-latest), never marked latest
    python tools/make_rank_release.py all     array|stamp     all of the above

It is the same code and the same version numbers as Arraytron (CURRENT in tools/versions.py) and Arraytron Stamp (STAMP_VERSION in tools/build_stamp_light.py): run it after every release of those two.
The staging copy has every name changed (files and text): Arraytron -> Rank_Array / Arraytron Stamp -> Rank_Stamp, node types rank_array::instancer::<ver> and rank_stamp::stamp::<ver>, the install
folders, installers, package files, environment variables, viewer states and update sources, so the new tools install next to the old ones. The repository address in URLs is kept. Releases go to the same
public repository as extra releases that are never the latest one, so Arraytron's own updater never sees them."""
from pathlib import Path
import json, os, re, shutil, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
HYTHON=Path('C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe');HYTHON205=Path('C:/Program Files/Side Effects Software/Houdini 20.5.445/bin/hython.exe')
REPO='abdulkarimnoah01/Arraytron'
TEXT={'.py','.md','.cmd','.ps1','.vfl','.json','.txt','.usda','.xml','.html','.ini','.csv','.cfg','.sh','.shelf','.pypanel','.toml'}
PROTECT=('abdulkarimnoah01/Arraytron-dev','abdulkarimnoah01/Arraytron')                       # the repository address stays
ARRAY_PAIRS=(('ARRAYTRON','RANK_ARRAY'),('Arraytron','Rank_Array'),('arraytron','rank_array'))
STAMP_PAIRS=(('Arraytron Stamp','Rank_Stamp'),('Arraytron-Stamp','Rank_Stamp'),('Arraytron_Stamp','Rank_Stamp'),('ArraytronStamp','RankStamp'),('ARRAYTRON_STAMP','RANK_STAMP'),
             ('arraytron::stamp','rank_stamp::stamp'),('arraytron_stamp','rank_stamp'),('arraytron-stamp','rank-stamp'))
DEMOS=('v03 paint_v060 paint_k_v150 fields_v070 cluster_v080 camera_v090 finish_v100 imported_v150 lodgen_v180 place_v190 falloff_v1120 rows_v1140 noise_v1220 proxy_v1240 viz_v1240 noisetypes_v1240 '
       'masknoise_v1250 palettes_v1250 biome_v1150 grow_v052 mask_v050 overlap_v051 groundauto_v1252 maskpaint_v1260 maskfull_v1270 hpaint_v1280 groups_v1290 surfdir_v1300 surfproxy_v1310 '
       'maskshape_v1320 maskfade_v1320 fieldmask_v1330 blast_v1330 mirror_v1340').split()

def stage_dir(kind):return ROOT/('build_rank_'+kind)
def rename_text(text,kind):
    held={};
    for i,p in enumerate(PROTECT):
        key='\0P%d\0'%i;text=text.replace(p,key);held[key]=p
    if kind=='stamp':
        for a,b in STAMP_PAIRS:text=text.replace(a,b)
        text=re.sub(r'(?<![-\w])stamp-(latest|v)',r'rank-stamp-\1',text)                           # the release tags
        text=text.replace("Arraytron's","Arraytron's")
    else:
        for a,b in ARRAY_PAIRS:text=text.replace(a,b)
        text=text.replace('releases/latest/download/','releases/download/rank-array-latest/')            # the rolling release the installed copies read
    for key,p in held.items():text=text.replace(key,p)
    return text
def rename_name(name,kind):
    pairs=STAMP_PAIRS if kind=='stamp' else ARRAYTRON_NAME_PAIRS
    for a,b in pairs:name=name.replace(a,b)
    return name
ARRAYTRON_NAME_PAIRS=ARRAY_PAIRS

def git_files():
    out=subprocess.run(['git','ls-files'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.splitlines();return [f for f in out if f]
def wanted(path,kind):
    top=path.split('/')[0];low=path.lower()
    if kind=='array':
        if 'stamp' in low:return False
        return top in ('src','tools','installer','icon','toolbar','docs') or path in ('README.md','INSTALL.md','CHANGELOG.md','LICENSE','tests/validate_installer.py')
    return top in ('src','tools','installer_stamp','toolbar_stamp','icon','docs') or path in ('README_STAMP.md','INSTALL_STAMP.md','CHANGELOG_STAMP.md','LICENSE','tests/validate_stamp_installer.py','tools/versions.py')
def stage(kind):
    dst=stage_dir(kind)
    if dst.exists():shutil.rmtree(dst)
    dst.mkdir();n=0
    for f in git_files():
        if not wanted(f,kind):continue
        src=ROOT/f
        if not src.is_file():continue
        target=dst/Path(*[rename_name(part,kind) for part in Path(f).parts]);target.parent.mkdir(parents=True,exist_ok=True)
        if src.suffix.lower() in TEXT:
            raw=src.read_bytes()
            try:text=raw.decode('utf-8')
            except UnicodeDecodeError:shutil.copy2(src,target);n+=1;continue
            target.write_bytes(rename_text(text,kind).encode('utf-8'))
        else:shutil.copy2(src,target)
        n+=1
    for folder in ('dist/test_assets',):                                                                      # assets the builders and demos read (not tracked)
        if (ROOT/folder).is_dir():shutil.copytree(ROOT/folder,dst/folder)
    if kind=='array':patch_hdas_only(dst)
    print('staged %d files into %s'%(n,dst))
def patch_hdas_only(dst):
    """Rank_Array is released as the HDAs alone: no demo scenes. The package builder leaves the demos out and the installer check cooks a new node of the installed HDA instead of a demo scene."""
    p=dst/'tools'/'make_release.py';lines=p.read_text(encoding='utf-8').split('\n')
    drop=("demos=payload/'demos'","shutil.copy2(DIST/('Rank_Array_%s.hda'%VID),demos)","shutil.copy2(DIST/('Rank_Array_%s_all_demos.hip'%VID),demos)","copy_tree(DIST/'test_assets',demos/","demos205=payload/'demos_h205'","shutil.copy2(H205/('Rank_Array_%s_H205_all_demos.hip'%VID),demos205)","copy_tree(H205/'test_assets',demos205/")
    kept=[l for l in lines if not l.strip().startswith(drop)];assert len(lines)-len(kept)==7,len(lines)-len(kept);p.write_text('\n'.join(kept),encoding='utf-8')
    p=dst/'CHANGELOG.md';t=p.read_text(encoding='utf-8');t=t.replace('**The release carries the all-demos scene only** (the single demo scenes stay in the development tree).','**The release carries the HDAs only**: no demo scenes.');p.write_text(t,encoding='utf-8')
    p=dst/'tests'/'validate_installer.py';t=p.read_text(encoding='utf-8')
    for a,b in (("'demos/Rank_Array_v%s_all_demos.hip'%VERSION,'demos/Rank_Array_v%s.hda'%VERSION,'demos/test_assets','demos_h205/Rank_Array_v%s_H205_all_demos.hip'%VERSION,'demos_h205/test_assets',",""),
                ("r=houdini(label,cook(label))","r=houdini(label,COOK)"),("r=houdini(label,two_demos(label))","r=houdini(label,THREE)"),
                ("int(line[-1].split()[1])>=8","int(line[-1].split()[1])>=1"),
                ("the installed all-demos scene cooks without errors in a clean session","a new node of the installed HDA cooks without errors in a clean session"),
                ("opening several demos one after another keeps the node parameters","making several nodes one after another keeps the node parameters")):
        assert a in t,a[:60];t=t.replace(a,b,1)
    i=t.index('LOOK=');j=t.index('\n',i)
    t=t[:j+1]+"COOK=\"import hou\\nn=hou.node('/stage').createNode(%r)\\nn.hdaModule().test_setup(n)\\ntry:n.cook(force=True)\\nexcept hou.OperationFailed:pass\\nbad={}\\nfor c in [n]+list(n.allSubChildren()):\\n    if c.errors():bad[c.path()]=c.errors()\\nprint('COOKED',1,len(bad))\\n\"%TYPE\nTHREE=\"import hou\\nfor k in range(3):\\n    n=hou.node('/stage').createNode(%r);n.hdaModule().test_setup(n);n.cook(force=True)\\n    print('PARMS',len(n.parms()))\\n\"%TYPE\n"+t[j+1:]
    p.write_text(t,encoding='utf-8')

def run(cmd,cwd,env=None,check=True):
    e=dict(os.environ)
    if env:e.update(env)
    r=subprocess.run([str(c) for c in cmd],cwd=str(cwd),capture_output=True,text=True,env=e)
    if check and r.returncode!=0:raise SystemExit('FAILED: %s\n%s\n%s'%(' '.join(map(str,cmd)),r.stdout[-1500:],r.stderr[-800:]))
    return r
def env205(kind):return {'HOUDINI_OTLSCAN_PATH':str(stage_dir(kind)/'otls_h205').replace('/','\\')+';&'}
def build(kind):
    d=stage_dir(kind);ver=version(kind)
    if kind=='array':
        script=['tools/build_rank_array_v03.py','v'+ver]
    else:script=['tools/build_stamp_light.py']
    for hy,env in ((HYTHON,None),(HYTHON205,None)):
        r=run([hy]+script,d,env);print(kind,'built with',hy.parent.parent.name,'->',[l for l in r.stdout.splitlines() if '"errors"' in l or 'hda' in l][-2:])
def version(kind):
    if kind=='array':return re.search(r"CURRENT='v([0-9.]+)'",(ROOT/'tools'/'versions.py').read_text(encoding='utf-8')).group(1)
    return re.search(r"STAMP_VERSION='([0-9.]+)'",(ROOT/'tools'/'build_stamp_light.py').read_text(encoding='utf-8')).group(1)
def demos(kind):
    d=stage_dir(kind);ver='v'+version(kind)
    for hy,env in ((HYTHON,None),(HYTHON205,env205(kind))):
        e=dict(env or {});e['ARRAYTRON_VERSION'.replace('ARRAYTRON','RANK_ARRAY')]=ver;e['ARRAYTRON_VERSION']=ver
        for name in DEMOS:
            r=run([hy,'tools/build_demo_%s.py'%name],d,e,check=False);print(name,'ok' if '"saved"' in r.stdout or r.returncode==0 else 'FAILED',r.stdout.strip().splitlines()[-1][:90] if r.stdout.strip() else '')
        for k in ('railway','box'):
            r=run([hy,'tools/build_demo_physics.py',k],d,e,check=False);print('physics',k,r.returncode)
        r=run([hy,'tools/build_demo_all.py'],d,e,check=False);print('all demos',r.returncode,r.stdout.strip().splitlines()[-1][:120] if r.stdout.strip() else r.stderr[-300:])
def package(kind):
    d=stage_dir(kind)
    if kind=='stamp':
        run([sys.executable,'tools/make_stamp_release.py'],d);print('stamp release ready in',d/'release'/'stamp');return
    run([sys.executable,'tools/make_manifest.py'],d,check=False)
    r=run([sys.executable,'tools/make_update_zip.py'],d);print(r.stdout.strip()[-400:])
    import zipfile,tempfile;ver=version('array');zips=list((d/'release'/'update').glob('*-%s.zip'%ver));assert zips,'no update zip'
    tmp=Path(tempfile.mkdtemp(prefix='rank_array_check_'));zipfile.ZipFile(zips[0]).extractall(tmp);top=next(p.parent for p in tmp.rglob('install.ps1'))
    r=run([sys.executable,'tests/validate_installer.py',top],d,check=False);print(r.stdout.strip()[-1800:])
def publish(kind):
    d=stage_dir(kind);ver=version(kind)
    if kind=='stamp':
        r=run([sys.executable,'tools/publish_stamp_release.py'],d,check=False);print(r.stdout.strip(),r.stderr.strip()[-300:]);return
    out=d/'release'/'update';manifest=json.loads((out/'version.json').read_text(encoding='utf-8'))
    if manifest.get('name')!='Rank_Array':raise SystemExit('release/update/version.json is not Rank_Array\'s.')
    files=[out/manifest['zip'],out/'version.json'];notes=out/'RELEASE_NOTES.md'
    notes.write_text('# Rank_Array %s\n\n%s\n\nInstall: unpack the zip and run Install Rank_Array.cmd, or use Check for Updates in an installed copy.\n'%(ver,'\n'.join('* '+n for n in manifest.get('notes',[]))),encoding='utf-8')
    title='Rank_Array %s'%ver
    for tag,rolling in (('rank-array-v'+ver,False),('rank-array-latest',True)):
        exists=run(['gh','release','view',tag,'--repo',REPO],d,check=False).returncode==0
        if exists:
            run(['gh','release','edit',tag,'--repo',REPO,'--title',title,'--notes-file',notes,'--latest=false'],d);run(['gh','release','upload',tag,'--repo',REPO,'--clobber']+files,d)
        else:run(['gh','release','create',tag,'--repo',REPO,'--title',title,'--notes-file',notes,'--latest=false']+files,d)
        if exists and rolling:
            for a in json.loads(run(['gh','release','view',tag,'--repo',REPO,'--json','assets'],d).stdout)['assets']:
                if a['name'] not in {f.name for f in files}:run(['gh','release','delete-asset',tag,a['name'],'--repo',REPO,'--yes'],d)
        print('published',tag)
def main():
    if len(sys.argv)!=3 or sys.argv[1] not in ('stage','build','demos','package','publish','all') or sys.argv[2] not in ('array','stamp'):raise SystemExit(__doc__)
    step,kind=sys.argv[1],sys.argv[2]
    steps=dict(stage=stage,build=build,demos=demos,package=package,publish=publish)
    for name in (('stage','build','demos','package','publish') if step=='all' else (step,)):
        if name=='demos':continue                                                                              # Rank_Array and Rank_Stamp come without demo scenes (the Stamp builds its own small demo in make_stamp_release)
        print('==',name,kind);steps[name](kind)
if __name__=='__main__':main()
