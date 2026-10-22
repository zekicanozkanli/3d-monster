"""Replace only the print mesh, preserving the user's saved scene and UI settings."""
import bpy
from pathlib import Path

root = Path(__file__).resolve().parent
o = next(o for o in bpy.data.objects if o.type == 'MESH')
original_materials = list(o.data.materials)
source = root/'monster.prepared.blend'
with bpy.data.libraries.load(str(source), link=False) as (available, loaded):
    loaded.objects = [name for name in available.objects if name.startswith('Monster — single print mesh')]
assert len(loaded.objects) == 1
incoming = loaded.objects[0]
o.data = incoming.data
o.data.materials.clear()
for material in original_materials:
    o.data.materials.append(material)
for key in incoming.keys():
    o[key] = incoming[key]
bpy.data.objects.remove(incoming, do_unlink=True)
notes = bpy.data.texts.get('PRINT_README')
notes.write('\nHair and hip update: two right-side tufts added to the leftmost head; the two right tufts on the second head from the left raised about 2 mm.\n'
            'Both enclosed hair voids are filled solid. Upper legs blend continuously into the torso.\n'
            'Dimensions remain 138 x 30 x 100 mm; recessed teeth retained.\n')
bpy.context.view_layer.objects.active = o
o.select_set(True)
bpy.context.view_layer.update()
assert o.data.library is None, 'The printable mesh must be local and self-contained'
bpy.ops.wm.save_as_mainfile(filepath=str(root/'monster.revised.blend'), compress=True)
print('MERGED_WITH_CURRENT_SCENE', list(o.dimensions), flush=True)
