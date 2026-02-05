import bpy
import bmesh
from bpy.app.handlers import persistent
from typing import cast, Dict, List, Set
import random

# --- シード値の設定 ---
# 複数のシードをリストで管理します
SEEDS = [42, 46]

def write_to_python_console(message: str):
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'CONSOLE':
                with bpy.context.temp_override(window=window, screen=screen, area=area):
                    bpy.ops.console.scrollback_append(text=str(message), type='OUTPUT')
                return

# --- 初期設定 ---
base_obj = bpy.data.objects.get("building")
if base_obj is None or base_obj.type != 'MESH':
    write_to_python_console("Error: Object 'building' not found.")
    raise RuntimeError("Missing 'building'")

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

# --- 状態管理の初期化 ---
# 複数のエージェントを保持するための辞書
# agents[seed] = {"latest": int, "visited": set, "random": RandomInstance}
agents = {}

def init_agents():
    global agents
    agents = {}
    for s in SEEDS:
        # シードごとに独立した乱数生成器（Randomインスタンス）を作成
        # これにより、一方の乱数消費がもう一方に影響を与えなくなります
        rng = random.Random(s)
        start_idx = rng.randrange(TOTAL_VERTS)
        agents[s] = {
            "latest": start_idx,
            "visited": {start_idx},
            "rng": rng,
            "spline_idx": -1 # 最新のスプラインを指す
        }

def start_new_path_for_agent(s, c_data, obj):
    """特定のエージェント（シード）に対して新しい線を開始する"""
    agent = agents[s]
    rng = agent["rng"]
    
    new_idx = rng.randrange(TOTAL_VERTS)
    agent["latest"] = new_idx
    agent["visited"] = {new_idx}
    
    polyline = c_data.splines.new('POLY')
    c_data.fill_mode = 'FULL'
    c_data.bevel_depth = 0.001 
    c_data.bevel_resolution = 2
    
    world_matrix = obj.matrix_world
    start_pos = world_matrix @ cast(bpy.types.Mesh, obj.data).vertices[new_idx].co
    polyline.points[0].co = (*start_pos, 1.0)
    
    # このエージェントが現在操作しているスプラインのインデックスを保存
    # (c_data.splines全体の中での位置)
    agent["spline_idx"] = len(c_data.splines) - 1

@persistent
def my_frame_change_handler(scene):
    global agents
    
    obj = bpy.data.objects.get("building")
    anim_obj = bpy.data.objects.get("animated_curve")
    if not obj or not anim_obj: return
    
    c_data = cast(bpy.types.Curve, anim_obj.data)
    
    # 1フレーム目（リセット時）
    if scene.frame_current <= scene.frame_start:
        c_data.splines.clear()
        init_agents()
        for s in SEEDS:
            start_new_path_for_agent(s, c_data, obj)
        return

    # 全エージェントを1歩ずつ進める
    mesh = cast(bpy.types.Mesh, obj.data)
    world_matrix = obj.matrix_world

    for s in SEEDS:
        agent = agents[s]
        rng = agent["rng"]
        
        # 自身が担当するスプラインを取得
        if agent["spline_idx"] >= len(c_data.splines): continue
        poly = c_data.splines[agent["spline_idx"]]

        # 頂点数上限
        if len(poly.points) >= 500:
            start_new_path_for_agent(s, c_data, obj)
            continue

        curr_idx = agent["latest"]
        adj_indices = ADJACENCY_MAP.get(curr_idx, [])
        unvisited_adj = [i for i in adj_indices if i not in agent["visited"]]
        
        if unvisited_adj:
            next_idx = rng.choice(unvisited_adj)
            agent["latest"] = next_idx
            agent["visited"].add(next_idx)
            
            poly.points.add(1)
            new_p_idx = len(poly.points) - 1
            
            next_pos = world_matrix @ mesh.vertices[next_idx].co
            poly.points[new_p_idx].co = (*next_pos, 1.0)
        else:
            # 行き止まり
            start_new_path_for_agent(s, c_data, obj)

# 初期実行
init_agents()

bpy.app.handlers.frame_change_post.clear()
bpy.app.handlers.frame_change_post.append(my_frame_change_handler)