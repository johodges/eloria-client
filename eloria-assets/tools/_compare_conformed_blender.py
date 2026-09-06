"""In-Blender half of `compare_conformed_piece.py`.  Not run directly."""
import bpy
import math
import sys

from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, YAW, POSE, WIDTH, DROP, LABELS = argv[:6]
YAW = float(YAW)
POSE = POSE == "1"
WIDTH = int(WIDTH)
DROP = [d for d in DROP.split(",") if d]
LABELS = LABELS.split(",") if LABELS else []
MODELS = argv[6:]

#: Where the generated meshes hang their arms, measured off the phoenix
#: cuirass and steady to a degree across the set: 11 degrees out from
#: vertical, 9 forward.  In Blender space, glTF +z (forward) is -y and
#: glTF +y (up) is +z.
DOWN_ARM = Vector((0.138, -0.162, -0.977)).normalized()

COLUMN = 1.30           # world units between columns
HEIGHT = 1.0            # every piece normalised to this tall

TRACKED = []


def load(path):
    """Import a GLB and return exactly the objects it brought.

    ``read_factory_settings`` is deferred in background Blender: the startup
    file is really read when the first operator runs, which is this import, so
    a purge before it does nothing and the default icosphere lands in the
    scene afterwards -- doubling every bounding box measured here.  The
    importer leaves its own objects selected, and that selection is the only
    trustworthy answer to "what did this file add".
    """
    bpy.ops.import_scene.gltf(filepath=path)
    got = list(bpy.context.selected_objects)
    for stray in list(bpy.data.objects):
        if stray not in got and stray not in TRACKED:
            bpy.data.objects.remove(stray, do_unlink=True)
    TRACKED.extend(got)
    print("loaded %s -> %s" % (path.rsplit("\\")[-1].rsplit("/")[-1],
                               [o.name for o in got]))
    return got


def drop_materials(objs):
    """Delete the faces of any material the caller asked to hide."""
    if not DROP:
        return
    import bmesh
    for obj in objs:
        if obj.type != "MESH":
            continue
        hide = {i for i, slot in enumerate(obj.material_slots)
                if slot.material and any(slot.material.name.endswith(d)
                                         for d in DROP)}
        if not hide:
            continue
        mesh = bmesh.new()
        mesh.from_mesh(obj.data)
        gone = [f for f in mesh.faces if f.material_index in hide]
        bmesh.ops.delete(mesh, geom=gone, context="FACES")
        mesh.to_mesh(obj.data)
        mesh.free()
        obj.data.update()


def bbox(objs):
    lo = Vector((1e9,) * 3)
    hi = Vector((-1e9,) * 3)
    deps = bpy.context.evaluated_depsgraph_get()
    for obj in objs:
        if obj.type != "MESH":
            continue
        ev = obj.evaluated_get(deps)
        for vert in ev.data.vertices:
            world = ev.matrix_world @ vert.co
            for axis in range(3):
                lo[axis] = min(lo[axis], world[axis])
                hi[axis] = max(hi[axis], world[axis])
    return lo, hi


def pose_arms(objs):
    """Swing the upper arms down to the angle the generated mesh hangs at.

    The rotation is built in armature space and pushed through
    ``bone.matrix_local``, the only form that survives the glTF importer's
    Y-up-to-Z-up conversion sitting on the object matrix.
    """
    arm = next((o for o in objs if o.type == "ARMATURE"), None)
    if arm is None:
        return
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    to_local = arm.matrix_world.inverted().to_3x3()
    for side, flip in (("l", 1.0), ("r", -1.0)):
        bone = arm.pose.bones.get("upperarm_%s" % side)
        if bone is None:
            continue
        rest = bone.bone.matrix_local
        head = rest.to_translation()
        have = (bone.bone.tail_local - bone.bone.head_local).normalized()
        want = (to_local @ Vector((DOWN_ARM.x * flip, DOWN_ARM.y,
                                   DOWN_ARM.z))).normalized()
        axis = have.cross(want)
        if axis.length < 1e-6:
            continue
        turn = Matrix.Rotation(
            math.acos(max(-1.0, min(1.0, have.dot(want)))), 4,
            axis.normalized())
        swing = Matrix.Translation(head) @ turn @ Matrix.Translation(-head)
        bone.matrix_basis = rest.inverted() @ swing @ rest
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()


def place(objs, x_at, index):
    lo, hi = bbox(objs)
    print("  bbox %s .. %s" % (tuple(round(v, 3) for v in lo),
                               tuple(round(v, 3) for v in hi)))
    scale = HEIGHT / max(hi[2] - lo[2], 1e-6)
    mid = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2,
                  (lo[2] + hi[2]) / 2))
    root = bpy.data.objects.new("column_%d" % index, None)
    bpy.context.collection.objects.link(root)
    TRACKED.append(root)
    for obj in objs:
        if obj.parent is None:
            obj.parent = root
    root.scale = (scale,) * 3
    root.location = (x_at - mid.x * scale, -mid.y * scale, -mid.z * scale)
    if YAW:
        pivot = (Matrix.Translation((x_at, 0, 0))
                 @ Matrix.Rotation(math.radians(YAW), 4, "Z")
                 @ Matrix.Translation((-x_at, 0, 0)))
        root.matrix_world = pivot @ root.matrix_world
    bpy.context.view_layer.update()


loaded = [load(path) for path in MODELS]
span = COLUMN * (len(loaded) - 1)
for index, objs in enumerate(loaded):
    drop_materials(objs)
    if POSE:
        pose_arms(objs)
    place(objs, index * COLUMN - span / 2.0, index)

camera_data = bpy.data.cameras.new("cam")
camera_data.type = "ORTHO"
camera_data.ortho_scale = COLUMN * len(loaded)
camera = bpy.data.objects.new("cam", camera_data)
bpy.context.collection.objects.link(camera)
camera.location = (0, -8, 0)
camera.rotation_euler = (math.radians(90), 0, 0)
bpy.context.scene.camera = camera

for direction, energy in (((-0.5, -1.0, 0.6), 4.0), ((0.9, -0.6, 0.2), 2.0),
                          ((0.0, 1.0, 0.3), 1.5)):
    data = bpy.data.lights.new("l", "SUN")
    data.energy = energy
    lamp = bpy.data.objects.new("l", data)
    bpy.context.collection.objects.link(lamp)
    lamp.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()

world = bpy.data.worlds.new("w")
bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (.07, .08, .09, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6

scene = bpy.context.scene
for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.resolution_x = WIDTH * len(loaded)
scene.render.resolution_y = int(WIDTH * 1.25)
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("  rendered %d column(s)" % len(loaded))
