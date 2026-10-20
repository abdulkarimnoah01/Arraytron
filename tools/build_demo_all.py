"""Combine every v0.5.2 demo into ONE scene: hython tools/build_demo_all.py
Each demo's /stage network is copied as a separate chain (own network box, laid out in its own row) into dist/Arraytron_v0.5.2_all_demos.hip.
Only the chain of the first demo has its display flag on; click another chain's last node (display flag) to look at it."""
from pathlib import Path
import sys, hou, tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.BUILD;DEMOS=(('demo','Main'),('paint_demo','Paint (viewport brush)'),('paint_k_demo','Paint only: the letter K'),('fields_demo','Field Stack'),('cluster_demo','Clusters + Separation + Avoid Geometry'),('camera_demo','Camera + LOD + primvars'),('finish_demo','Overrides + Debug (v1.0)'),('falloff_demo','Falloff (scale and density)'),('place_demo','Instance Place (one at a time)'),('lodgen_demo','LOD generator (ladder + field)'),('imported_demo','Imported Points (FX sim)'),('grow_demo','Grow'),('mask_demo','Masks'),('overlap_demo','Separation (No Overlap)'),('physics_railway_demo','Physics Railway'),('physics_box_demo','Physics Box'))
tmp=Path(tempfile.mkdtemp());files=[];displays=[];objfiles=[]
for suffix,title in DEMOS:
    hou.hipFile.load(str(versions.demo_file(VID,suffix)),suppress_save_prompt=True,ignore_load_warnings=True)
    stage=hou.node('/stage');kids=stage.children();disp=[n.name() for n in kids if hasattr(n,"isDisplayFlagSet") and n.isDisplayFlagSet()]
    ob=hou.node('/obj');of=tmp/(suffix+'_obj.cpio');ok=bool(ob.children())
    if ok:ob.saveItemsToFile(ob.children(),str(of))
    objfiles.append(of if ok else None)
    f=tmp/(suffix+'.cpio');stage.saveItemsToFile(kids,str(f));files.append(f);displays.append(disp)
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID)
stage=hou.node('/stage');y=0.0;out=[]
for (suffix,title),f,disp,of in zip(DEMOS,files,displays,objfiles):
    if of:hou.node('/obj').loadItemsFromFile(str(of))
    before=set(stage.children());stage.loadItemsFromFile(str(f));new=[n for n in stage.children() if n not in before]
    # lay the chain out in its own row below the previous one
    stage.layoutChildren(new);top=max(n.position()[1] for n in new)
    for n in new:n.setPosition((n.position()[0],n.position()[1]-top-y))
    y=top-min(n.position()[1] for n in new)+y+4 if False else -min(n.position()[1] for n in new)+4
    box=stage.createNetworkBox('box_'+suffix);box.setComment(title+' demo')
    for n in new:box.addNode(n)
    box.fitAroundContents()
    for n in new:
        if hasattr(n,"setDisplayFlag"):n.setDisplayFlag(False)
    out.append((title,len(new)))
    if suffix==DEMOS[0][0]:
        for n in new:
            if hasattr(n,"setDisplayFlag") and (n.name() in disp or n.name().startswith(tuple(disp))):n.setDisplayFlag(True)
errs={n.path():n.errors() for n in stage.allSubChildren() if n.errors()}
hou.playbar.setFrameRange(1,240);hou.setFrame(1)
dst=versions.demo_file(VID,'all_demos');hou.hipFile.save(str(dst));print(out,errs,dst)
