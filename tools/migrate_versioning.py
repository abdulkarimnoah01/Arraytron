# SUPERSEDED: this is the record of pass 1 (ad-hoc names -> zero-padded vMM.mm.pp). The ids were then changed to plain vM.m.p (tools/migrate_versioning_plain.py); this script is not meant to be run again.
"""One-off migration (2026-10-04) from the ad-hoc version names to vMM.mm.pp. Kept for the record; it is not idempotent.
Run with hython after tools/versions.py exists:  hython tools/migrate_versioning.py
LESSON (first attempt failed): a HIP stores its HDA's absolute library path. Loading an old hip after its HDA had been moved
left the nodes degraded, and saving that froze the damage (the HDA definition ended up Embedded and empty). The correct order,
used by the hip step below, is: keep the old HDA at its old path, load the hip, install the archive copy with
force_use_assets=True so the nodes switch to it, uninstall the old file, patch paths, save, and only then delete the old files.
- HDA files of v00.01.00 .. v00.02.01 are moved bit-for-bit to dist/archive/ under their new names (their internal type
  names are unchanged, so scenes built with them still load).
- Their demo HIPs are loaded, their $HIP asset/render paths patched for the archive folder, and saved under the new names.
- USD exports, render previews and test evidence files are renamed; JSON evidence paths are updated.
- v00.03.00 and v00.03.05 were rebuilt from the registry-aware builders beforehand; their old files are removed."""
from pathlib import Path
import json, os, re, shutil, sys
import hou
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions as V
DIST,ARCH,REN,TESTS=V.DIST,V.ARCHIVE,V.RENDERS,ROOT/'tests'
ARCH.mkdir(exist_ok=True)

# (new id) -> old HDA file, [(old hip, kind)], [(old usd, new usd name)]
OLD={
 'v00.01.00':('Arraytron_v0.1.hda',[('Arraytron_v0.1_demo.hip',''),('Arraytron_transform_demo.hip','transform')],
              [('line_render.usda','Arraytron_v00.01.00_line_render.usda'),('demo_render.usda','Arraytron_v00.01.00_demo_render.usda'),('transform_demo_render.usda','Arraytron_v00.01.00_transform_demo_render.usda')]),
 'v00.01.05':('Arraytron_v0.15.hda',[('Arraytron_v0.15_demo.hip','')],[('v015_demo_render.usda','Arraytron_v00.01.05_demo_render.usda')]),
 'v00.01.06':('Arraytron_v0.16.hda',[('Arraytron_v0.16_demo.hip','')],[('v016_demo_render.usda','Arraytron_v00.01.06_demo_render.usda')]),
 'v00.02.00':('Arraytron_v0.2.hda',[('Arraytron_v0.2_demo.hip','')],[('v02_demo_render.usda','Arraytron_v00.02.00_demo_render.usda')]),
 'v00.02.01':('Arraytron_v0.21.hda',[('Arraytron_v0.21_demo.hip','')],[('v021_demo_render.usda','Arraytron_v00.02.01_demo_render.usda')]),
}
SUPERSEDED=['Arraytron_v0.3.hda','Arraytron_v0.3_demo.hip','v03_demo_render.usda','Arraytron_v0.35.hda','Arraytron_v0.35_demo.hip','v035_demo_render.usda']
# render base names: old -> new (extensions .exr .png .log follow)
RENDER_BASES={
 'arraytron_demo_xpu':'arraytron_v00.01.00_demo_xpu','demo_xpu':'arraytron_v00.01.00_demo_xpu',
 'arraytron_transform_demo_xpu':'arraytron_v00.01.00_transform_demo_xpu','transform_demo_xpu':'arraytron_v00.01.00_transform_demo_xpu',
 'line_xpu':'arraytron_v00.01.00_line_xpu','demo_without_area':'arraytron_v00.01.00_demo_without_area','rop_smoke':'arraytron_v00.01.00_rop_smoke',
 'arraytron_v015_demo_xpu':'arraytron_v00.01.05_demo_xpu','arraytron_v016_demo_xpu':'arraytron_v00.01.06_demo_xpu',
 'arraytron_v02_demo_xpu':'arraytron_v00.02.00_demo_xpu','arraytron_v021_demo_xpu':'arraytron_v00.02.01_demo_xpu',
 'scale_compare_on':'arraytron_v00.02.01_scale_compare_on','scale_compare_off':'arraytron_v00.02.01_scale_compare_off',
 'arraytron_v03_demo_xpu':'arraytron_v00.03.00_demo_xpu','arraytron_v035_demo_xpu':'arraytron_v00.03.05_demo_xpu',
}
TEST_JSON={'validation.json':'validation_v00.01.00.json','render_validation.json':'render_validation_v00.01.00.json','line_validation.json':'line_validation_v00.01.00.json',
 'rop_validation.json':'rop_validation_v00.01.00.json','validation_v015.json':'validation_v00.01.05.json','validation_v016.json':'validation_v00.01.06.json',
 'validation_v02.json':'validation_v00.02.00.json','validation_v021.json':'validation_v00.02.01.json','validation_v03.json':'validation_v00.03.00.json','validation_v035.json':'validation_v00.03.05.json'}

def move(src,dst):
    src,dst=Path(src),Path(dst)
    if not src.exists():print('  skip (missing)',src.name);return False
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(src),str(dst));print('  moved',src.relative_to(ROOT),'->',dst.relative_to(ROOT));return True

HIPS_ONLY='--hips-only' in sys.argv      # the other steps were already done by the first run
print('1. HDA files (copied; the old file is removed after the hips are migrated)');
if not HIPS_ONLY:
    for vid,(old_hda,_,_) in OLD.items():
        V.hda(vid).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DIST/old_hda,V.hda(vid));print('  copied',old_hda,'->',V.hda(vid).relative_to(ROOT))
print('2. demo HIPs')
def patch_paths(vid):
    old_to_new={k:v for k,v in RENDER_BASES.items()}
    changed=0
    for node in hou.node('/stage').children():
        for parm in node.parms():
            if parm.parmTemplate().type()!=hou.parmTemplateType.String:continue
            try:raw=parm.unexpandedString()
            except hou.Error:continue
            new=raw.replace('$HIP/test_assets','$HIP/../test_assets')
            m=re.search(r'\$HIP/\.\./renders/([^/]+?)\.(exr|png)$',new)
            if m and m.group(1) in old_to_new:
                new=f'$HIP/../../renders/{old_to_new[m.group(1)]}.{m.group(2)}'
            if new!=raw:parm.set(new);changed+=1
    return changed
def switch_library(vid):
    """Make every Arraytron node in the loaded hip use the archive copy of its HDA."""
    new=str(V.hda(vid)).replace('\\','/')
    hou.hda.installFile(new,force_use_assets=True)
    for node in hou.node('/stage').children():
        if node.type().name().startswith('arraytron::'):
            node.matchCurrentDefinition()
            lib=str(node.type().definition().libraryFilePath()).replace('\\','/')
            assert lib.lower()==new.lower(),('node still uses',lib,'not',new)
for vid,(old_hda,hips,_) in OLD.items():
    for old_hip,kind in hips:
        src=DIST/old_hip;dst=V.demo(vid,kind)
        hou.hipFile.load(str(src),suppress_save_prompt=True)          # old HDA is still at the path the hip recorded
        switch_library(vid)
        try:hou.hda.uninstallFile(str(DIST/old_hda).replace('\\','/'))
        except hou.Error as exc:print('  note: could not uninstall the old library:',exc)
        n=patch_paths(vid)
        hou.hipFile.save(str(dst))                                  # $HIP now points at the archive folder
        for node in hou.node('/stage').children():                  # prove the migrated stage still cooks
            if node.type().name().startswith('arraytron::'):assert node.stage() is not None and not node.errors(),(old_hip,node.name(),node.errors())
        hou.hipFile.clear(suppress_save_prompt=True)
        print('  saved',dst.relative_to(ROOT),'(',n,'path parms patched )')
for vid,(old_hda,hips,_) in OLD.items():                          # every hip of this version is done: drop the old files
    for old_hip,kind in hips:(DIST/old_hip).unlink(missing_ok=True)
    (DIST/old_hda).unlink(missing_ok=True)
print('  removed the old hips and HDA files')
if HIPS_ONLY:
    print('done (hips only)');sys.exit(0)
print('3. USD exports')
for vid,(_,_,usds) in OLD.items():
    for old,new in usds:move(DIST/old,ARCH/new)
print('4. superseded v0.3 / v0.35 files');
for name in SUPERSEDED:
    p=DIST/name
    if p.exists():p.unlink();print('  removed',name)
print('5. render previews')
for f in sorted(REN.iterdir()):
    stem,ext=f.stem,f.suffix
    if stem in RENDER_BASES and ext in ('.exr','.png','.log'):move(f,REN/(RENDER_BASES[stem]+ext))
print('6. test evidence')
move(TESTS/'demo_without_area.usda',TESTS/'Arraytron_v00.01.00_demo_without_area.usda')
for old,new in TEST_JSON.items():move(TESTS/old,TESTS/new)
PATHS=[('dist/line_render.usda','dist/archive/Arraytron_v00.01.00_line_render.usda'),('dist/demo_render.usda','dist/archive/Arraytron_v00.01.00_demo_render.usda'),
       ('dist/transform_demo_render.usda','dist/archive/Arraytron_v00.01.00_transform_demo_render.usda'),('tests/demo_without_area.usda','tests/Arraytron_v00.01.00_demo_without_area.usda')]
def fix(value):
    if not isinstance(value,str):return value
    v=value.replace('\\','/')
    for old,new in PATHS:v=v.replace(old,new)
    for old,new in RENDER_BASES.items():v=re.sub(r'renders/'+re.escape(old)+r'\.(exr|png|log)',lambda m:'renders/'+new+'.'+m.group(1),v)
    return v if v!=value.replace('\\','/') else value
def walk(x):
    if isinstance(x,dict):return {k:walk(v) for k,v in x.items()}
    if isinstance(x,list):return [walk(v) for v in x]
    return fix(x)
for name in ('render_validation_v00.01.00.json','line_validation_v00.01.00.json','rop_validation_v00.01.00.json','validation_v00.01.00.json'):
    p=TESTS/name
    if p.exists():p.write_text(json.dumps(walk(json.loads(p.read_text(encoding='utf-8'))),indent=2),encoding='utf-8')
print('done')
