"""Recreate the supplied monster as one printable mesh using Blender's API."""
import bpy
import bmesh
import json
import math
import sys
from collections import deque
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from monster_reference import HEADS, NECK_PATHS_PX, PRINT_REQUIREMENTS

SCALE = 13.36  # image pixels per approximate millimeter, normalized at the end
parts = []


def pt(pixel, y=0):
    return Vector(((pixel[0] - 737) / SCALE, y, (1008 - pixel[1]) / SCALE))


def ellipsoid(name, center, radii, angle=0, segments=72, rings=48):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=center)
    o = bpy.context.object
    o.name = name
    o.scale = radii
    o.rotation_euler[1] = -angle
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    parts.append(o)
    return o


def catmull(points, n=64):
    result = []
    for j in range(n + 1):
        q = j / n * (len(points) - 1)
        i = min(int(q), len(points) - 2)
        t = q - i
        p0, p1 = points[max(0, i - 1)], points[i]
        p2, p3 = points[i + 1], points[min(len(points) - 1, i + 2)]
        result.append(0.5 * ((2*p1) + (-p0+p2)*t + (2*p0-5*p1+4*p2-p3)*t*t + (-p0+3*p1-3*p2+p3)*t*t*t))
    return result


def tube(name, points, radii, flatten=1, steps=96, sides=64):
    # Sweep in the image plane; local depth is the second ellipse axis.
    path = catmull([Vector(p) for p in points], steps)
    verts, faces = [], []
    for i, p in enumerate(path):
        q = i / steps * (len(radii)-1)
        k = min(int(q), len(radii)-2)
        u = q-k
        u = u*u*(3-2*u)
        radius = radii[k]*(1-u) + radii[k+1]*u
        tangent = path[min(i+1, steps)] - path[max(i-1, 0)]
        tangent.normalize()
        axis = tangent.cross(Vector((0, 1, 0))).normalized()
        depth = tangent.cross(axis).normalized()
        for j in range(sides):
            a = 2*math.pi*j/sides
            v = p + radius * (axis*math.cos(a) + depth*math.sin(a)*flatten)
            verts.append(tuple(v))
    for i in range(steps):
        for j in range(sides):
            a = i*sides+j
            b = i*sides+(j+1)%sides
            faces.append((a, b, b+sides, a+sides))
    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple(steps*sides+j for j in range(sides)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    o = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(o)
    parts.append(o)
    return o


def join(objects, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    return o


def apply(o, mod):
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=mod.name)


def remesh(o, size, smooth=2):
    mod = o.modifiers.new('Fuse sculpt volumes', 'REMESH')
    mod.mode = 'VOXEL'
    mod.voxel_size = size
    mod.adaptivity = 0
    mod.use_smooth_shade = True
    apply(o, mod)
    if smooth:
        mod = o.modifiers.new('Soften sculpt joins', 'SMOOTH')
        mod.factor = 0.65
        mod.iterations = smooth
        apply(o, mod)


def boolean(o, cutter, operation='DIFFERENCE'):
    mod = o.modifiers.new('Sculpt cavity', 'BOOLEAN')
    mod.operation = operation
    mod.solver = 'EXACT'
    mod.object = cutter
    apply(o, mod)
    bpy.data.objects.remove(cutter, do_unlink=True)


def cleanup(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(o.data)
    bm.free()
    for p in o.data.polygons:
        p.use_smooth = True


def remove_voxel_dust(o):
    """Remove only sub-0.1 mm isolated numerical remnants, never features."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    remaining = set(bm.verts)
    dust = []
    while remaining:
        seed = remaining.pop()
        stack, component = [seed], [seed]
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                w = e.other_vert(v)
                if w in remaining:
                    remaining.remove(w)
                    stack.append(w)
                    component.append(w)
        if len(component) <= 16:
            lo = Vector([min(v.co[k] for v in component) for k in range(3)])
            hi = Vector([max(v.co[k] for v in component) for k in range(3)])
            if (hi-lo).length < 0.1:
                dust.extend(component)
    if dust:
        print('Removed numerical voxel dust vertices:', len(dust), flush=True)
        bmesh.ops.delete(bm, geom=dust, context='VERTS')
        bm.to_mesh(o.data)
        o.data.update()
    bm.free()


def inspect(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    todo = set(bm.verts)
    components = []
    small_component_bounds = []
    while todo:
        seed = todo.pop()
        stack, count = [seed], 1
        component_verts = [seed]
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                w = e.other_vert(v)
                if w in todo:
                    todo.remove(w)
                    stack.append(w)
                    component_verts.append(w)
                    count += 1
        components.append(count)
        if count < 100000:
            small_component_bounds.append({
                'vertices': count,
                'min': [min(v.co[k] for v in component_verts) for k in range(3)],
                'max': [max(v.co[k] for v in component_verts) for k in range(3)],
            })
    result = {
        'vertices': len(bm.verts), 'faces': len(bm.faces),
        'euler_characteristic': len(bm.verts)-len(bm.edges)+len(bm.faces),
        'components': len(components), 'component_vertex_counts': sorted(components, reverse=True),
        'small_component_bounds': small_component_bounds,
        'non_manifold_edges': sum(not e.is_manifold for e in bm.edges),
        'boundary_edges': sum(e.is_boundary for e in bm.edges),
        'wire_edges': sum(e.is_wire for e in bm.edges),
        'volume_mm3': bm.calc_volume(signed=True),
        'dimensions_mm': list(o.dimensions),
        'lowest_z_mm': min((o.matrix_world @ v.co).z for v in bm.verts),
    }
    bm.free()
    return result


bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.001
scene.unit_settings.length_unit = 'MILLIMETERS'

# The torso and necks form the smooth five-way branching silhouette.
ellipsoid('Torso', pt((742, 758)), (11.8, 6.9, 14.6))
ellipsoid('Shoulders', pt((738, 644)), (12.0, 6.4, 8.7))
for name, pixels in NECK_PATHS_PX.items():
    radii = {
        'Left_Low': [6.2, 4.7, 4.0, 4.2],
        'Left_High': [6.0, 4.8, 4.0, 4.2],
        'Center': [5.8, 4.3, 3.9, 4.3],
        'Right_High': [6.0, 4.8, 3.8, 4.0],
        'Right_Low': [6.3, 4.7, 3.7, 3.8],
    }[name]
    tube('Neck_' + name, [pt((737, 740))] + [pt(p) for p in pixels],
         [4.5] + radii, flatten=0.94)

for h in HEADS:
    ax, ay = h['mouth_axis_px']
    angle = math.atan2(-ay, ax)
    h['angle'] = angle
    h['center'] = pt(h['center_px'])
    h['mouth_center'] = pt(h['mouth_center_px'], -6.2)
    rx, rz = [v/SCALE for v in h['radii_px']]
    # Depth inferred with the user's explicit authorization.
    ry = 6.4 if h['name'] != 'Center' else 6.1
    h['head_depth'] = ry
    ellipsoid('Head_' + h['name'], h['center'], (rx, ry, rz), angle)

# Paired legs, broad feet and individual rounded toes, with no added base.
for side in (-1, 1):
    tube('Leg', [(side*3.0, 0, 25), (side*7.5, 0, 19),
                 (side*10.4, 0, 12), (side*11.4, -0.2, 5.2)],
         [4.4, 6.0, 5.5, 5.7], flatten=0.98)
    ellipsoid('Foot', (side*12, -0.9, 3.8), (8.8, 6.7, 4.7))
    for j in range(4):
        x = side*12 + (j-1.5)*3.2
        center_factor = 1-abs(j-1.5)/2
        ellipsoid('Toe', (x, -5.2-1.5*center_factor, 2.9),
                  (2.05+0.35*center_factor, 3.1, 3.35))

# Blend the large forms before adding the thin hanging details.
monster = join(parts, 'Organic body and heads')
parts.clear()
print('STAGE organic body smoothing', flush=True)
remesh(monster, 0.22, smooth=130)
# Feathered smoothing only across the two hip junctions.
group = monster.vertex_groups.new(name='Hip transition blend')
buckets = {}
for v in monster.data.vertices:
    world = monster.matrix_world @ v.co
    q = ((abs(world.x)-10.0)/6.5)**2 + ((world.z-19.0)/7.0)**2
    if q < 1:
        w = (1-q)**2
        level = max(1, round(w*30))
        buckets.setdefault(level, []).append(v.index)
for level, indices in buckets.items():
    group.add(indices, level/30, 'REPLACE')
mod = monster.modifiers.new('Continuous leg to torso transition', 'SMOOTH')
mod.vertex_group = group.name
mod.factor = 0.8
mod.iterations = 110
apply(monster, mod)
hip_group = monster.vertex_groups.get('Hip transition blend')
if hip_group is not None:
    monster.vertex_groups.remove(hip_group)
parts.append(monster)

# The hanging soft prongs are traced individually rather than mirrored.
fin_paths = [
    # left lower head
    [(115, 591), (113, 644), (119, 698), (129, 736)],
    [(139, 612), (139, 670), (150, 723), (158, 749)],
    [(164, 621), (168, 670), (183, 710), (187, 720)],
    [(286, 473), (306, 501), (326, 534), (337, 540)],
    # left upper head
    [(331, 269), (319, 312), (323, 362), (334, 380)],
    [(350, 290), (341, 341), (346, 385), (358, 406)],
    [(378, 290), (369, 335), (376, 373), (381, 392)],
    [(529, 231), (540, 267), (548, 306), (546, 326)],
    [(512, 259), (517, 300), (526, 329), (529, 340)],
    # middle head
    [(634, 304), (610, 350), (603, 401), (608, 418)],
    [(639, 342), (624, 383), (624, 425), (631, 449)],
    [(660, 347), (648, 383), (650, 416), (654, 430)],
    [(839, 322), (856, 358), (855, 402), (846, 421)],
    [(821, 344), (833, 384), (826, 424), (816, 445)],
    [(801, 349), (811, 390), (802, 425), (795, 433)],
    # right upper head
    [(955, 224), (930, 258), (915, 306), (914, 326)],
    [(974, 251), (948, 295), (940, 337), (938, 351)],
    [(991, 267), (969, 301), (963, 321), (958, 329)],
    [(1135, 255), (1139, 295), (1130, 338), (1122, 354)],
    [(1114, 269), (1118, 313), (1105, 357), (1096, 378)],
    [(1095, 272), (1099, 306), (1089, 335), (1080, 349)],
    # right lower head
    [(1179, 370), (1156, 398), (1143, 425), (1144, 437)],
    [(1280, 505), (1270, 542), (1251, 579), (1244, 598)],
    [(1302, 510), (1297, 556), (1281, 601), (1273, 618)],
    [(1324, 508), (1325, 551), (1312, 593), (1301, 608)],
    # Two additional right-side tufts on the leftmost head.
    [(306, 455), (333, 500), (348, 544), (352, 565)],
    [(328, 465), (360, 512), (379, 554), (388, 576)],
]
for i, path in enumerate(fin_paths):
    # Bury the entire root cap in the nearest head, avoiding a cut-off shelf.
    head = min(HEADS, key=lambda h: sum((path[0][k]-h['center_px'][k])**2 for k in range(2)))
    hc = head['center_px']
    path = [(hc[0]+0.62*(path[0][0]-hc[0]), hc[1]+0.62*(path[0][1]-hc[1]))] + path[1:]
    if i in (7, 8):
        # Approximately 2 mm vertically in the final 100 mm-high model.
        path = [(x, y-18) for x, y in path]
    depth_profile = [-2.6, -4.3, -5.1, -5.2] if i >= 25 else [-1.9]*4
    tube('Hanging_prong_%02d' % i, [pt(p, y) for p, y in zip(path, depth_profile)],
         [1.35, 1.19, 0.94, 0.56], flatten=0.86, steps=48, sides=40)
    ellipsoid('Rounded prong tip', pt(path[-1], depth_profile[-1]), (0.57, 0.50, 0.62), segments=24, rings=16)

monster = join(parts, 'Monster — single print mesh')
parts.clear()
print('STAGE base fusion', flush=True)
remesh(monster, 0.14, smooth=6)


def find_hair_tunnels(o, pixel_box):
    """Find enclosed empty regions in the front projection of this hair group."""
    px0, px1, py0, py1 = pixel_box
    xmin, xmax = pt((px0, 0)).x, pt((px1, 0)).x
    zmin, zmax = pt((0, py1)).z, pt((0, py0)).z
    step = 0.08
    nx, nz = int((xmax-xmin)/step)+1, int((zmax-zmin)/step)+1
    tree = BVHTree.FromObject(o, bpy.context.evaluated_depsgraph_get())
    inverse = o.matrix_world.inverted()
    empty = set()
    for ix in range(nx):
        for iz in range(nz):
            origin = inverse @ Vector((xmin+ix*step, -100, zmin+iz*step))
            if tree.ray_cast(origin, Vector((0, 1, 0)))[0] is None:
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
            holes.append((min(xs), max(xs), min(zs), max(zs)))
    return holes


hair_regions = [(470, 575, 190, 370), (890, 1000, 200, 380)]
patches = []
for region in hair_regions:
    for xmin, xmax, zmin, zmax in find_hair_tunnels(monster, region):
        patches.append(ellipsoid('Solid hair repair',
            ((xmin+xmax)/2, -1.7, (zmin+zmax)/2),
            ((xmax-xmin)/2+0.50, 0.95, (zmax-zmin)/2+0.50),
            segments=48, rings=32))
print('STAGE hair tunnel patches', len(patches), flush=True)
if patches:
    monster = join([monster]+patches, 'Monster — single print mesh')
    remesh(monster, 0.14, smooth=8)
parts.clear()
for region in hair_regions:
    if find_hair_tunnels(monster, region):
        raise RuntimeError('A requested hair tunnel remains open')

# Cut the open space between legs and the five front-only mouth bowls.
# Freeze the uncut outer skin for a geometric tooth-placement check.
outer_skin = BVHTree.FromObject(monster, bpy.context.evaluated_depsgraph_get())
skin_matrix = monster.matrix_world.copy()
skin_inverse = skin_matrix.inverted()
arch = ellipsoid('Arch cutter', (0.1, 0, 0.3), (4.4, 16.0, 10.4), segments=64, rings=40)
boolean(monster, arch)
for h in HEADS:
    a, b = [v/SCALE for v in h['mouth_radii_px']]
    h['mouth_radii'] = a, b
    cutter = ellipsoid('Mouth cutter', h['mouth_center'], (a, 4.4, b), h['angle'], segments=64, rings=40)
    boolean(monster, cutter)
parts.clear()


def mouth_point(h, x, y, z):
    a = h['angle']
    c = h['mouth_center']
    return Vector((c.x + math.cos(a)*x - math.sin(a)*z,
                   y, c.z + math.sin(a)*x + math.cos(a)*z))


# Roots are buried behind the lip, and crowns emerge from the inner walls.
tooth_clearances = []
tooth_outside_skin = []
for index, h in enumerate(HEADS):
    a, b = h['mouth_radii']
    count_upper = [4, 4, 5, 5, 4][index]
    count_lower = [3, 4, 4, 4, 4][index]
    for upper, count in [(True, count_upper), (False, count_lower)]:
        for j in range(count):
            xn = -0.73 + 1.46*j/(count-1)
            x = xn*a
            sign = 1 if upper else -1
            zroot = sign*b*math.sqrt(1-xn*xn)*0.98
            length = (1.35 + 0.7*(1-abs(xn))) * (1 if upper else 0.94)
            length *= 1 + 0.10*math.sin(index*4+j*2)
            root = mouth_point(h, x, -2.35, zroot)
            mid = mouth_point(h, x*0.97, -3.30, zroot-sign*length*0.45)
            near_tip = mouth_point(h, x*0.91, -3.70, zroot-sign*length*0.88)
            tip = mouth_point(h, x*0.90, -3.75, zroot-sign*length)
            tooth = tube('Tooth', [root, mid, near_tip, tip], [0.72, 0.62, 0.44, 0.30],
                         steps=36, sides=24)
            for v in tooth.data.vertices:
                p = tooth.matrix_world @ v.co
                ray = skin_inverse @ Vector((p.x, -100, p.z))
                hit, normal, face, distance = outer_skin.ray_cast(ray, Vector((0, 1, 0)))
                if hit is None:
                    tooth_outside_skin.append((h['name'], upper, j))
                    continue
                front = skin_matrix @ hit
                clearance = p.y-front.y
                tooth_clearances.append(clearance)
                if clearance < 0.15:
                    tooth_outside_skin.append((h['name'], upper, j))
print('TOOTH_RECESS_CHECK', min(tooth_clearances), 'outside samples', len(tooth_outside_skin), flush=True)
if tooth_outside_skin:
    raise RuntimeError('Tooth geometry reached the outer lip surface: '+str(tooth_outside_skin[:8]))

monster = join([monster] + list(parts), 'Monster — single print mesh')
parts.clear()
print('STAGE final fusion', flush=True)
remesh(monster, 0.10, smooth=2)

# Plane-cut soles give two stable coplanar contact patches, not a pedestal.
cutter = ellipsoid('Unused', (0, 0, -1000), (1, 1, 1))
bpy.data.objects.remove(cutter, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, -49.3))
cutter = bpy.context.object
cutter.name = 'Sole plane cutter'
cutter.scale = (100, 100, 50)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
boolean(monster, cutter)
cleanup(monster)
remove_voxel_dust(monster)

# Apply the user's updated exact width, depth and height to the geometry.
coords = [monster.matrix_world @ v.co for v in monster.data.vertices]
lo = Vector(tuple(min(p[k] for p in coords) for k in range(3)))
hi = Vector(tuple(max(p[k] for p in coords) for k in range(3)))
target_dimensions = Vector(PRINT_REQUIREMENTS['exact_dimensions_mm'])
factors = Vector([target_dimensions[k]/(hi[k]-lo[k]) for k in range(3)])
center_x = (hi.x+lo.x)/2
center_y = (hi.y+lo.y)/2
for v in monster.data.vertices:
    world = monster.matrix_world @ v.co
    v.co = Vector(((world.x-center_x)*factors.x, (world.y-center_y)*factors.y, (world.z-lo.z)*factors.z))
monster.matrix_world = Matrix.Identity(4)
monster.data.update()
bpy.context.view_layer.update()
cleanup(monster)

clay = bpy.data.materials.new('Warm ivory clay')
clay.diffuse_color = (0.58, 0.51, 0.42, 1)
clay.use_nodes = True
shader = clay.node_tree.nodes.get('Principled BSDF')
shader.inputs['Base Color'].default_value = (0.58, 0.51, 0.42, 1)
shader.inputs['Roughness'].default_value = 0.83
ao = clay.node_tree.nodes.new('ShaderNodeAmbientOcclusion')
ao.inputs['Color'].default_value = (0.58, 0.51, 0.42, 1)
ao.inputs['Distance'].default_value = 4.0
ao.only_local = True
ao.samples = 16
clay.node_tree.links.new(ao.outputs['Color'], shader.inputs['Base Color'])
monster.data.materials.clear()
monster.data.materials.append(clay)

monster['Print object'] = True
monster['Size limit'] = 'Exact dimensions: 138 mm width x 30 mm depth x 100 mm height'
monster['Teeth'] = 'Recessed crowns with roots buried in inner mouth walls, behind the outer skin'
monster['Minimum tooth setback mm'] = min(tooth_clearances)*factors.y
monster['Construction'] = 'One fused solid mesh; front mouth recesses; rounded back; no base'
monster['Printing'] = 'Filament; supports permitted. Printer, nozzle and material are unknown.'
monster['Reference'] = 'User supplied image; back and depth inferred with user authorization'
monster['Fine features'] = 'Teeth and hanging-prong tips need slicer inspection for the chosen nozzle.'
monster['Hair revision'] = 'Two extra right tufts on leftmost head; second-left right pair raised about 2 mm; both hair tunnels filled'
monster['Hip revision'] = 'Leg roots embedded in torso, with feathered smoothing across hip transitions'

report = inspect(monster)
report['requirements'] = PRINT_REQUIREMENTS
report['tooth_samples_outside_outer_skin'] = len(tooth_outside_skin)
report['minimum_tooth_setback_mm'] = min(tooth_clearances)*factors.y
report['feature_notes'] = 'Closed mouth bowls, integrated teeth and prongs. Flat coplanar soles. Supports required for overhangs. Printer-specific process settings remain unknown.'
(ROOT/'mesh_report.json').write_text(json.dumps(report, indent=2))
print('MODEL_REPORT=' + json.dumps(report), flush=True)
if report['components'] != 1 or report['non_manifold_edges'] != 0 or report['volume_mm3'] <= 0 or report['euler_characteristic'] != 2:
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'monster.diagnostic.blend'))
    raise RuntimeError('Print mesh failed connected closed-volume check')
if any(abs(report['dimensions_mm'][k]-target_dimensions[k]) > 0.001 for k in range(3)) or abs(report['lowest_z_mm']) > 0.001:
    raise RuntimeError('Model failed size or bed alignment check')

# Keep only the printable mesh, camera and lamps in the saved scene.
world = bpy.data.worlds.new('Studio')
scene.world = world
world.use_nodes = True
world.node_tree.nodes.get('Background').inputs['Color'].default_value = (0.7, 0.66, 0.59, 1)
world.node_tree.nodes.get('Background').inputs['Strength'].default_value = 0.28


def aim(o, at):
    o.rotation_euler = (Vector(at)-o.location).to_track_quat('-Z', 'Y').to_euler()


for name, loc, energy, size in [
    ('Key softbox', (-91, -119, 175), 352800, 91),
    ('Fill softbox', (112, -56, 91), 58800, 98),
    ('Rim softbox', (14, 91, 147), 215600, 91),
]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size = energy, 'DISK', size
    o = bpy.data.objects.new(name, data)
    scene.collection.objects.link(o)
    o.location = loc
    aim(o, (0, 0, 50))

data = bpy.data.cameras.new('Inspection Camera')
camera = bpy.data.objects.new('Inspection Camera', data)
scene.collection.objects.link(camera)
scene.camera = camera
data.type = 'ORTHO'
data.ortho_scale = 155
data.lens = 50
data.clip_start, data.clip_end = 0.1, 1000
camera.location = (0, -308, 78)
aim(camera, (0, 0, 50))

scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 1400
scene.render.resolution_y = 1150
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'

bpy.ops.object.select_all(action='DESELECT')
monster.select_set(True)
bpy.context.view_layer.objects.active = monster
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.clip_start, space.clip_end = 0.05, 10000
            space.region_3d.view_distance = 201
            space.region_3d.view_location = (0, 0, 50)
            space.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            space.region_3d.view_perspective = 'ORTHO'
            space.overlay.show_floor = False

notes = bpy.data.texts.new('PRINT_README')
notes.write('Monster recreated from the supplied reference.\n'
            'Exact dimensions: 138 mm width x 30 mm depth x 100 mm height. Millimeter units.\n'
            'One closed connected mesh, no base. Teeth recessed behind the lips and rooted in the inner walls.\n'
            'Rounded unseen back/depth inferred with user approval; mouths are front recesses.\n'
            'Flat soles sit at Z=0. Supports allowed and needed for teeth and hanging features.\n'
            'Printer, nozzle and filament type are unknown: inspect thin tips and supports in your slicer.\n'
            'Select the Monster mesh when exporting; camera/lights are presentation objects.\n')
notes.write('Hair revision: two additional right tufts on the leftmost head; right pair on second-left head raised about 2 mm.\n'
            'Both enclosed hair voids filled; leg-to-torso transitions blended continuously.\n')
output = ROOT/'monster.prepared.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True)
scene.render.filepath = str(ROOT/'monster_front.png')
print('STAGE front render', flush=True)
bpy.ops.render.render(write_still=True)
camera.location = (189, -294, 133)
aim(camera, (0, 0, 50))
scene.render.filepath = str(ROOT/'monster_three_quarter.png')
print('STAGE three-quarter render', flush=True)
bpy.ops.render.render(write_still=True)
camera.location = (0, 308, 77)
aim(camera, (0, 0, 50))
scene.render.filepath = str(ROOT/'monster_back.png')
print('STAGE back render', flush=True)
bpy.ops.render.render(write_still=True)
# Close inspection of the central mouth from a shallow side angle.
camera.location = (9, -100, 76)
aim(camera, (0.8, 0, 74))
data.ortho_scale = 27
scene.render.resolution_x = 1200
scene.render.resolution_y = 1000
scene.render.filepath = str(ROOT/'monster_mouth_closeup.png')
print('STAGE mouth closeup render', flush=True)
bpy.ops.render.render(write_still=True)
print('BUILD_COMPLETE', flush=True)
