import bpy
import bmesh
from bpy.app.handlers import persistent
from typing import cast
import random

# console output
def write_to_python_console(message: str):
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'CONSOLE':
                # override
                with bpy.context.temp_override(window=window, screen=screen, area=area):
                    bpy.ops.console.scrollback_append(
                        text=str(message), 
                        type='OUTPUT'
                    )
                return

# [initialize] set edit-mode in selected mesh data
base_obj = bpy.data.objects.get("building")

if base_obj is None or base_obj.type != 'MESH':
    write_to_python_console("Error: Object 'building' not found.")
    raise RuntimeError("Required object 'building' is missing.") 

bpy.context.view_layer.objects.active = base_obj
if base_obj.mode != 'EDIT':
    bpy.ops.object.mode_set(mode='EDIT')

bm: bmesh.types.BMesh = bmesh.from_edit_mesh(cast(bpy.types.Mesh, base_obj.data))

# [initialize] set animated curve line
animated_obj = bpy.data.objects.get("animated_curve")
curve_data: bpy.types.Curve

if animated_obj is None:
    curve_data = bpy.data.curves.new(name="animated_curve_data", type='CURVE')
    curve_data.dimensions = '3D'
    
    animated_obj = bpy.data.objects.new("animated_curve", curve_data)
    bpy.context.collection.objects.link(animated_obj)
    
    polyline = curve_data.splines.new('POLY')
    polyline.points.add(1) 
else:
    curve_data = cast(bpy.types.Curve, animated_obj.data)
    polyline = curve_data.splines[0]

curve_data.fill_mode = 'FULL'  # fill mode
curve_data.bevel_depth = 0.02  # radius
curve_data.bevel_resolution = 4 # smooth

# set materials
mat_name = "Line_Material"
mat = bpy.data.materials.get(mat_name)

if mat is None:
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    node_emission = nodes.new(type='ShaderNodeEmission')
    node_emission.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0) # set white color
    node_emission.inputs['Strength'].default_value = 5.0 # strength

    node_output = nodes.new(type='ShaderNodeOutputMaterial')

    links.new(node_emission.outputs['Emission'], node_output.inputs['Surface'])

if not curve_data.materials:
    curve_data.materials.append(mat)

polyline.points[0].co = (0.0, 0.0, 0.0, 1.0)
polyline.points[1].co = (0.0, 0.0, 0.0, 1.0)


# [initialize] select start vert index randomly 
all_vertex = [v for v in bm.verts]
latest_vert = random.sample(all_vertex, k=1)[0]

# ------------------------ main process ------------------------------

@persistent
def my_frame_change_handler(scene):
    global latest_vert
    
    world_matrix = bpy.data.objects["building"].matrix_world
    
    bm.verts.ensure_lookup_table()
    origin_vert = latest_vert 
    
    adjacent_verts = [e.other_vert(origin_vert) for e in origin_vert.link_edges]

    if adjacent_verts:
        latest_vert = random.choice(adjacent_verts)
    else:
        latest_vert = random.choice(bm.verts)
        write_to_python_console("Dead end! Warped to a new location.")

    p0 = world_matrix @ origin_vert.co
    p1 = world_matrix @ latest_vert.co

    polyline.points[0].co = (*p0, 1.0)
    polyline.points[1].co = (*p1, 1.0)
    
    write_to_python_console(f"Frame {scene.frame_current}: Moved from {origin_vert.index} to {latest_vert.index}")


# add handler
bpy.app.handlers.frame_change_post.clear()
bpy.app.handlers.frame_change_post.append(my_frame_change_handler)
