"""Louvain 社区检测"""
from ..models import GraphNode, GraphEdge


def detect_communities(nodes, edges):
    """使用 Louvain 算法检测社区，返回 node_id -> community_id 映射"""
    try:
        import community as community_louvain
        import networkx as nx
    except ImportError:
        # 回退: 简单的连通分量检测
        return _simple_communities(nodes, edges)

    G = nx.Graph()
    for node in nodes:
        G.add_node(node.id)
    for edge in edges:
        G.add_edge(edge.source, edge.target, weight=edge.weight)

    partition = community_louvain.best_partition(G, weight="weight")

    # 更新节点社区信息
    community_map = {}
    for node in nodes:
        node.community = partition.get(node.id, -1)
        community_map[node.id] = node.community

    return community_map


def _simple_communities(nodes, edges):
    """简单连通分量作为回退"""
    from collections import defaultdict

    # 并查集
    parent = {n.id: n.id for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for edge in edges:
        if edge.source in parent and edge.target in parent:
            union(edge.source, edge.target)

    # 分配社区 ID
    roots = {}
    community_id = 0
    community_map = {}
    for node in nodes:
        root = find(node.id)
        if root not in roots:
            roots[root] = community_id
            community_id += 1
        node.community = roots[root]
        community_map[node.id] = node.community

    return community_map


def compute_community_cohesion(nodes, edges):
    """计算每个社区的凝聚度 (intra-edge density)"""
    from collections import defaultdict

    communities = defaultdict(list)
    for node in nodes:
        communities[node.community].append(node.id)

    # 计算每个社区内的边数
    intra_edges = defaultdict(int)
    for edge in edges:
        s_comm = None
        t_comm = None
        for node in nodes:
            if node.id == edge.source:
                s_comm = node.community
            if node.id == edge.target:
                t_comm = node.community
        if s_comm is not None and t_comm is not None and s_comm == t_comm:
            intra_edges[s_comm] += 1

    cohesion = {}
    for cid, members in communities.items():
        n = len(members)
        max_edges = n * (n - 1) / 2
        if max_edges > 0:
            cohesion[cid] = intra_edges.get(cid, 0) / max_edges
        else:
            cohesion[cid] = 0.0

    return cohesion