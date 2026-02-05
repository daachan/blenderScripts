import bpy
import bmesh
from bpy.app.handlers import persistent
from typing import cast, Dict, List
import random

def write_to_python_console(message: str):
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'CONSOLE':
                with bpy.context.temp_override(window=window, screen=screen, area=area):
                    bpy.ops.console.scrollback_append(text=str(message), type='OUTPUT')
                return

base_obj = bpy.data.objects.get("building")
if base_obj is None or base_obj.type != 'MESH':
    write_to_python_console("Please create base-mesh to generate line-connect animation, which named 'building'")
    raise RuntimeError("Required object 'building' is missing.")

if base_obj.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

base_mesh = cast(bpy.types.Mesh, base_obj.data)

bm_tmp = bmesh.new()
bm_tmp.from_mesh(base_mesh)
bm_tmp.verts.ensure_lookup_table()

ADJACENCY_MAP: Dict[int, List[int]] = {
    v.index: [e.other_vert(v).index for e in v.link_edges] 
    for v in bm_tmp.verts
}
TOTAL_VERTS = len(bm_tmp.verts)
bm_tmp.free()

animated_obj = bpy.data.objects.get("animated_curve")
curve_data: bpy.types.Curve

if animated_obj is None:
    curve_data = bpy.data.curves.new(name="animated_curve_data", type='CURVE')
    curve_data.dimensions = '3D'
    animated_obj = bpy.data.objects.new("animated_curve", curve_data)
    bpy.context.collection.objects.link(animated_obj)
else:
    curve_data = cast(bpy.types.Curve, animated_obj.data)

if not curve_data.splines:
    polyline = curve_data.splines.new('POLY')
    polyline.points.add(1)
else:
    polyline = curve_data.splines[0]

curve_data.fill_mode = 'FULL'
curve_data.bevel_depth = 0.01
curve_data.bevel_resolution = 4

mat_name = "Line_Material"
mat = bpy.data.materials.get(mat_name)
if mat is None:
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    node_emi = nodes.new(type='ShaderNodeEmission')
    node_emi.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    node_emi.inputs['Strength'].default_value = 10.0
    node_out = nodes.new(type='ShaderNodeOutputMaterial')
    mat.node_tree.links.new(node_emi.outputs['Emission'], node_out.inputs['Surface'])

if not any(m == mat for m in curve_data.materials):
    curve_data.materials.append(mat)

latest_vert_idx = random.randrange(TOTAL_VERTS)

@persistent
def my_frame_change_handler(scene):
    global latest_vert_idx
    
    obj = bpy.data.objects.get("building")
    if not obj: return
    
    mesh = cast(bpy.types.Mesh, obj.data)
    world_matrix = obj.matrix_world

    origin_idx = latest_vert_idx
    origin_pos = mesh.vertices[origin_idx].co.copy()
    
    adj_indices = ADJACENCY_MAP.get(origin_idx, [])
    
    if adj_indices:
        latest_vert_idx = random.choice(adj_indices)
    else:
        latest_vert_idx = random.randrange(TOTAL_VERTS)
        write_to_python_console("Dead end! Warped to a new location.")

    p0 = world_matrix @ origin_pos
    p1 = world_matrix @ mesh.vertices[latest_vert_idx].co.copy()

    polyline.points[0].co = (*p0, 1.0)
    polyline.points[1].co = (*p1, 1.0)
    
    write_to_python_console(f"Frame {scene.frame_current}: Moved from {origin_idx} to {latest_vert_idx}")

bpy.app.handlers.frame_change_post.clear()
bpy.app.handlers.frame_change_post.append(my_frame_change_handler)