import bpy
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parent
scene = bpy.context.scene
camera = scene.camera
scene.cycles.samples = 16
scene.render.resolution_x = 1000
scene.render.resolution_y = 1000
for material in bpy.data.materials:
    if material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == 'AMBIENT_OCCLUSION':
                node.samples = 8
for filename, location, target, width in [
    ('monster_leftmost_hair_detail.png', (-52, -160, 57), (-51, 0, 48), 43),
    ('monster_left_upper_hair_detail.png', (-32, -160, 85), (-32, 0, 81), 43),
    ('monster_right_upper_hair_detail.png', (34, -160, 85), (34, 0, 82), 43),
    ('monster_hip_detail.png', (35, -160, 42), (0, 0, 25), 65),
]:
    camera.location = location
    camera.rotation_euler = (Vector(target)-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = width
    scene.render.filepath = str(root/filename)
    bpy.ops.render.render(write_still=True)
    print('DETAIL_RENDERED', filename, flush=True)
