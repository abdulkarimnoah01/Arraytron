import sys,hou,numpy as np
print(hou.applicationVersionString(),sys.version.split()[0],'numpy',np.__version__)
R='X:/Assets/HDAs/Arraytron/src/'
files=['arraytron_module.py','arraytron_physics.py','arraytron_scatter.py','arraytron_mask.py','arraytron_overlap.py','arraytron_grow.py','arraytron_paint.py','arraytron_fields.py','arraytron_cluster.py','arraytron_camera.py','arraytron_overrides.py','arraytron_finish.py']
text=''.join('\n\n'+open(R+f,encoding='utf8').read() for f in files)
ns={'__name__':'arraytron_module_test'}
try:
    exec(compile(text,'module','exec'),ns);print('module compiles and imports: OK, functions',len([k for k,v in ns.items() if callable(v)]))
except Exception as e:
    import traceback;traceback.print_exc()
m=type('M',(),ns)
import numpy as np
checks=[]
def t(name,f):
    try:f();checks.append((name,'ok'))
    except Exception as e:checks.append((name,'FAIL '+repr(e)[:150]))
t('frustum',lambda:ns['frustum_outside'](np.random.rand(10,3)-0.5,np.ones(10)*0.1,0.36,0.2,0.1,100))
t('falloff',lambda:ns['falloff_weight'](np.linspace(0,1,5),2))
t('paint codec',lambda:ns['paint_decode'](ns['paint_encode']({'pts':np.random.rand(5,7),'dab':1,'next':5})))
t('combine',lambda:ns['combine']([np.random.rand(5),np.random.rand(5)],[0,1]))
t('greedy',lambda:ns['greedy_remove'](np.random.rand(50,3),np.full(50,0.1),1.0,1))
t('tri_dist',lambda:ns['distance_to_triangles'](np.random.rand(5,3),np.random.rand(6,3,3),1.0,1))
t('quat',lambda:ns['euler_to_quat']((10,20,30)))
t('noise',lambda:ns['fbm_noise'](np.random.rand(20,3),1.0,np.zeros(3),3,0.5,1))
t('hash',lambda:ns['scatter_hash'](np.arange(10),3,1))
for c in checks:print(c)
