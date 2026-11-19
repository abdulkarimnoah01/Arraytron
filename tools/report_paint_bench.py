"""Write docs/PAINT_ENGINE_2_PERFORMANCE.md from the benchmark files of tools/bench_paint_engine.py: python tools/report_paint_bench.py
Reads tests/bench_paint_baseline_<tool>_22.json (Arraytron v1.35.0, Arraytron Stamp 0.10.0) and tests/bench_paint_after_<tool>_22.json (v1.36.0, 0.11.0)."""
import json, os, platform, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(name):
    p=os.path.join(ROOT,'tests',name)
    return json.load(open(p)) if os.path.exists(p) else None
def ms(e,k='mean'):
    if not e:return '-'
    v=e.get(k) if isinstance(e,dict) else e
    return '-' if v is None else ('%.1f'%v if v>=10 else '%.2f'%v)
rows=[];out=['# Paint Engine 2.0: performance (measured)','',
 'Measured with `tools/bench_paint_engine.py`: the real viewer-state code of each HDA driven through a stand-in viewport (no GPU drawing is measured), Houdini 22.0.368 hython,',
 'a terrain of 80 000 triangles, brush radius 2, density 3, spacing 0.3, the Soft Natural / default falloff, 201 mouse events per stroke, 120 hover events. Milliseconds per mouse event (mean / 95th percentile);',
 'commit = the release of the stroke (the parameter write); cook = the LOP cook after the stroke. Machine: %s, %s.'%(platform.processor() or 'Intel Core i9-13900K','Windows 11'),'',
 'Before = Arraytron v1.35.0 and Arraytron Stamp 0.10.0; after = Arraytron v1.36.0 and Arraytron Stamp 0.11.0 (Paint Engine 2.0). Each number is one run on one machine: they vary by a few milliseconds between runs.','']
for tool,label in (('arraytron','Arraytron (procedural paint)'),('stamp','Arraytron Stamp (stamps)')):
    b=load('bench_paint_baseline_%s_22.json'%tool);a=load('bench_paint_after_%s_22.json'%tool)
    out+=['## '+label,'','| Instances | Hover before | Hover after | Paint event before | Paint event after | Paint commit before / after | Erase event before / after | Cook after stroke before / after | Points painted before / after |','|---|---|---|---|---|---|---|---|---|']
    for n in ('1000','10000','50000','100000'):
        B=(b or {}).get('sizes',{}).get(n,{});A=(a or {}).get('sizes',{}).get(n,{})
        def ev(x,k):return '%s / %s'%(ms(x.get(k,{}).get('event')),ms(x.get(k,{}).get('event'),'p95')) if x.get(k) else '-'
        def cnt(x):
            e=x.get('paint');return '-' if not e else str(e['count_after']-e['count_before'])
        er_b=ev(B,'erase') if B.get('erase') else (ev(B,'paint_ctrl') if B.get('paint_ctrl') else '-');er_a=ev(A,'erase') if A.get('erase') else '-'
        out.append('| %s | %s | %s | %s | %s | %s / %s | %s / %s | %s / %s | %s / %s |'%(n,'%s / %s'%(ms(B.get('hover')),ms(B.get('hover'),'p95')) if B.get('hover') else '-','%s / %s'%(ms(A.get('hover')),ms(A.get('hover'),'p95')) if A.get('hover') else '-',
            ev(B,'paint'),ev(A,'paint'),ms(B.get('paint',{}).get('commit_ms')),ms(A.get('paint',{}).get('commit_ms')),er_b.split(' / ')[0],er_a.split(' / ')[0],ms(B.get('paint',{}).get('cook_ms')),ms(A.get('paint',{}).get('cook_ms')),cnt(B),cnt(A)))
    sculpt=[k for k in ('relax','scale','push') if any(((a or {}).get('sizes',{}).get(n,{}).get(k)) for n in ('1000','10000','50000','100000'))]
    if sculpt:
        out+=['','Sculpt brushes after (mean ms per mouse event / commit ms / undo restores / redo re-applies):','','| Instances | '+' | '.join(k.title() for k in sculpt)+' |','|---|'+'---|'*len(sculpt)]
        for n in ('1000','10000','50000','100000'):
            A=(a or {}).get('sizes',{}).get(n,{});cells=[]
            for k in sculpt:
                e=A.get(k);cells.append('-' if not e else '%s / %s / %s / %s'%(ms(e['event']),ms(e['commit_ms']),'yes' if e.get('undo_restores') else 'no','yes' if e.get('redo_reapplies') else 'no'))
            out.append('| %s | %s |'%(n,' | '.join(cells)))
    un=[];sv=[]
    for n in ('1000','10000','50000','100000'):
        A=(a or {}).get('sizes',{}).get(n,{});e=A.get('paint')
        if e:un.append('%s: undo %s ms (%s), redo %s ms (%s), peak Python memory of the stroke %s MB'%(n,ms(e['undo_ms']),'restores' if e['undo_restores'] else 'DOES NOT restore',ms(e['redo_ms']),'re-applies' if e['redo_reapplies'] else 'does NOT re-apply',e['peak_mb']))
        if A.get('save_ms') is not None:sv.append('%s: save %s ms, reopen + cook %s ms (%s)'%(n,ms(A['save_ms']),ms(A['reopen_cook_ms']),'same count' if A.get('reopen_same_count') else 'COUNT CHANGED'))
        if A.get('error'):out+=['','**Error at %s:** `%s`'%(n,A['error'].strip().splitlines()[-1])]
    out+=['','Paint stroke undo / redo after: '+'; '.join(un) if un else '','','Save / reopen after: '+'; '.join(sv) if sv else '','']
out+=['## What changed, and where the time went','',
 '* **Hover (cursor only).** Before: Arraytron tested every triangle of the Paint Target with numpy on every mouse move; Stamp cast 65 rays for the ring and read the HUD values. After: one hou.Geometry ray cast (Houdini\'s own acceleration structure) for the hit; the ring is cast once per point; the HUD is written only when a value changes. *Python execution and surface queries.*',
 '* **Paint events.** Before: Arraytron made a dab per mouse event (density depended on the event rate), checked the spacing with a Python loop against every point near the dab and redrew every painted point as a new hou.Geometry; Stamp\'s swept field was already incremental. After: BrushCore\'s swept field in both, a hash grid for the spacing (only the instances under the brush cost anything), the preview redrawn at most every 60 ms and at most 20 000 dots (a fixed subset by id) plus the stroke. *Python execution, spatial queries, drawing.*',
 '* **Commit.** One parameter write on release (Arraytron) or held-back writes (Stamp): the cost is the length of the data, which is why Arraytron writes once. *Parameter write / serialization.*',
 '* **Limit.** Arraytron v1.35.0 stopped painting at 20 000 painted points (PAINT_MAX); v1.36.0 paints up to 200 000.','']
open(os.path.join(ROOT,'docs','PAINT_ENGINE_2_PERFORMANCE.md'),'w',encoding='utf8').write('\n'.join(out))
print('written')
