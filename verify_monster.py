"""Independent saved-file checks, and optional STL export, via Blender."""
import bpy
import bmesh
import numpy as np
import json
from pathlib import Path

root = Path(__file__).resolve().parent
objects = [o for o in bpy.data.objects if o.type == 'MESH']
assert len(objects) == 1, 'Expected exactly one printable mesh in the scene'
o = objects[0]
mesh = o.data
bm = bmesh.new()
bm.from_mesh(mesh)
nonmanifold = sum(not e.is_manifold for e in bm.edges)
degenerate = sum(f.calc_area() < 1e-10 for f in bm.faces)
signed_volume = bm.calc_volume(signed=True)
euler = len(bm.verts)-len(bm.edges)+len(bm.faces)
remaining = set(bm.verts)
component_counts = []
while remaining:
    stack = [remaining.pop()]
    count = 1
    while stack:
        v = stack.pop()
        for e in v.link_edges:
            w = e.other_vert(v)
            if w in remaining:
                remaining.remove(w)
                stack.append(w)
                count += 1
    component_counts.append(count)
bm.free()

vertices = np.empty(len(mesh.vertices)*3, dtype=np.float64)
mesh.vertices.foreach_get('co', vertices)
vertices = vertices.reshape(-1, 3)
mesh.calc_loop_triangles()
triangles = np.empty(len(mesh.loop_triangles)*3, dtype=np.int32)
mesh.loop_triangles.foreach_get('vertices', triangles)
triangles = triangles.reshape(-1, 3)
volume = 0.0
moment = np.zeros(3)
for start in range(0, len(triangles), 200000):
    tri = vertices[triangles[start:start+200000]]
    v = np.einsum('ij,ij->i', tri[:, 0], np.cross(tri[:, 1], tri[:, 2])) / 6
    volume += v.sum()
    moment += ((tri[:, 0]+tri[:, 1]+tri[:, 2])*v[:, None]/4).sum(axis=0)
centroid = moment / volume

contact = vertices[np.abs(vertices[:, 2]) < 1e-5]
points = sorted(set((float(p[0]), float(p[1])) for p in contact))

def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

lower, upper = [], []
for p in points:
    while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
        lower.pop()
    lower.append(p)
for p in reversed(points):
    while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
        upper.pop()
    upper.append(p)
hull = lower[:-1] + upper[:-1]
stable_solid = len(hull) >= 3 and all(cross(hull[i], hull[(i+1)%len(hull)], centroid[:2]) >= -1e-5 for i in range(len(hull)))
world_vertices = vertices @ np.array(o.matrix_world)[:3, :3].T + np.array(o.matrix_world)[:3, 3]
dimensions = world_vertices.max(axis=0)-world_vertices.min(axis=0)
unit_mm = bpy.context.scene.unit_settings.scale_length*1000
report = {
    'file': Path(bpy.data.filepath).name,
    'mesh_objects': len(objects),
    'connected_components': len(component_counts),
    'non_manifold_edges': nonmanifold,
    'degenerate_faces': degenerate,
    'euler_characteristic': euler,
    'triangles': len(triangles),
    'signed_volume_mm3': signed_volume*unit_mm**3,
    'dimensions_mm': (dimensions*unit_mm).tolist(),
    'bottom_z_mm': float(world_vertices[:, 2].min()*unit_mm),
    'coplanar_sole_vertices': len(contact),
    'left_sole_vertices': int((contact[:, 0] < -1).sum()),
    'right_sole_vertices': int((contact[:, 0] > 1).sum()),
    'uniform_solid_centroid_mm': (centroid*unit_mm).tolist(),
    'uniform_solid_centroid_over_feet': stable_solid,
    'scale_length': bpy.context.scene.unit_settings.scale_length,
    'tooth_minimum_setback_mm': o.get('Minimum tooth setback mm'),
    'tooth_construction': o.get('Teeth'),
    'limitations': 'Printer, nozzle and filament unknown. Slicer must choose supports, extrusion, infill and verify small tips. Solid-centroid check assumes uniform density.',
}
(root/'verification.json').write_text(json.dumps(report, indent=2))
print('VERIFICATION='+json.dumps(report), flush=True)
assert len(component_counts) == 1
assert nonmanifold == 0 and degenerate == 0 and signed_volume > 0
assert euler == 2, 'Expected no closed hair tunnels after repairs'
assert np.all(np.abs(dimensions*unit_mm-np.array([138, 30, 100])) < 0.001)
assert abs(world_vertices[:, 2].min()) < 1e-5
assert report['left_sole_vertices'] > 10 and report['right_sole_vertices'] > 10
assert stable_solid
assert o.get('Minimum tooth setback mm', 0) > 0
print('ALL_CHECKS_PASSED', flush=True)
