"""One-off pass 2 (2026-10-04): zero-padded vMM.mm.pp ids -> plain vM.m.p ids (v00.03.05 -> v0.3.5). Not idempotent; kept as a record.
Run with hython: hython tools/migrate_versioning_plain.py
Uses the safe order learned in pass 1 (see tools/archive_release.py): a HIP records its HDA's absolute library path, so for each hip the
HDA is copied to its new name, the hip is loaded while the old HDA is still at the recorded path, the new copy is installed with
force_use_assets so the nodes switch to it, the old library is uninstalled, render paths are patched, the hip is saved under the new
name and its stage must cook. The two Prototype Bank releases (v0.3.0, v0.3.5) carry the padded id inside the HDA's help text, so they
are rebuilt from their builders afterwards instead of migrated; their old padded files are removed here."""
from pathlib import Path
import json, re, shutil, sys
import hou
ROOT=Path(__file__).resolve().parents[1]
DIST,ARCH,REN,TESTS=ROOT/'dist',ROOT/'dist/archive',ROOT/'renders',ROOT/'tests'
PAIRS=[('v00.01.00','v0.1.0'),('v00.01.05','v0.1.5'),('v00.01.06','v0.1.6'),('v00.02.00','v0.2.0'),('v00.02.01','v0.2.1'),('v00.03.00','v0.3.0'),('v00.03.05','v0.3.5')]
def plain(text):
    for old,new in PAIRS:text=text.replace(old,new)
    return text
def norm(p):return str(p).replace('\\','/')
MIGRATE=['v00.01.00','v00.01.05','v00.01.06','v00.02.00','v00.02.01']     # HDA bits are preserved; hips are migrated
REBUILD=['v00.03.00','v00.03.05']                                          # rebuilt from the builders afterwards

print('1. migrate HDAs and hips (safe order)')
for old_id in MIGRATE:
    new_id=plain(old_id);old_hda=ARCH/f'Arraytron_{old_id}.hda';new_hda=ARCH/f'Arraytron_{new_id}.hda'
    shutil.copy2(old_hda,new_hda)
    for old_hip in sorted(ARCH.glob(f'Arraytron_{old_id}_*demo.hip')):
        new_hip=ARCH/plain(old_hip.name)
        hou.hipFile.load(str(old_hip),suppress_save_prompt=True)              # the old HDA is still at the path the hip recorded
        hou.hda.installFile(norm(new_hda),force_use_assets=True)
        for node in hou.node('/stage').children():
            if node.type().name().startswith('arraytron::'):
                node.matchCurrentDefinition()
                assert norm(node.type().definition().libraryFilePath()).lower()==norm(new_hda).lower(),('still on the old library',node.path())
        try:hou.hda.uninstallFile(norm(old_hda))
        except hou.Error as exc:print('  note: could not uninstall',old_hda.name,exc)
        patched=0
        for node in hou.node('/stage').children():
            for parm in node.parms():
                if parm.parmTemplate().type()!=hou.parmTemplateType.String:continue
                try:raw=parm.unexpandedString()
                except hou.Error:continue
                new=plain(raw)
                if new!=raw:parm.set(new);patched+=1
        hou.hipFile.save(str(new_hip))
        for node in hou.node('/stage').children():
            if node.type().name().startswith('arraytron::'):assert node.stage() is not None and not node.errors(),(new_hip.name,node.name(),node.errors())
        hou.hipFile.clear(suppress_save_prompt=True);print('  saved',new_hip.relative_to(ROOT),f'({patched} render path parms patched, stage cooks)')
        old_hip.unlink()
    old_hda.unlink()
print('2. remove the padded v0.3.0 / v0.3.5 HDA, hips and USD (rebuilt next)')
for old_id in REBUILD:
    for pattern in (f'Arraytron_{old_id}.hda',f'Arraytron_{old_id}_*demo.hip'):
        for folder in (DIST,ARCH):
            for f in folder.glob(pattern):f.unlink();print('  removed',f.relative_to(ROOT))
print('3. rename the other files (USD exports, renders, test evidence)')
for folder in (DIST,ARCH,REN,TESTS):
    for f in sorted(folder.iterdir()):
        if f.is_file() and plain(f.name)!=f.name:
            dst=f.with_name(plain(f.name))
            if dst.exists():dst.unlink()
            f.rename(dst);print('  renamed',f.name,'->',dst.name)
print('4. evidence JSON: file names inside')
for f in TESTS.glob('*.json'):
    text=f.read_text(encoding='utf-8');new=plain(text)
    if new!=text:f.write_text(new,encoding='utf-8');print('  updated',f.name)
print('done')
