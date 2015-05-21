import bpy
from math import pi
from mathutils import Euler
import itertools

bl_info = {
    "name": "Euler Filter",
    "author": "Manuel Odendahl",
    "version": (0, 1),
    "blender": (2, 74, 0),
    "location": "Search > Euler Filter",
    "description": "Euler Filter",
    "warning": "",
    "wiki_url": "http://",
    "tracker_url": "https://",
    "category": "Animation"
}

def get_fcu_keyframe_numbers(fcu):
    return sorted([p.co[0] for p in fcu.keyframe_points])


def get_selected_fcu_keyframe_numbers(fcu):
    return sorted([p.co[0] for p in fcu.keyframe_points if p.select_control_point])


def update_euler_keyframes(bone, keyframes):
    for kf in keyframes:
        bone.rotation_euler = kf["rotation_euler"]
        bone.keyframe_insert(data_path='rotation_euler', frame=kf["key"])


#################################################
# actual euler filter

def euler_to_string(e):
    return "%.2f, %.2f, %.2f" % (r(e[0]), r(e[1]), r(e[2]))


def degrees(a):
    return a / 360.0 * 2 * pi


def d(a):
    return degrees(a)


def r(a):
    return a / (2 * pi) * 360.0


def wrap_angle(a):
    return (a + pi) % (2 * pi) - pi


def euler_distance(e1, e2):
    return abs(e1[0] - e2[0]) + abs(e1[1] - e2[1]) + abs(e1[2] - e2[2])


def euler_axis_index(axis):
    if axis == 'X':
        return 0
    if axis == 'Y':
        return 1
    if axis == 'Z':
        return 2
    return None


def flip_euler(euler, rotation_mode):
    ret = euler.copy()
    inner_axis = rotation_mode[0]
    outer_axis = rotation_mode[2]
    middle_axis = rotation_mode[1]

    ret[euler_axis_index(inner_axis)] += pi
    ret[euler_axis_index(outer_axis)] += pi
    ret[euler_axis_index(middle_axis)] *= -1
    ret[euler_axis_index(middle_axis)] += pi
    return ret


def naive_flip_diff(a1, a2):
    while abs(a1 - a2) > pi:
        if a1 < a2:
            a2 -= 2 * pi
        else:
            a2 += 2 * pi

    return a2


def euler_filter(kfs, rotation_mode):
    if len(kfs) <= 1:
        return kfs
    prev = kfs[0]["rotation_euler"]
    ret = [{"key": kfs[0]["key"],
            "rotation_euler": prev.copy()}]
    for i in range(1, len(kfs)):
        e = kfs[i]["rotation_euler"].copy()
        e[0] = naive_flip_diff(prev[0], e[0])
        e[1] = naive_flip_diff(prev[1], e[1])
        e[2] = naive_flip_diff(prev[2], e[2])

        fe = flip_euler(e, rotation_mode)
        fe[0] = naive_flip_diff(prev[0], fe[0])
        fe[1] = naive_flip_diff(prev[1], fe[1])
        fe[2] = naive_flip_diff(prev[2], fe[2])

        de = euler_distance(prev, e)
        dfe = euler_distance(prev, fe)
        # print("distance: %s, flipped distance: %s" % (de, dfe))

        if dfe < de:
            e = fe
        prev = e
        ret += [{"key": kfs[i]["key"],
                 "rotation_euler": e}]
    return ret


#################################################
# keyframes / fcurves helpers

def split_data_path(data_path):
    """
    :param data_path: an FCurve data path
    :return: object path, property
    """
    return data_path.rsplit(".", 1)


# XXX when needed for rotation_mode
def get_bone_from_fcurve(obj, fcurve):
    """
    Resolve the path of a bone from the data_path of an fcurve
    :param obj: object the action belongs to (to resolve the fcurve data_path)
    :param fcurve: the fcurve
    :return: the resolved bone
    """
    bone, prop = split_data_path(fcurve.data_path)
    return obj.path_resolve(bone)


def get_selected_rotation_fcurves(context):
    """
    Returns the selected rotation euler curves.
    This checks that 3 curves for the same bone with property "rotation_euler" are selected,
    and that their array_index cover 0, 1, 2.
    :param context:
    :return: fcurves, error_string
    """
    obj = context.active_object
    if not obj:
        return None, "No object selected"
    if not obj.animation_data:
        return None, "Object have no animation data"
    if not obj.animation_data.action:
        return None, "Object has no action"
    fcurves = obj.animation_data.action.fcurves

    selected_fcurves = []
    selected_bone = None

    for fc in fcurves:
        if not fc.select:
            continue

        bone, prop = split_data_path(fc.data_path)
        if prop != "rotation_euler":
            continue

        if not selected_bone:
            selected_bone = bone
        if bone != selected_bone:
            return None, "Only select the rotation of a single object"

        selected_fcurves.append(fc)

    if len(selected_fcurves) != 3:
        return None, "Select only XYZ rotation curves"

    selected_fcurves = sorted(selected_fcurves, key=lambda fcu: fcu.array_index)
    for i in range(3):
        if selected_fcurves[i].array_index != i:
            return None, "Wrong index for rotation curves, selected all 3 angles"

    return selected_fcurves, None


def get_selected_rotation_keyframes(context):
    """
    Returns the selected rotation keyframes.
    The keyframes are in the format {"key": frame, "rotation_euler": Euler}.
    If there is an error, keyframes, fcurves will be None, and error_string will be set to a descriptive string.
    :param context:
    :return: keyframes, fcurves, error_string
    """
    fcurves, error = get_selected_rotation_fcurves(context)
    if not fcurves or len(fcurves) != 3:
        return None, None, error

    fcu_keyframes = [get_selected_fcu_keyframe_numbers(fcu) for fcu in fcurves]
    if fcu_keyframes[0] != fcu_keyframes[1] or fcu_keyframes[1] != fcu_keyframes[2]:
        # XXX warn
        print("All 3 rotation angles need to be keyframed together")
        return None, None, "All 3 rotation angles need to be keyframed together on every keyframe"

    keyframes = sorted(set(itertools.chain.from_iterable([get_selected_fcu_keyframe_numbers(fcu) for fcu in fcurves])))

    res = []
    for keyframe in keyframes:
        euler = Euler([fcurve.evaluate(keyframe) for fcurve in fcurves], 'XYZ')
        res += [{
            "key": keyframe,
            "rotation_euler": euler,
        }]

    return res, fcurves, None


def refresh_fcurve_editor(context):
    """
    Execute a meaningless command on F-Curve Editor which has the effect of
    refreshing the graph.

    From: http://blender.stackexchange.com/questions/7261/refresh-an-f-curve-with-python-after-changing-extrapolation-mode

    XXX Sadly selects all the values.
    """
    old_area_type = context.area.type
    context.area.type = 'GRAPH_EDITOR'
    bpy.ops.graph.clean(threshold=0)
    context.area.type = old_area_type

#################################################

# noinspection PyPep8Naming
class GRAPH_OT_EulerFilter(bpy.types.Operator):
    """Filter euler rotations to remove danger of gimbal lock.
    """

    bl_idname = "graph.euler_filter"
    bl_label = "Euler Filter"
    bl_description = "Filter euler rotations to remove danger of gimbal lock"
    bl_options = {'REGISTER', 'UNDO'}
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        fcus = get_selected_rotation_fcurves(context)
        return fcus

    def execute(self, context):
        kfs, fcus, error = get_selected_rotation_keyframes(context)
        if not kfs:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}

        bone = get_bone_from_fcurve(context.active_object, fcus[0])

        efs = euler_filter(kfs, bone.rotation_mode)

        for i in range(len(efs)):
            e = efs[i]["rotation_euler"]
            frame = efs[i]["key"]
            # p = kfs[i]["rotation_euler"]
            # print("%s -> %s" % (euler_to_string(p), euler_to_string(e)))
            for i in range(3):
                fcus[i].keyframe_points.insert(frame=frame, value=e[i])

        refresh_fcurve_editor(context)

        return {'FINISHED'}


#################################################

def register():
    bpy.utils.register_class(GRAPH_OT_EulerFilter)


def unregister():
    bpy.utils.unregister_class(GRAPH_OT_EulerFilter)


if __name__ == "__main__":
    register()

#################################################

def test():
    def get_euler_keyframes(action, bone=None):
        if bone:
            data_path = bone.path_from_id() + ".rotation_euler"
            rotation_mode = bone.rotation_mode
        else:
            rotation_mode = "XYZ"
            data_path = "rotation_euler"
        fcurves = [get_fcurve_for_data_path(action, data_path, i) for i in range(0, 3)]

        keyframes = sorted(set(itertools.chain.from_iterable([get_fcu_keyframe_numbers(fcu) for fcu in fcurves])))

        res = []
        for keyframe in keyframes:
            euler = Euler([fcurve.evaluate(keyframe) for fcurve in fcurves], rotation_mode)
            res += [{
                "key": keyframe,
                "rotation_euler": euler,
            }]

        return res

    def get_fcurve_for_data_path(action, data_path, index):
        for fcu in action.fcurves:
            if fcu.data_path == data_path and fcu.array_index == index:
                return fcu
        return action.fcurves.new(data_path, index=index)

    scene = bpy.context.scene
    scene.frame_current = 1
    (scene.frame_start, scene.frame_end)

    action = bpy.data.actions["Action"]
    hector = bpy.data.objects['Hector_RIG_proxy']

    head = hector.pose.bones['Head_CTRL']

    kfs = get_euler_keyframes(action, head)

    efs = euler_filter(kfs)
    for i in range(len(efs)):
        e = efs[i]["rotation_euler"]
        p = kfs[i]["rotation_euler"]
        print("%s -> %s" % (euler_to_string(p), euler_to_string(e)))
