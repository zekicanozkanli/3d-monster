import bpy
import json
from pathlib import Path
from collections import deque
from mathutils import Vector
from mathutils.bvhtree import BVHTree

root = Path(__file__).resolve().parent
o = next(o for o in bpy.data.objects if o.type == 'MESH')
tree = BVHTree.FromObject(o, bpy.context.evaluated_depsgraph_get())
step = 0.12
results = {}
for name, (xmin, xmax, zmin, zmax) in {
    'second_head_from_left_right_hair': (-28, -13, 63, 91),
    'second_head_from_right_left_hair': (12, 30, 62, 93),
}.items():
    nx, nz = int((xmax-xmin)/step)+1, int((zmax-zmin)/step)+1
    empty = set()
    for ix in range(nx):
        for iz in range(nz):
            point = Vector((xmin+ix*step, -100, zmin+iz*step))
            if tree.ray_cast(point, Vector((0, 1, 0)))[0] is None:
                empty.add((ix, iz))
    holes = []
    while empty:
        seed = empty.pop()
        queue, component = deque([seed]), [seed]
        border = False
        while queue:
            ix, iz = queue.popleft()
            border |= ix in (0, nx-1) or iz in (0, nz-1)
            for p in ((ix-1, iz), (ix+1, iz), (ix, iz-1), (ix, iz+1)):
                if p in empty:
                    empty.remove(p)
                    queue.append(p)
                    component.append(p)
        if not border and len(component) >= 2:
            xs = [xmin+p[0]*step for p in component]
            zs = [zmin+p[1]*step for p in component]
            holes.append({'sample_count': len(component),
                          'center_xz_mm': [sum(xs)/len(xs), sum(zs)/len(zs)],
                          'bounds_xz_mm': [[min(xs), min(zs)], [max(xs), max(zs)]]})
    results[name] = holes
results['euler_characteristic'] = len(o.data.vertices)-len(o.data.edges)+len(o.data.polygons)
results['genus_if_one_closed_orientable_surface'] = (2-results['euler_characteristic'])/2
suffix = 'before' if 'before-hair' in bpy.data.filepath else 'after'
(root/('hair_voids_'+suffix+'.json')).write_text(json.dumps(results, indent=2))
print('HAIR_VOIDS='+json.dumps(results), flush=True)
