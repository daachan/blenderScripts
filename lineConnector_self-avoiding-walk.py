import bpy
import bmesh
from bpy.app.handlers import persistent
from typing import cast, Dict, List, Set
import random

def write_to_python_console(message: str):
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'CONSOLE':
                with bpy.context.temp_override(window=window, screen=screen, area=area):
                    bpy.ops.console.scrollback_append(text=str(message), type='OUTPUT')
                return

# 初期設定 
base_obj = bpy.data.objects.get("building")
if base_obj is None or base_obj.type != 'MESH':
    write_to_python_console("Error: Object 'building' not found.")
    raise RuntimeError("Missing 'building'")

if base_obj.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

base_mesh = cast(bpy.types.Mesh, base_obj.data)

# 隣接情報のキャッシュ
bm_tmp = bmesh.new()
bm_tmp.from_mesh(base_mesh)
bm_tmp.verts.ensure_lookup_table()
ADJACENCY_MAP: Dict[int, List[int]] = {
    v.index: [e.other_vert(v).index for e in v.link_edges] 
    for v in bm_tmp.verts
}
TOTAL_VERTS = len(bm_tmp.verts)
bm_tmp.free()

# 状態管理変数
latest_vert_idx = random.randrange(TOTAL_VERTS)
visited_verts: Set[int] = {latest_vert_idx}

def reset_path(c_data, obj):
    """経路と履歴を完全にリセットする関数"""
    global latest_vert_idx, visited_verts
    
    latest_vert_idx = random.randrange(TOTAL_VERTS)
    visited_verts = {latest_vert_idx}
    
    c_data.splines.clear()
    polyline = c_data.splines.new('POLY')
    c_data.fill_mode = 'FULL'
    c_data.bevel_depth = 0.01
    
    world_matrix = obj.matrix_world
    start_pos = world_matrix @ cast(bpy.types.Mesh, obj.data).vertices[latest_vert_idx].co
    polyline.points[0].co = (*start_pos, 1.0)
    
    write_to_python_console("Path Reset: Restarting exploration...")

@persistent
def my_frame_change_handler(scene):
    global latest_vert_idx, visited_verts
    
    obj = bpy.data.objects.get("building")
    anim_obj = bpy.data.objects.get("animated_curve")
    if not obj or not anim_obj: return
    
    c_data = cast(bpy.types.Curve, anim_obj.data)
    
    # --- リセット条件の判定 ---
    
    # 1. 開始フレームに戻った場合
    is_start_frame = scene.frame_current <= scene.frame_start
    
    # 2. 頂点数が上限を超えた場合
    is_over_limit = False
    if c_data.splines and len(c_data.splines[0].points) >= 3000:
        is_over_limit = True
        write_to_python_console("Reset: Vertex limit (3000) reached.")

    # 条件のいずれかを満たせばリセット実行
    if is_start_frame or is_over_limit:
        reset_path(c_data, obj)
        return

    # --- 探索の更新 ---
    if not c_data.splines: return
    poly = c_data.splines[0]

    adj_indices = ADJACENCY_MAP.get(latest_vert_idx, [])
    unvisited_adj = [i for i in adj_indices if i not in visited_verts]
    
    if unvisited_adj:
        # 次の頂点を選択
        latest_vert_idx = random.choice(unvisited_adj)
        visited_verts.add(latest_vert_idx)
        
        # 線を伸ばす
        poly.points.add(1)
        new_idx = len(poly.points) - 1
        
        w_mat = obj.matrix_world
        next_pos = w_mat @ cast(bpy.types.Mesh, obj.data).vertices[latest_vert_idx].co
        poly.points[new_idx].co = (*next_pos, 1.0)
    else:
        # 3. 探索が行き止まりになった場合のリセット
        write_to_python_console(f"Reset: Stuck at vertex {latest_vert_idx}.")
        reset_path(c_data, obj)

# ハンドラー登録
bpy.app.handlers.frame_change_post.clear()
bpy.app.handlers.frame_change_post.append(my_frame_change_handler)