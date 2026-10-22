"""Pack the supplied reference and leave a clean editing viewport."""
import bpy
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
from monster_reference import REFERENCE_IMAGE

reference = bpy.data.images.load(REFERENCE_IMAGE, check_existing=True)
reference.name = 'Original monster reference (packed)'
reference.use_fake_user = True
reference.pack()
for o in bpy.data.objects:
    if o.type in {'CAMERA', 'LIGHT'}:
        o.hide_set(True)
readme = bpy.data.texts.get('PRINT_README')
readme.use_fake_user = True
if 'The original reference image is packed' not in readme.as_string():
    readme.write('\nThe original reference image is packed in this file for further editing.\n')
bpy.ops.wm.save_as_mainfile(filepath=str(root/'monster.prepared.blend'), compress=True)
print('FINALIZED', flush=True)
