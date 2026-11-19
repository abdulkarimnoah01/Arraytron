"""Build the Arraytron Stamp release: python tools/make_stamp_release.py [--skip-verify] [--out release/stamp] [--update-source <folder or https url>]
Plain Python (it starts hython and WinRAR itself). Needs the built HDAs (hython tools/build_stamp_light.py with hython 22 and with hython 20.5) and CHANGELOG_STAMP.md.
Produces, in release/stamp/:
  Arraytron_Stamp_v<ver>_Release.rar   the installer package: Install Arraytron Stamp.cmd, Uninstall Arraytron Stamp.cmd, install.ps1, INSTALL.md, CHANGELOG.md and payload/ (the HDAs in
                                       h22/otls and h205/otls, the shelf with Check for Updates, the demos, the documentation, the icon, the updater)
  Arraytron-Stamp-<ver>.zip            the same package as the update source file, and version.json (name, version, sha256, size, Houdini range, notes from CHANGELOG_STAMP.md)
  SHA256SUMS.txt
Arraytron Stamp is its own product: its own install folder (%LOCALAPPDATA%\\ArraytronStamp), package file (arraytron_stamp.json), variable (ARRAYTRON_STAMP) and update source, so it never mixes with Arraytron.
Unless --skip-verify the Release archive is unpacked and tests/validate_stamp_installer.py runs the installer in a sandbox with clean Houdinis (22.0, 21.0 and 20.5 when installed) and the
update path end to end with the zip and version.json. The version is STAMP_VERSION in tools/build_stamp_light.py."""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, zipfile
from datetime import date
ROOT=Path(__file__).resolve().parents[1]
VER=re.search(r"STAMP_VERSION='([0-9.]+)'",(ROOT/'tools'/'build_stamp_light.py').read_text(encoding='utf-8')).group(1)
HDA22=ROOT/'dist'/('Arraytron_Stamp_v%s.hda'%VER);HDA205=ROOT/'otls_h205'/('Arraytron_Stamp_v%s_H205.hda'%VER)
HYTHON=Path('C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe');HYTHON205=Path('C:/Program Files/Side Effects Software/Houdini 20.5.445/bin/hython.exe')
DEFAULT_UPDATE_SOURCE='https://github.com/abdulkarimnoah01/Arraytron/releases/download/stamp-latest/'          # the rolling release that tools/publish_stamp_release.py keeps current (not the repo's "latest": that is Arraytron's)
HOUDINI={'min':'20.5','max_exclusive':'23.0'}
def find_rar():
    for p in ('C:/Program Files/WinRAR/Rar.exe','C:/Program Files (x86)/WinRAR/Rar.exe'):
        if Path(p).is_file():return p
    found=shutil.which('rar')
    if found:return found
    raise SystemExit('Rar.exe (WinRAR) was not found.')
def run(cmd,cwd=None,check=True):
    r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True)
    if check and r.returncode!=0:raise SystemExit('FAILED: %s\n%s\n%s'%(' '.join(map(str,cmd)),r.stdout[-1500:],r.stderr[-800:]))
    return r
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def notes(version):
    """The bullets of this version's section of CHANGELOG_STAMP.md, without markdown."""
    lines,grab=[],False
    for line in (ROOT/'CHANGELOG_STAMP.md').read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            if grab:break
            grab=line[3:].strip().lstrip('v').split(' ')[0]==version
        elif grab and line.lstrip().startswith(('*','-')):lines.append(re.sub(r'[`*]','',line.strip().lstrip('*-').strip()))
    return lines
def build_package(stage,update_source,demos):
    """The folder of the package. demos: {h22: hip, h205: hip} built without a library record."""
    top=stage/('Arraytron_Stamp_v%s_Release'%VER);payload=top/'payload';payload.mkdir(parents=True)
    for f in ('Install Arraytron Stamp.cmd','Uninstall Arraytron Stamp.cmd','install.ps1'):shutil.copy2(ROOT/'installer_stamp'/f,top/f)
    shutil.copy2(ROOT/'INSTALL_STAMP.md',top/'INSTALL.md');shutil.copy2(ROOT/'CHANGELOG_STAMP.md',top/'CHANGELOG.md')
    for build,hda in (('h22',HDA22),('h205',HDA205)):
        (payload/build/'otls').mkdir(parents=True);shutil.copy2(hda,payload/build/'otls');(payload/build/'toolbar').mkdir();shutil.copy2(ROOT/'toolbar_stamp'/'arraytron_stamp.shelf',payload/build/'toolbar')
    (payload/'demos').mkdir();(payload/'demos_h205').mkdir()
    for hip in demos['h22'].parent.glob('*.hip'):shutil.copy2(hip,payload/'demos')                       # the demo and the Paint Falloff demo
    for hip in demos['h205'].parent.glob('*.hip'):shutil.copy2(hip,payload/'demos_h205')
    (payload/'docs').mkdir();shutil.copy2(ROOT/'docs'/'ARRAYTRON_STAMP.md',payload/'docs')
    pdf=ROOT/'docs'/'guide'/('Arraytron_Stamp_Guide_%s.pdf'%VER)
    if pdf.is_file():shutil.copy2(pdf,top/'Arraytron_Stamp_Guide.pdf')                  # the PDF guide travels with the package (RAR and update zip: about 2.5 MB)
    shutil.copy2(ROOT/'INSTALL_STAMP.md',payload/'INSTALL.md');shutil.copy2(ROOT/'CHANGELOG_STAMP.md',payload/'CHANGELOG.md')
    (payload/'updater').mkdir()
    for f in ('stamp_update.py','stamp_update_ui.py'):shutil.copy2(ROOT/'src'/f,payload/'updater'/f)
    (payload/'icon').mkdir();shutil.copy2(ROOT/'icon'/'Arraytron-Stamp.svg',payload/'icon')
    if update_source:(payload/'update_source.txt').write_text(update_source.strip()+'\n',encoding='utf8')
    (payload/'VERSION.json').write_text(json.dumps({'version':VER,'name':'Arraytron Stamp','houdini':HOUDINI,
        'builds':[{'folder':'h22','min':'22.0','max_exclusive':'23.0','built_with':'22.0.368','tested':['22.0.368']},
                  {'folder':'h205','min':'20.5','max_exclusive':'22.0','built_with':'20.5.445','tested':['20.5.445','21.0.440']}]},indent=2),encoding='utf8')
    return top
def main():
    p=argparse.ArgumentParser(description=__doc__.split('\n')[0]);p.add_argument('--out',default=str(ROOT/'release'/'stamp'));p.add_argument('--update-source',default=DEFAULT_UPDATE_SOURCE);p.add_argument('--skip-verify',action='store_true');a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);rar=find_rar()
    for f in (HDA22,HDA205,ROOT/'icon'/'Arraytron-Stamp.svg',ROOT/'docs'/'ARRAYTRON_STAMP.md'):
        if not f.is_file():raise SystemExit('Missing %s: build the Stamp first (hython tools/build_stamp_light.py, with hython 22 and with hython 20.5).'%f)
    if not notes(VER):raise SystemExit('CHANGELOG_STAMP.md has no section "## %s" with bullets.'%VER)
    stage=Path(tempfile.mkdtemp(prefix='arraytron_stamp_release_'));demos={}
    for build,hython,name in (('h22',HYTHON,'Arraytron_Stamp_v%s_demo.hip'%VER),('h205',HYTHON205,'Arraytron_Stamp_v%s_H205_demo.hip'%VER)):
        folder=stage/('demo_'+build);run([str(hython),str(ROOT/'tools'/'build_demo_stamplite.py'),'--release',str(folder)],cwd=str(ROOT));demos[build]=folder/name
        run([str(hython),str(ROOT/'tools'/'build_demo_paintfalloff.py'),'--release',str(folder)],cwd=str(ROOT))
        run([str(hython),str(ROOT/'tools'/'build_demo_materials.py'),'--release',str(folder)],cwd=str(ROOT))
    for old in list(out.glob('*%s*'%VER)):old.unlink()
    top=build_package(stage,a.update_source,demos)
    release_rar=out/('Arraytron_Stamp_v%s_Release.rar'%VER)
    run([rar,'a','-r','-m5','-md128m','-rr3p','-idq','-y',str(release_rar),top.name],cwd=top.parent);run([rar,'t','-idq',str(release_rar)])
    zip_path=out/('Arraytron-Stamp-%s.zip'%VER)
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(top.rglob('*')):
            if f.is_file():z.write(f,f.relative_to(top.parent).as_posix())
    manifest={'name':'Arraytron Stamp','version':VER,'released':date.today().isoformat(),'zip':zip_path.name,'sha256':sha(zip_path),'size':zip_path.stat().st_size,'houdini':HOUDINI,'notes':notes(VER)}
    (out/'version.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('built %s (%.1f MB), %s (%.1f MB) and version.json'%(release_rar.name,release_rar.stat().st_size/1e6,zip_path.name,zip_path.stat().st_size/1e6))
    if not a.skip_verify:
        check=Path(tempfile.mkdtemp(prefix='arraytron_stamp_verify_'));run([rar,'x','-idq','-y',str(release_rar),str(check)+os.sep])
        r=run([sys.executable,str(ROOT/'tests'/'validate_stamp_installer.py'),str(check/top.name),str(out)],check=False);print(r.stdout.strip())
        if r.returncode!=0:print(r.stderr[-800:]);raise SystemExit('The installer validation failed (see above).')
        shutil.rmtree(check,ignore_errors=True)
    (out/'SHA256SUMS.txt').write_text('\n'.join('%s  %s'%(sha(f).upper(),f.name) for f in (release_rar,zip_path))+'\n',encoding='utf8')
    shutil.rmtree(stage,ignore_errors=True);print('release ready in',out)
if __name__=='__main__':main()
