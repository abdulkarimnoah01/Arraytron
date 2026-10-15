"""Move a finished release from dist/ into dist/archive/ when a newer release becomes current.
Usage (hython):  hython tools/archive_release.py v0.3.5
Order of events when releasing the next version:
  1. Add the new id to tools/versions.py VERSIONS and set CURRENT to it.
  2. Build and validate the new release (its files go to dist/ because it is now CURRENT).
  3. Run this tool for the previous release. Its files are still in dist/ under their old locations.
What it does (and why the order matters): a HIP records its HDA's absolute library path and uses $HIP-relative asset and render
paths. So the HDA is copied to archive/ first, the HIP is loaded while the old HDA is still at the recorded path, the archive
copy is installed with force_use_assets so the nodes switch to it, the old library is uninstalled, the $HIP paths are patched for
the deeper folder, the HIP is saved in archive/, and only after the saved stage cooks cleanly are the old files removed.
Loading a HIP after moving its HDA degrades the nodes and saving freezes the damage (this happened once; see
tools/migrate_versioning.py)."""
from pathlib import Path
import re, shutil, sys
import hou
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions as V

def norm(p):return str(p).replace('\\','/')
def archive(vid):
    vid=V.resolve(vid)
    if vid==V.CURRENT:raise SystemExit(f'{vid} is the current release; set versions.CURRENT to the newer release first.')
    old_hda=V.DIST/f'Arraytron_{vid}.hda'
    if not old_hda.exists():raise SystemExit(f'{old_hda} not found: nothing to archive (already archived?)')
    V.ARCHIVE.mkdir(exist_ok=True)
    new_hda=V.hda(vid);shutil.copy2(old_hda,new_hda);print('copied',old_hda.name,'->',new_hda.relative_to(ROOT))
    hips=sorted(V.DIST.glob(f'Arraytron_{vid}_*demo.hip'))
    for old_hip in hips:
        hou.hipFile.load(str(old_hip),suppress_save_prompt=True)             # the old HDA is still at the path the HIP recorded
        hou.hda.installFile(norm(new_hda),force_use_assets=True)
        for node in hou.node('/stage').children():
            if node.type().name().startswith('arraytron::'):
                node.matchCurrentDefinition()
                assert norm(node.type().definition().libraryFilePath()).lower()==norm(new_hda).lower(),('node still uses the old library',node.path())
        try:hou.hda.uninstallFile(norm(old_hda))
        except hou.Error as exc:print('note: could not uninstall the old library:',exc)
        patched=0
        for node in hou.node('/stage').children():
            for parm in node.parms():
                if parm.parmTemplate().type()!=hou.parmTemplateType.String:continue
                try:raw=parm.unexpandedString()
                except hou.Error:continue
                new=raw.replace('$HIP/test_assets','$HIP/../test_assets').replace('$HIP/../renders/','$HIP/../../renders/')
                if new!=raw:parm.set(new);patched+=1
        dst=V.ARCHIVE/old_hip.name
        hou.hipFile.save(str(dst))
        for node in hou.node('/stage').children():
            if node.type().name().startswith('arraytron::'):assert node.stage() is not None and not node.errors(),(dst.name,node.name(),node.errors())
        hou.hipFile.clear(suppress_save_prompt=True);print('saved',dst.relative_to(ROOT),f'({patched} path parms patched, stage cooks)')
        old_hip.unlink()
    for usd in sorted(V.DIST.glob(f'Arraytron_{vid}_*render.usda')):shutil.move(str(usd),str(V.ARCHIVE/usd.name));print('moved',usd.name)
    old_hda.unlink();print('removed',old_hda.name)
    cache=V.DIST/'arraytron_cache'
    if cache.is_dir() and any(cache.iterdir()):                       # Physics Settle demos keep their frozen result in $HIP/arraytron_cache: the archived HIPs need a copy beside them
        shutil.copytree(cache,V.ARCHIVE/'arraytron_cache',dirs_exist_ok=True);print('copied arraytron_cache -> archive/arraytron_cache')
    print(f'{vid} archived. Update docs/VERSIONING.md and regenerate dist/manifest.json.')

if __name__=='__main__':
    archive(sys.argv[1] if len(sys.argv)>1 else (_ for _ in ()).throw(SystemExit(__doc__)))
