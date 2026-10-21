"""Build the shipping packages: python tools/make_release.py [--skip-verify]
Produces, in release/ (a PhiAxis-style installer package and a development kit, both as RAR archives):
  Arraytron_v<ver>_Release.rar  Install Arraytron.cmd, Uninstall Arraytron.cmd, install.ps1, INSTALL.md, README.md, CHANGELOG.md and payload/ (the HDAs in h22/otls and h205/otls, the
                                demos with their assets and caches, the documentation, the icon, preview renders). Double-click Install Arraytron.cmd.
  Arraytron_v<ver>_DevKit.rar   everything needed to continue the work on another PC (also with another Claude instance): sources, build tools, test suites,
                                documents including HANDOFF.md, the built release files, the previous HDAs the suites compare against, the Claude memory copy.
  SHA256SUMS.txt                hashes of both archives.
Before packing it requires `python tools/check_docs.py` to pass. Unless --skip-verify it then proves the packages: the archives are tested, the Release
archive is unpacked and its installer is run in a sandbox with clean Houdinis (tests/validate_installer.py: 22.0, 21.0 and 20.5 when installed), and the DevKit is unpacked
and checked (check_docs, the main, polish and production suites with hython 22 and hython 20.5, and tests/validate_h205.py run inside the unpacked copy). Needs WinRAR's Rar.exe and Houdini
22.0.368, 21.0.440 and 20.5.445 (hython). The release holds both builds: payload/h22/otls and payload/h205/otls, demos and demos_h205. Earlier releases' archives in release/ are kept."""
from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.CURRENT;VER=VID[1:]
UPDATE_SOURCE=os.environ.get('ARRAYTRON_UPDATE_SOURCE_BAKED','https://github.com/abdulkarimnoh01/Arraytron/releases/latest/download/')                                # set by tools/make_update_zip.py
OUT=ROOT/'release';DIST=ROOT/'dist';H205=ROOT/'otls_h205'
HYTHON=Path('C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe')
HYTHON205=Path('C:/Program Files/Side Effects Software/Houdini 20.5.445/bin/hython.exe')       # builds the Houdini 20.5 / 21 HDA; Houdini 21.0.440 is tested too
def find_rar():
    for p in ('C:/Program Files/WinRAR/Rar.exe','C:/Program Files (x86)/WinRAR/Rar.exe'):
        if Path(p).is_file():return p
    found=shutil.which('rar')
    if found:return found
    raise SystemExit('Rar.exe (WinRAR) was not found.')
RAR=find_rar()
def run(cmd,cwd=None,check=True,quiet=False):
    r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True)
    if check and r.returncode!=0:raise SystemExit('FAILED: %s\n%s\n%s'%(' '.join(map(str,cmd)),r.stdout[-1500:],r.stderr[-800:]))
    return r
def copy_tree(src,dst,skip=('__pycache__',),only_suffix=None):
    for p in Path(src).rglob('*'):
        if any(s in p.parts for s in skip) or p.is_dir():continue
        if only_suffix and p.suffix.lower() not in only_suffix:continue
        target=Path(dst)/p.relative_to(src);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
def living_docs():
    """The documents an artist or developer reads (not the history of old multi-agent runs)."""
    return [p for p in sorted((ROOT/'docs').glob('*.md')) if 'AUDIT' not in p.name and not p.name.startswith('TEAM_') and p.name not in ('CODER_RETRY.md','CONTROLS_COVERAGE.md','CONTROLS_FINAL_REVIEW.md','FINAL_REVIEW.md','INITIAL_TEAM_TASK.md','RESEARCH_RECHECK.md','RESEARCH_TASK.md')]

def build_release(stage):
    top=stage/('Arraytron_v%s_Release'%VER);top.mkdir(parents=True)
    for f in ('Install Arraytron.cmd','Uninstall Arraytron.cmd','install.ps1'):shutil.copy2(ROOT/'installer'/f,top/f)
    for f in ('INSTALL.md','README.md','CHANGELOG.md'):shutil.copy2(ROOT/f,top/f)
    payload=top/'payload'
    (payload/'h22'/'otls').mkdir(parents=True);shutil.copy2(DIST/('Arraytron_%s.hda'%VID),payload/'h22'/'otls')                      # Houdini 22
    (payload/'h205'/'otls').mkdir(parents=True);shutil.copy2(H205/('Arraytron_%s_H205.hda'%VID),payload/'h205'/'otls')              # Houdini 20.5 and 21
    demos=payload/'demos';demos.mkdir()
    shutil.copy2(DIST/('Arraytron_%s.hda'%VID),demos)                                              # next to the hips: they reference $HIP/Arraytron_<ver>.hda
    for p in sorted(DIST.glob('Arraytron_%s_*demo.hip'%VID))+[DIST/('Arraytron_%s_all_demos.hip'%VID)]:shutil.copy2(p,demos)
    copy_tree(DIST/'test_assets',demos/'test_assets');copy_tree(DIST/'arraytron_cache',demos/'arraytron_cache')
    demos205=payload/'demos_h205';demos205.mkdir()                                                   # no HDA beside these hips: they find it through the package (see versions.ensure_installed)
    for p in sorted(H205.glob('Arraytron_%s_H205_*demo.hip'%VID))+[H205/('Arraytron_%s_H205_all_demos.hip'%VID)]:shutil.copy2(p,demos205)
    copy_tree(H205/'test_assets',demos205/'test_assets');copy_tree(H205/'arraytron_cache',demos205/'arraytron_cache')
    (payload/'docs').mkdir()
    for p in living_docs():shutil.copy2(p,payload/'docs')
    for f in ('INSTALL.md','CHANGELOG.md','README.md'):shutil.copy2(ROOT/f,payload/f)
    (payload/'updater').mkdir()
    for f in ('arraytron_update.py','arraytron_update_ui.py'):shutil.copy2(ROOT/'src'/f,payload/'updater'/f)                    # the in-Houdini Check for Updates (shelf tool, plain Python)
    for build in ('h22','h205'):(payload/build/'toolbar').mkdir(exist_ok=True);shutil.copy2(ROOT/'toolbar'/'arraytron.shelf',payload/build/'toolbar')
    if UPDATE_SOURCE:(payload/'update_source.txt').write_text(UPDATE_SOURCE.strip()+'\n',encoding='utf8')
    copy_tree(ROOT/'icon',payload/'icon');(payload/'previews').mkdir()
    for p in sorted((ROOT/'renders').glob('arraytron_%s_*.png'%VID)):shutil.copy2(p,payload/'previews')
    (payload/'VERSION.json').write_text(json.dumps({'version':VER,'name':'Arraytron','houdini':{'min':'20.5','max_exclusive':'23.0'},
        'builds':[{'folder':'h22','min':'22.0','max_exclusive':'23.0','built_with':'22.0.368','tested':['22.0.368']},
                  {'folder':'h205','min':'20.5','max_exclusive':'22.0','built_with':'20.5.445','tested':['20.5.445','21.0.440']}]},indent=2),encoding='utf8')
    return top

def build_devkit(stage):
    top=stage/('Arraytron_v%s_DevKit'%VER);top.mkdir(parents=True)
    for f in ('CLAUDE.md','HANDOFF.md','STATUS.md','README.md','INSTALL.md','CHANGELOG.md','Arraytron_Master_Solaris_Instancer_Prompt.md'):
        if (ROOT/f).is_file():shutil.copy2(ROOT/f,top/f)
    for d in ('src','tools','tests','installer','icon','handoff'):copy_tree(ROOT/d,top/d)
    (top/'docs').mkdir()
    for p in sorted((ROOT/'docs').glob('*.md')):shutil.copy2(p,top/'docs'/p.name)                     # all documents, history included
    copy_tree(ROOT/'docs'/'images',top/'docs'/'images')                                                # pictures the README shows
    (top/'dist').mkdir()
    for p in DIST.glob('Arraytron_%s*'%VID):
        if p.is_file():shutil.copy2(p,top/'dist')
    shutil.copy2(DIST/'manifest.json',top/'dist'/'manifest.json')
    copy_tree(DIST/'test_assets',top/'dist'/'test_assets');copy_tree(DIST/'arraytron_cache',top/'dist'/'arraytron_cache')
    copy_tree(H205,top/'otls_h205',skip=('__pycache__','backup'))                                      # the Houdini 20.5 / 21 HDAs (release and the older baselines the suites compare against), demos, assets, caches
    (top/'dist'/'archive').mkdir()
    for p in (DIST/'archive').glob('*.hda'):shutil.copy2(p,top/'dist'/'archive')                         # the suites compare against the previous releases
    (top/'renders').mkdir()
    for p in (ROOT/'renders').glob('arraytron_%s_*.png'%VID):shutil.copy2(p,top/'renders')
    return top

def pack(folder,archive):
    if archive.exists():archive.unlink()
    run([RAR,'a','-r','-m5','-md128m','-rr3p','-idq','-y',str(archive),folder.name],cwd=folder.parent)
    run([RAR,'t','-idq',str(archive)])
    return archive

def sha(path):
    h=hashlib.sha256();h.update(Path(path).read_bytes());return h.hexdigest().upper()

def main():
    skip_verify='--skip-verify' in sys.argv
    r=run([sys.executable,str(ROOT/'tools'/'check_docs.py')],check=False);print(r.stdout.strip())
    if r.returncode!=0:raise SystemExit('Documents are not current: fix the problems above (python tools/check_docs.py), then build again.')
    run([sys.executable,str(ROOT/'tools'/'make_manifest.py')])
    OUT.mkdir(exist_ok=True)
    for old in list(OUT.glob('*_v%s_*.rar'%VER)):old.unlink()                                      # earlier releases' archives stay
    stage=Path(tempfile.mkdtemp(prefix='arraytron_release_'))
    release_dir=build_release(stage);devkit_dir=build_devkit(stage)
    release_rar=pack(release_dir,OUT/('Arraytron_v%s_Release.rar'%VER));devkit_rar=pack(devkit_dir,OUT/('Arraytron_v%s_DevKit.rar'%VER))
    print('built %s (%.1f MB) and %s (%.1f MB)'%(release_rar.name,release_rar.stat().st_size/1e6,devkit_rar.name,devkit_rar.stat().st_size/1e6))
    if not skip_verify:
        check=Path(tempfile.mkdtemp(prefix='arraytron_verify_'))
        run([RAR,'x','-idq','-y',str(release_rar),str(check)+os.sep]);unpacked=check/('Arraytron_v%s_Release'%VER)
        r=run([sys.executable,str(ROOT/'tests'/'validate_installer.py'),str(unpacked)],check=False);print(r.stdout.strip())
        if r.returncode!=0:raise SystemExit('The installer validation failed (see above).')
        run([RAR,'x','-idq','-y',str(devkit_rar),str(check)+os.sep]);kit=check/('Arraytron_v%s_DevKit'%VER)
        r=run([sys.executable,str(kit/'tools'/'check_docs.py')],check=False);print('DevKit check_docs:',r.stdout.strip().splitlines()[0])
        if r.returncode!=0:print(r.stdout);raise SystemExit('check_docs fails inside the unpacked DevKit.')
        for hython,label in ((HYTHON,'Houdini 22'),(HYTHON205,'Houdini 20.5')):
            for suite in ('v016','polish','production'):
                r=run([str(hython),str(kit/'tests'/('validate_%s.py'%suite)),VID],cwd=str(kit),check=False);line=[l for l in r.stdout.splitlines() if 'ALL PASSED' in l]
                print('DevKit validate_%s (%s): %s'%(suite,label,line[-1][:60] if line else 'FAILED'))
                if r.returncode!=0 or not line:print(r.stdout[-1500:],r.stderr[-800:]);raise SystemExit('A suite failed inside the unpacked DevKit.')
        r=run([sys.executable,str(kit/'tests'/'validate_h205.py'),VID],cwd=str(kit),check=False);line=[l for l in r.stdout.splitlines() if 'ALL PASSED' in l]
        print('DevKit validate_h205 (Houdini 22 against 20.5 and 21): %s'%(line[-1][:60] if line else 'FAILED'))
        if r.returncode!=0 or not line:print(r.stdout[-1500:],r.stderr[-800:]);raise SystemExit('The cross-version suite failed inside the unpacked DevKit.')
        shutil.rmtree(check,ignore_errors=True)
    (OUT/'SHA256SUMS.txt').write_text('\n'.join('%s  %s'%(sha(p),p.name) for p in sorted(OUT.glob('Arraytron_v*_*.rar')))+'\n',encoding='utf8')
    shutil.copy2(ROOT/'CHANGELOG.md',OUT/'RELEASE_NOTES.md')
    shutil.rmtree(stage,ignore_errors=True)
    print('release ready in',OUT)
if __name__=="__main__":main()
