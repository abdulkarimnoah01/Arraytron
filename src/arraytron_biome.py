# Biome (v1.15.0): Distribution Mode "Biome". Scatter on a terrain mesh by RULES: a table of biomes, every row with the conditions where it grows (elevation, slope, moisture, temperature, each a
# range with a soft edge), its own density, its own Prototype Mix (Prototype Bank rows with weights) and its own scale range. Every biome scatters its own stable candidates over the whole terrain; a
# candidate survives with the probability of its biome's WEIGHT at that spot (the product of the four condition weights), so the biomes thin out and blend smoothly at their borders (an ecotone) instead
# of ending on a hard line, and a higher density only ever adds points. The fields: elevation = the height, slope = the angle of the surface normal from up, moisture = a constant, noise, the distance
# to water (a mesh or curve prim) or an image, temperature = a base temperature lowered with the height (lapse rate), plus noise and a warm facing (aspect). Appended to the PythonModule after the
# Falloff module (uses surface_points, stage_surface, fbm_noise, read_image / planar_uv / sample_image, band / ramp, _prim_geometry, distance_to_triangles). The pure numpy functions are tested directly.
import re
import numpy as np

BIOME_STRIDE=1000000                 # id of candidate i of biome row k (1 based): (k - 1) * BIOME_STRIDE + i
BIOME_MAX_ROWS=32
BIOME_MAX_CANDIDATES=100000          # per biome
BIOME_STREAM=97
_BIOME_STATS={}

# ---------------------------------------------------------------- pure functions
def biome_parse_mix(text,enabled):
    """The Prototype Mix text as ([(bank row, weight)], [rejected words]): words 'row' or 'row:weight' separated by spaces, commas or semicolons; a row that is not enabled or a weight <= 0 is rejected."""
    pairs=[];bad=[];enabled=set(int(r) for r in enabled)
    for word in re.split(r'[\s,;]+',str(text).strip()):
        if not word:continue
        row,_,weight=word.partition(':')
        try:r=int(row);w=float(weight) if weight else 1.0
        except ValueError:bad.append(word);continue
        if r in enabled and w>0:pairs.append((r,w))
        else:bad.append(word)
    return pairs,bad

def biome_choose(ids,pairs,seed):
    """The Prototype Bank row of every id: a stable draw (hash of the id) against the cumulative weights of the mix."""
    rows=np.array([r for r,_ in pairs],dtype=np.int64);cum=np.cumsum([w for _,w in pairs]);u=scatter_hash(np.asarray(ids,dtype=np.int64),seed,BIOME_STREAM+1)*cum[-1]
    return rows[np.minimum(np.searchsorted(cum,u,side='right'),len(rows)-1)]

def biome_slope(normals):
    """Slope in degrees (0 flat, 90 a wall, more than 90 an overhang) from unit normals."""
    return np.degrees(np.arccos(np.clip(np.asarray(normals,dtype=np.float64)[:,1],-1.0,1.0)))

def biome_temperature(P,normals,base,base_height,lapse,noise_amount,noise_values,warm,warm_angle):
    """Temperature in degrees: base - lapse * (height - base height) / 100, plus noise_amount * (2 * noise - 1), plus the warm facing: warm * sin(slope) * cos(angle between the horizontal part of the
    normal and the direction `warm_angle` (degrees in the XZ plane from +X towards +Z)); zero on flat ground."""
    P=np.asarray(P,dtype=np.float64);n=np.asarray(normals,dtype=np.float64);t=base-lapse*(P[:,1]-base_height)/100.0+noise_amount*(2.0*np.asarray(noise_values,dtype=np.float64)-1.0)
    if warm!=0.0:
        h=np.linalg.norm(n[:,[0,2]],axis=1);a=np.radians(warm_angle);d=np.array([np.cos(a),np.sin(a)])
        facing=np.where(h>1e-9,(n[:,0]*d[0]+n[:,2]*d[1])/np.maximum(h,1e-12),0.0);t=t+warm*np.sin(np.radians(biome_slope(n)))*facing
    return t

def biome_effect(w,effect):
    """Blend a band weight with 1 by the effect of its condition: effect 1 is the band as it is, 0 ignores the condition (weight 1 everywhere), in between the condition only partly counts."""
    return 1.0-float(effect)*(1.0-np.asarray(w,dtype=np.float64))

def biome_weights(P,normals,moisture,temperature,row):
    """Weight in [0, 1] of one biome row at every point: the product of the elevation, slope, moisture and temperature bands (1 inside the range, a smoothstep to 0 over the edge outside it), each
    blended with 1 by its Effect (rows without an effect count as 1)."""
    return (biome_effect(band(P[:,1],row['h'][0],row['h'][1],row['h_edge']),row.get('h_effect',1.0))*biome_effect(band(biome_slope(normals),row['s'][0],row['s'][1],row['s_edge']),row.get('s_effect',1.0))
            *biome_effect(band(moisture,row['m'][0],row['m'][1],row['m_edge']),row.get('m_effect',1.0))*biome_effect(band(temperature,row['t'][0],row['t'][1],row['t_edge']),row.get('t_effect',1.0)))

# ---------------------------------------------------------------- the fields (Houdini side)
def biome_rows(asset):
    """The enabled biome rows as dicts: index (1 based), name, density, mix text, the four ranges with their edges and the scale range."""
    rows=[]
    for i in range(1,min(asset.evalParm('biomes'),BIOME_MAX_ROWS)+1):
        if not asset.evalParm('biome_on%d'%i):continue
        rows.append(dict(index=i,name=asset.evalParm('biome_name%d'%i).strip() or 'Biome %d'%i,density=asset.evalParm('biome_density%d'%i),mix=asset.evalParm('biome_mix%d'%i),
                         h=asset.evalParmTuple('biome_hrange%d'%i),h_edge=asset.evalParm('biome_hedge%d'%i),s=asset.evalParmTuple('biome_srange%d'%i),s_edge=asset.evalParm('biome_sedge%d'%i),
                         m=asset.evalParmTuple('biome_mrange%d'%i),m_edge=asset.evalParm('biome_medge%d'%i),t=asset.evalParmTuple('biome_trange%d'%i),t_edge=asset.evalParm('biome_tedge%d'%i),
                         scale=asset.evalParmTuple('biome_scale%d'%i),h_effect=asset.evalParm('biome_heffect%d'%i),s_effect=asset.evalParm('biome_seffect%d'%i),m_effect=asset.evalParm('biome_meffect%d'%i),t_effect=asset.evalParm('biome_teffect%d'%i),
                         layer=asset.evalParm('biome_layer%d'%i) if asset.parm('biome_layer%d'%i) is not None else 1,clear=asset.evalParm('biome_clear%d'%i) if asset.parm('biome_clear%d'%i) is not None else 0.0,
                         exclude=biome_parse_rows(asset.evalParm('biome_excl%d'%i)) if asset.parm('biome_excl%d'%i) is not None else ()))
    return rows

def biome_parse_rows(text):
    """Row numbers written in a text ('2 3', '2,3'): a tuple of ints (words that are not whole numbers are ignored)."""
    out=[]
    for word in re.split(r'[\s,;]+',str(text or '').strip()):
        if word.isdigit() and int(word) not in out:out.append(int(word))
    return tuple(out)

def biome_order(rows):
    """The order the biomes are placed in: a biome comes after everything that is above it. A biome on a lower layer (a bigger layer number) comes after the biomes on the layers above, and a biome
    that lists another in its Excludes Rows comes before it. Ties (and a cycle, which is broken) go by layer, then row number. Returns the rows in that order."""
    by_index={r['index']:r for r in rows}
    before={r['index']:set() for r in rows}                          # index -> the indices that must come first
    for q in rows:
        for r in rows:
            if q is not r and q['layer']<r['layer'] and q['clear']>0:before[r['index']].add(q['index'])
        for e in q['exclude']:
            if e in by_index and e!=q['index'] and q['clear']>0:before[e].add(q['index'])
    order=[];left=sorted(rows,key=lambda r:(r['layer'],r['index']))
    while left:
        ready=[r for r in left if not (before[r['index']]-{o['index'] for o in order})]
        pick=ready[0] if ready else left[0]                           # nothing is free: a cycle, the first by layer and row number goes
        order.append(pick);left=[r for r in left if r is not pick]
    return order

def biome_clear_keep(data,rows):
    """Layers and exclusion: a boolean mask of the points to keep. Rows are walked in biome_order; a point of a biome is dropped when it lies closer than Clearance x the scale of a surviving point
    of a biome that is above it (a smaller layer number) or that lists its row in Excludes Rows. Only the biomes above a row can remove its points, so adding a lower layer never moves the ones above."""
    n=len(data['ids']);keep=np.ones(n,dtype=bool)
    if n==0:return keep
    order=biome_order(rows);idx={r['index']:np.nonzero(data['biome']==r['index'])[0] for r in rows}
    for pos,r in enumerate(order):
        for q in order[:pos]:
            if q['clear']<=0 or not (q['layer']<r['layer'] or r['index'] in q['exclude']):continue
            qi=idx[q['index']];qi=qi[keep[qi]];ri=idx[r['index']];ri=ri[keep[ri]]
            if not len(qi) or not len(ri):continue
            radius=q['clear']*data['scale'][qi];pts=np.vstack([data['pos'][qi],data['pos'][ri]]);nq=len(qi)
            i,j=neighbor_pairs(pts,max(float(radius.max())*2.0,1e-9));sel=(i<nq)&(j>=nq);i=i[sel];j=j[sel]
            hit=np.linalg.norm(pts[i]-pts[j],axis=1)<radius[i];keep[ri[j[hit]-nq]]=False
    return keep


def biome_noise(asset,P,stream):
    """Fractal noise in [0, 1] stretched to use the whole range (fractal noise clusters around 0.5)."""
    n=fbm_noise(np.asarray(P,dtype=np.float64),asset.evalParm('biome_noise_freq'),np.zeros(3),3,0.5,asset.evalParm('biome_seed')+stream);return np.clip((n-0.5)*2.0+0.5,0.0,1.0)

def biome_moisture(asset,P):
    """Moisture in [0, 1] at every point: Constant, Noise, Distance To Water (1 at the water, 0 at the reach) or an Image (planar from above), plus a noise variation and a bias."""
    mode=asset.evalParm('biome_moist_mode');P=np.asarray(P,dtype=np.float64)
    if mode==0:m=np.full(len(P),float(asset.evalParm('biome_moist_const')))
    elif mode==1:m=biome_noise(asset,P,101)
    elif mode==2:
        path=asset.evalParm('biome_water').strip()
        if not path:raise hou.NodeError('Biome: the Water Prim is empty (Moisture: Distance To Water). Pick a mesh or curve prim.')
        tris,segs=_prim_geometry(asset,path);reach=max(asset.evalParm('biome_water_reach'),1e-6)
        d=np.minimum(distance_to_triangles(P,tris,reach,0),distance_to_triangles(P,segs,reach,0));m=1.0-ramp(d,0.0,reach)
    else:
        path=asset.evalParm('biome_moist_image').strip()
        if not path:raise hou.NodeError('Biome: the Moisture Image is empty.')
        path=hou.text.expandString(path)
        if not os.path.isfile(path):raise hou.NodeError('Biome: the moisture image %s does not exist.'%path)
        try:img=read_image(path,0)
        except ValueError as exc:raise hou.NodeError(str(exc))
        u,v=planar_uv(P,0,asset.evalParmTuple('biome_moist_center'),asset.evalParmTuple('biome_moist_size'));m=sample_image(img,u,v,2)
    amount=asset.evalParm('biome_moist_noise')
    if amount>0:m=m+(biome_noise(asset,P,102)-0.5)*2.0*amount
    return np.clip(m+asset.evalParm('biome_moist_bias'),0.0,1.0)

def biome_temperature_field(asset,P,normals):
    noise=biome_noise(asset,P,103) if asset.evalParm('biome_temp_noise')!=0 else np.zeros(len(P))
    return biome_temperature(P,normals,asset.evalParm('biome_temp'),asset.evalParm('biome_temp_h'),asset.evalParm('biome_lapse'),asset.evalParm('biome_temp_noise'),noise,asset.evalParm('biome_warm'),asset.evalParm('biome_warm_dir'))

def biome_points(asset):
    """Every surviving point of every biome: dict(pos (n,3), normal (n,3), align (n,4), ids, biome (1 based row), proto (Prototype Bank row), scale (n,), weight (n,)) and the statistics per row."""
    P,T,area,normals,vn=stage_surface(asset,'biome_prim');rows=biome_rows(asset);enabled=bank_rows(asset);seed=asset.evalParm('biome_seed');smooth=asset.evalParm('biome_normal')==1;total=float(area.sum())
    parts=[];stats=[]
    for r in rows:
        pairs,bad=biome_parse_mix(r['mix'],enabled)
        if not pairs:raise hou.NodeError("Biome '%s': the Prototype Mix names no enabled Prototype Bank row (write bank row numbers, for example '1 2:3 4:0.5')."%r['name'])
        count=int(min(round(r['density']*total/100.0),BIOME_MAX_CANDIDATES));rs=seed+r['index']*7919
        pos,n,quat=surface_points(P,T,area,normals,vn,count,rs,smooth,0.0,180.0,0.0,asset.evalParm('biome_align'));parts.append((r,pairs,bad,rs,pos,n,quat));stats.append(dict(name=r['name'],candidates=len(pos),kept=0,bad=bad))
    empty=dict(pos=np.zeros((0,3)),normal=np.zeros((0,3)),align=np.zeros((0,4)),ids=np.zeros(0,dtype=np.int64),biome=np.zeros(0,dtype=np.int64),proto=np.zeros(0,dtype=np.int64),scale=np.zeros(0),weight=np.zeros(0))
    if not parts or sum(len(p[4]) for p in parts)==0:return empty,stats
    allP=np.vstack([p[4] for p in parts]);allN=np.vstack([p[5] for p in parts]);moist=biome_moisture(asset,allP);temp=biome_temperature_field(asset,allP,allN);out={k:[] for k in empty};at=0
    for (r,pairs,bad,rs,pos,n,quat),st in zip(parts,stats):
        k=len(pos);sl=slice(at,at+k);at+=k
        if k==0:continue
        w=biome_weights(allP[sl],allN[sl],moist[sl],temp[sl],r);ids=np.arange(k,dtype=np.int64);keep=scatter_hash(ids,rs,BIOME_STREAM)<w;ids=ids[keep]
        if not len(ids):continue
        lo,hi=r['scale'];u=scatter_hash(ids,rs,BIOME_STREAM+2);st['kept']=len(ids)
        out['pos'].append(pos[keep]+n[keep]*asset.evalParm('biome_offset'));out['normal'].append(n[keep]);out['align'].append(quat[keep]);out['ids'].append((r['index']-1)*BIOME_STRIDE+ids)
        out['biome'].append(np.full(len(ids),r['index'],dtype=np.int64));out['proto'].append(biome_choose(ids,pairs,rs));out['scale'].append(lo+(hi-lo)*u);out['weight'].append(w[keep])
    data={k:(np.concatenate(v) if len(v) else empty[k]) if k not in ('pos','normal','align') else (np.vstack(v) if len(v) else empty[k]) for k,v in out.items()}
    if any(r['clear']>0 for r in rows):                                  # Layers and Exclusion (v1.19.0): rows above remove the points of the rows below that sit too close
        keep=biome_clear_keep(data,rows)
        for r,st in zip(rows,stats):st['cleared']=int(np.count_nonzero((data['biome']==r['index'])&~keep))
        data={k:v[keep] for k,v in data.items()}
        for r,st in zip(rows,stats):st['kept']=int(np.count_nonzero(data['biome']==r['index']))
    return data,stats

def sop_biome(geo,asset):
    """generate_biome: the points of every biome. The terrain normal alignment in p@align, the biome scale in v@srcscale, the Prototype Bank row of the mix in i@place_proto (the Prototype Assignment honours it), the biome row in i@biome."""
    data,stats=biome_points(asset);_BIOME_STATS[asset.path()]=stats;geo.clear()
    for name,default in (('id',0),('align',(0.0,0.0,0.0,1.0)),('srcscale',(1.0,1.0,1.0)),('place_proto',0),('biome',0)):geo.addAttrib(hou.attribType.Point,name,default)
    n=len(data['ids'])
    if not n:return
    geo.createPoints([tuple(v) for v in data['pos'].tolist()]);geo.setPointIntAttribValues('id',data['ids'].tolist());geo.setPointFloatAttribValues('align',data['align'].ravel().tolist())
    geo.setPointFloatAttribValues('srcscale',np.repeat(data['scale'],3).tolist());geo.setPointIntAttribValues('place_proto',data['proto'].tolist());geo.setPointIntAttribValues('biome',data['biome'].tolist())

def biome_info(asset):
    """Read-only text for the Biome section: the points of every biome after the last cook."""
    if asset.evalParm('mode')!=10:return 'Switch Distribution Mode to Biome.'
    if asset.evalParm('biomes')==0:return 'No biomes yet: add a row to the table below.'
    stats=_BIOME_STATS.get(asset.path())
    if not stats:return 'Cook the node to see the points of every biome.'
    lines=[]
    for s in stats:
        text='%s: %s of %s candidates'%(s['name'],format(s['kept'],','),format(s['candidates'],','))
        if s.get('cleared'):text+=', %s cleared by the layers above' % format(s['cleared'],',')
        if s['bad']:text+=' (ignored in the mix: %s)'%' '.join(s['bad'])
        lines.append(text)
    return '\n'.join(lines)
