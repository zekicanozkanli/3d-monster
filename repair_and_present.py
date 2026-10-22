"""Finish the diagnostic sculpt after removing a tiny isolated voxel artifact."""
import bpy
import bmesh
import ast
import json
from mathutils import Vector
from pathlib import Path

ROOT = Path(__file__).resolve().parent
scene = bpy.context.scene
monster = next(o for o in bpy.data.objects if o.type == 'MESH')
source = (ROOT/'build_monster.py').read_text()
tree = ast.parse(source)
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {'remove_voxel_dust', 'inspect'}]
exec(compile(ast.Module(body=functions, type_ignores=[]), str(ROOT/'build_monster.py'), 'exec'))
remove_voxel_dust(monster)
report = inspect(monster)
report['requirements'] = json.loads((ROOT/'mesh_report.json').read_text())['requirements']
(ROOT/'mesh_report.json').write_text(json.dumps(report, indent=2))
print('REPAIRED_REPORT=' + json.dumps(report), flush=True)
assert report['components'] == 1 and report['non_manifold_edges'] == 0
exec(source[source.index('# Keep only the printable mesh'):])
