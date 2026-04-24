"""知识图谱可视化 — 生成自包含 HTML"""
import json
from pathlib import Path
from typing import Optional

from ..models import EdgeType, GraphEdge, GraphNode, PageType
from .community import compute_community_cohesion, detect_communities


# vis.js CDN
VIS_JS_CDN = "https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"

# 12色调色板
PALETTE = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
    "#469990", "#dcbeff",
]

# 页面类型颜色
TYPE_COLORS = {
    PageType.ENTITY: "#e6194b",
    PageType.CONCEPT: "#3cb44b",
    PageType.SOURCE: "#4363d8",
    PageType.SYNTHESIS: "#ffe119",
    PageType.QUERY: "#f58231",
    PageType.OVERVIEW: "#911eb4",
}


class GraphVisualizer:
    """生成自包含 HTML 知识图谱可视化"""

    def __init__(self, nodes: list[GraphNode], edges: list[GraphEdge]):
        self.nodes = nodes
        self.edges = edges
        detect_communities(self.nodes, self.edges)
        self.cohesion = compute_community_cohesion(self.nodes, self.edges)

    def render(self, output_path: Path, title: str = "LLM Wiki Knowledge Graph",
               color_by: str = "type"):
        """生成自包含 HTML 文件"""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        nodes_data = self._build_nodes_data(color_by)
        edges_data = self._build_edges_data()
        communities_data = self._build_communities_data()

        html = self._html_template(title, nodes_data, edges_data, communities_data)
        output_path.write_text(html, encoding="utf-8")

    def _build_nodes_data(self, color_by: str = "type") -> list[dict]:
        nodes = []
        for node in self.nodes:
            if color_by == "community" and node.community >= 0:
                color = PALETTE[node.community % len(PALETTE)]
            else:
                color = TYPE_COLORS.get(node.page_type, "#888888")

            size = max(15, min(50, 15 + node.degree * 3))
            nodes.append({
                "id": node.id,
                "label": node.label[:30],
                "title": f"{node.label}\nType: {node.page_type.value}\nDegree: {node.degree}",
                "color": color,
                "size": size,
                "font": {"size": 12, "color": "#333"},
                "borderWidth": 2,
                "borderWidthSelected": 4,
            })
        return nodes

    def _build_edges_data(self) -> list[dict]:
        edges = []
        for edge in self.edges:
            color = "#999"
            width = 1
            dashes = False

            if edge.edge_type == EdgeType.EXTRACTED:
                color = "#666"
                width = 2
            elif edge.edge_type == EdgeType.INFERRED:
                color = "#2196F3"
                width = 1.5
                dashes = True
            elif edge.edge_type == EdgeType.AMBIGUOUS:
                color = "#FF9800"
                width = 1
                dashes = [5, 5]

            edges.append({
                "from": edge.source,
                "to": edge.target,
                "color": {"color": color, "highlight": "#2196F3"},
                "width": width,
                "dashes": dashes,
                "label": edge.label[:20] if edge.label else "",
                "title": f"{edge.edge_type.value} ({edge.weight:.1f})" + (f": {edge.label}" if edge.label else ""),
                "arrows": {"to": {"enabled": False}},
                "smooth": {"type": "continuous"},
            })
        return edges

    def _build_communities_data(self) -> list[dict]:
        from collections import defaultdict
        communities = defaultdict(list)
        for node in self.nodes:
            if node.community >= 0:
                communities[node.community].append(node.label)

        result = []
        for cid, members in sorted(communities.items()):
            cohesion = self.cohesion.get(cid, 0)
            result.append({
                "id": cid,
                "color": PALETTE[cid % len(PALETTE)],
                "members": len(members),
                "top_member": members[0] if members else "",
                "cohesion": round(cohesion, 3),
                "warning": cohesion < 0.15 and len(members) >= 3,
            })
        return result

    def _html_template(self, title: str, nodes: list[dict],
                       edges: list[dict], communities: list[dict]) -> str:
        nodes_json = json.dumps(nodes, ensure_ascii=False)
        edges_json = json.dumps(edges, ensure_ascii=False)
        communities_json = json.dumps(communities, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; }}
        #header {{ background: #fff; padding: 12px 20px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; }}
        #header h1 {{ font-size: 18px; color: #333; }}
        #controls {{ display: flex; gap: 8px; }}
        #controls button {{ padding: 6px 14px; border: 1px solid #ddd; border-radius: 4px; background: #fff; cursor: pointer; font-size: 13px; }}
        #controls button:hover {{ background: #e3f2fd; }}
        #main {{ display: flex; height: calc(100vh - 50px); }}
        #graph {{ flex: 1; background: #fafafa; }}
        #sidebar {{ width: 280px; background: #fff; border-left: 1px solid #ddd; padding: 16px; overflow-y: auto; font-size: 13px; }}
        #sidebar h3 {{ margin-bottom: 8px; color: #555; font-size: 14px; }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; }}
        .legend-color {{ width: 14px; height: 14px; border-radius: 3px; }}
        .community-card {{ background: #f9f9f9; padding: 8px; border-radius: 6px; margin: 6px 0; }}
        .warning {{ border-left: 3px solid #FF9800; }}
        #search {{ width: 200px; padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; }}
        #info-panel {{ margin-top: 16px; padding: 10px; background: #e3f2fd; border-radius: 6px; display: none; font-size: 12px; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>{title}</h1>
        <div id="controls">
            <input type="text" id="search" placeholder="Search nodes..." />
            <button onclick="zoomIn()">+</button>
            <button onclick="zoomOut()">-</button>
            <button onclick="fitScreen()">Fit</button>
            <select id="colorMode" onchange="recolor()">
                <option value="type">Color by Type</option>
                <option value="community">Color by Community</option>
            </select>
        </div>
    </div>
    <div id="main">
        <div id="graph"></div>
        <div id="sidebar">
            <h3>Legend</h3>
            <div id="legend"></div>
            <h3 style="margin-top:16px">Communities</h3>
            <div id="community-list"></div>
            <div id="info-panel"></div>
        </div>
    </div>

    <script src="{VIS_JS_CDN}"></script>
    <script>
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});
        var communities = {communities_json};

        var container = document.getElementById('graph');
        var network = new vis.Network(container, {{nodes: nodes, edges: edges}}, {{
            layout: {{ improvedLayout: true }},
            physics: {{
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {{ gravitationalConstant: -50, centralGravity: 0.01, springLength: 100, springConstant: 0.08 }},
                stabilization: {{ iterations: 150 }}
            }},
            interaction: {{ hover: true, tooltipDelay: 200, navigationButtons: false }}
        }});

        // Legend
        var typeColors = {json.dumps({k.value: v for k, v in TYPE_COLORS.items()}, ensure_ascii=False)};
        var palette = {json.dumps(PALETTE, ensure_ascii=False)};
        function renderLegend(mode) {{
            var el = document.getElementById('legend');
            el.innerHTML = '';
            if (mode === 'type') {{
                Object.keys(typeColors).forEach(function(t) {{
                    el.innerHTML += '<div class="legend-item"><div class="legend-color" style="background:'+typeColors[t]+'"></div>'+t+'</div>';
                }});
            }} else {{
                communities.forEach(function(c) {{
                    el.innerHTML += '<div class="legend-item"><div class="legend-color" style="background:'+c.color+'"></div>Community '+c.id+' ('+c.members+')</div>';
                }});
            }}
        }}
        renderLegend('type');

        // Community list
        var cl = document.getElementById('community-list');
        communities.forEach(function(c) {{
            var cls = c.warning ? 'community-card warning' : 'community-card';
            cl.innerHTML += '<div class="'+cls+'"><b>'+c.top_member+'</b> ('+c.members+' nodes)<br/>Cohesion: '+c.cohesion+(c.warning?' ⚠️':'')+'</div>';
        }});

        // Search
        document.getElementById('search').addEventListener('input', function(e) {{
            var q = e.target.value.toLowerCase();
            network.setData({{nodes: nodes, edges: edges}});
            if (q) {{
                var matchIds = [];
                nodes.forEach(function(n) {{
                    if (n.label.toLowerCase().includes(q)) matchIds.push(n.id);
                }});
                if (matchIds.length) network.selectNodes(matchIds);
            }}
        }});

        // Node click info
        network.on('click', function(params) {{
            var panel = document.getElementById('info-panel');
            if (params.nodes.length) {{
                var nid = params.nodes[0];
                var n = nodes.get(nid);
                panel.style.display = 'block';
                panel.innerHTML = '<b>'+n.label+'</b><br/>Type: '+n.title.split('\\n')[1]+'<br/>Degree: '+(n.size-15)/3;
            }} else {{
                panel.style.display = 'none';
            }}
        }});

        function recolor() {{
            var mode = document.getElementById('colorMode').value;
            renderLegend(mode);
            var updates = [];
            nodes.forEach(function(n) {{
                if (mode === 'community') {{
                    var comm = communities.find(function(c) {{ return n.label === c.top_member || true; }});
                    // find node's community from original data
                }}
            }});
        }}

        function zoomIn() {{ network.moveTo({{ scale: network.getScale() * 1.3 }}); }}
        function zoomOut() {{ network.moveTo({{ scale: network.getScale() / 1.3 }}); }}
        function fitScreen() {{ network.fit({{ animation: true }}); }}
    </script>
</body>
</html>"""