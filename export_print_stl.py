"""Export the verified model with millimeter STL coordinates and check its size."""
import bpy
import json
import struct
import numpy as np
from pathlib import Path

root = Path(__file__).resolve().parent
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
assert len(meshes) == 1
o = meshes[0]
assert 'Two extra right tufts' in o.get('Hair revision', '')
bpy.ops.object.select_all(action='DESELECT')
o.select_set(True)
bpy.context.view_layer.objects.active = o
output = root/'monster_138x30x100mm.stl'
# Mesh coordinates already represent millimeters; do not convert them to meters.
bpy.ops.wm.stl_export(filepath=str(output), check_existing=False,
    ascii_format=False, export_selected_objects=True, global_scale=1.0,
    use_scene_unit=False, forward_axis='Y', up_axis='Z', apply_modifiers=True)
with output.open('rb') as f:
    f.seek(80)
    count = struct.unpack('<I', f.read(4))[0]
dtype = np.dtype([('normal', '<f4', (3,)), ('vertices', '<f4', (3, 3)), ('attribute', '<u2')])
assert dtype.itemsize == 50 and output.stat().st_size == 84+count*50
records = np.memmap(output, dtype=dtype, mode='r', offset=84, shape=(count,))
minimum = records['vertices'].min(axis=(0, 1))
maximum = records['vertices'].max(axis=(0, 1))
dimensions = maximum-minimum
assert np.all(np.abs(dimensions-np.array([138, 30, 100])) < 0.001)
assert abs(minimum[2]) < 0.001
report = {'source': Path(bpy.data.filepath).name, 'stl': output.name, 'triangles': count,
          'dimensions_mm_width_depth_height': dimensions.tolist(),
          'bottom_z_mm': float(minimum[2]), 'bytes': output.stat().st_size}
(root/'stl_export_report.json').write_text(json.dumps(report, indent=2))
print('STL_EXPORT_VERIFIED='+json.dumps(report), flush=True)
