"""
Interactive Traffic Network Designer — toy prototype

Run:
    python3 traffic_tree_toy.py

Uses only the Python standard library (Tkinter).

Model:
- The road map is a rooted tree.
- Exactly one node is the Start (the root).
- Exactly one node is the End.
- Every non-root TreeNode stores the capacity of the road from its parent.
- Drag nodes to change the road geometry.
- Select a node to edit the incoming road capacity.
- Add/delete branches while preserving the tree structure.
- Move the unique End marker with "Set selected as End".
"""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk
from typing import Optional


@dataclass
class TreeNode:
    """One intersection in the road-network tree."""
    node_id: int
    name: str
    x: float
    y: float
    parent: Optional["TreeNode"] = None
    capacity_from_parent: float = 100.0
    children: list["TreeNode"] = field(default_factory=list)

    def add_child(self, child: "TreeNode") -> None:
        child.parent = self
        self.children.append(child)

    def remove_child(self, child: "TreeNode") -> None:
        self.children.remove(child)
        child.parent = None

    def contains(self, target: "TreeNode") -> bool:
        if self is target:
            return True
        return any(child.contains(target) for child in self.children)

    def path_from_root(self) -> list["TreeNode"]:
        path = []
        cur: Optional[TreeNode] = self
        while cur is not None:
            path.append(cur)
            cur = cur.parent
        path.reverse()
        return path


class TrafficTreeApp:
    NODE_RADIUS = 16

    def __init__(self, root_window: tk.Tk) -> None:
        self.root_window = root_window
        self.root_window.title("Interactive Traffic Network Designer — Tree Toy")
        self.root_window.geometry("1120x700")
        self.root_window.minsize(900, 600)

        self.next_id = 0
        self.start: TreeNode
        self.end: TreeNode
        self.selected: Optional[TreeNode] = None
        self.dragging: Optional[TreeNode] = None
        self.drag_dx = 0.0
        self.drag_dy = 0.0

        self.demand_var = tk.DoubleVar(value=80.0)
        self.capacity_var = tk.DoubleVar(value=100.0)
        self.status_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="")

        self._build_ui()
        self._build_initial_tree()
        self.selected = self.end
        self._sync_selected_controls()
        self.redraw()

    # ---------------------------
    # UI
    # ---------------------------

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root_window, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(main, width=250)
        controls.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Label(
            controls,
            text="Traffic Tree Toy",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            controls,
            text=(
                "Drag intersections directly on the map.\n"
                "Click a node to select it."
            ),
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(controls, text="Traffic demand").pack(anchor="w")
        demand_scale = ttk.Scale(
            controls,
            from_=10,
            to=180,
            variable=self.demand_var,
            command=lambda _value: self.redraw(),
        )
        demand_scale.pack(fill=tk.X, pady=(2, 2))
        self.demand_label = ttk.Label(controls)
        self.demand_label.pack(anchor="w", pady=(0, 14))

        ttk.Separator(controls).pack(fill=tk.X, pady=4)

        ttk.Label(
            controls,
            text="Selected incoming-road capacity",
        ).pack(anchor="w", pady=(8, 0))

        self.capacity_scale = ttk.Scale(
            controls,
            from_=20,
            to=200,
            variable=self.capacity_var,
            command=self._capacity_changed,
        )
        self.capacity_scale.pack(fill=tk.X, pady=(2, 2))

        self.capacity_label = ttk.Label(controls)
        self.capacity_label.pack(anchor="w", pady=(0, 12))

        button_frame = ttk.Frame(controls)
        button_frame.pack(fill=tk.X, pady=4)

        ttk.Button(
            button_frame,
            text="Add child road",
            command=self.add_child_to_selected,
        ).pack(fill=tk.X, pady=3)

        ttk.Button(
            button_frame,
            text="Delete selected branch",
            command=self.delete_selected_branch,
        ).pack(fill=tk.X, pady=3)

        ttk.Button(
            button_frame,
            text="Set selected as End",
            command=self.set_selected_as_end,
        ).pack(fill=tk.X, pady=3)

        ttk.Button(
            button_frame,
            text="Reset demo",
            command=self.reset_demo,
        ).pack(fill=tk.X, pady=3)

        ttk.Separator(controls).pack(fill=tk.X, pady=12)

        ttk.Label(
            controls,
            text="Simulation",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            controls,
            textvariable=self.summary_var,
            justify=tk.LEFT,
            wraplength=235,
        ).pack(anchor="w", pady=(5, 8))

        ttk.Label(
            controls,
            textvariable=self.status_var,
            justify=tk.LEFT,
            wraplength=235,
            foreground="#555555",
        ).pack(anchor="w", pady=(4, 0))

        canvas_frame = ttk.Frame(main)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            canvas_frame,
            background="#f7f7f7",
            highlightthickness=1,
            highlightbackground="#bbbbbb",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Configure>", lambda _event: self.redraw())

    # ---------------------------
    # Tree construction
    # ---------------------------

    def _new_node(
        self,
        name: str,
        x: float,
        y: float,
        parent: Optional[TreeNode] = None,
        capacity: float = 100.0,
    ) -> TreeNode:
        node = TreeNode(
            node_id=self.next_id,
            name=name,
            x=x,
            y=y,
            parent=parent,
            capacity_from_parent=capacity,
        )
        self.next_id += 1
        if parent is not None:
            parent.children.append(node)
        return node

    def _build_initial_tree(self) -> None:
        self.next_id = 0

        # Main Start -> ... -> End corridor.
        self.start = self._new_node("Start", 100, 320)
        a = self._new_node("A", 280, 250, self.start, capacity=100)
        b = self._new_node("B", 480, 330, a, capacity=85)
        self.end = self._new_node("End", 720, 260, b, capacity=70)

        # Two side branches make the data structure visibly tree-shaped.
        self._new_node("C", 300, 455, a, capacity=120)
        self._new_node("D", 525, 475, b, capacity=90)

    # ---------------------------
    # Tiny traffic model
    # ---------------------------

    @staticmethod
    def edge_length(a: TreeNode, b: TreeNode) -> float:
        # 100 canvas pixels = 1 toy distance unit.
        return math.hypot(a.x - b.x, a.y - b.y) / 100.0

    def active_path(self) -> list[TreeNode]:
        """Unique Start-to-End path in a rooted tree."""
        return self.end.path_from_root()

    def edge_on_active_path(self, child: TreeNode) -> bool:
        if child.parent is None:
            return False
        path = self.active_path()
        return any(
            path[i] is child.parent and path[i + 1] is child
            for i in range(len(path) - 1)
        )

    def edge_flow(self, child: TreeNode) -> float:
        return self.demand_var.get() if self.edge_on_active_path(child) else 0.0

    def utilization(self, child: TreeNode) -> float:
        if child.parent is None:
            return 0.0
        cap = max(child.capacity_from_parent, 1e-9)
        return self.edge_flow(child) / cap

    def edge_travel_time(self, child: TreeNode) -> float:
        """Simple BPR-style travel time, in toy minutes."""
        if child.parent is None:
            return 0.0

        length = self.edge_length(child.parent, child)

        # Toy free-flow speed: 1 distance unit corresponds to ~1 minute.
        free_flow_minutes = max(length, 0.05)

        u = self.utilization(child)

        # BPR-like congestion penalty.
        return free_flow_minutes * (1.0 + 0.15 * (u ** 4))

    def total_trip_time(self) -> float:
        path = self.active_path()
        return sum(self.edge_travel_time(path[i]) for i in range(1, len(path)))

    @staticmethod
    def congestion_color(utilization: float, active: bool) -> str:
        if not active:
            return "#b8b8b8"
        if utilization < 0.65:
            return "#2a9d8f"
        if utilization < 1.00:
            return "#e9a23b"
        return "#d1495b"

    # ---------------------------
    # Drawing
    # ---------------------------

    def all_nodes(self) -> list[TreeNode]:
        out: list[TreeNode] = []

        def visit(node: TreeNode) -> None:
            out.append(node)
            for child in node.children:
                visit(child)

        visit(self.start)
        return out

    def redraw(self) -> None:
        if not hasattr(self, "canvas"):
            return

        self.canvas.delete("all")

        # Legend.
        self.canvas.create_text(
            16,
            15,
            anchor="nw",
            text="Road utilization: green < 65%   orange < 100%   red ≥ 100%   gray = unused branch",
            fill="#444444",
            font=("TkDefaultFont", 10),
        )

        # Draw all roads first.
        for node in self.all_nodes():
            if node.parent is None:
                continue

            active = self.edge_on_active_path(node)
            util = self.utilization(node)
            color = self.congestion_color(util, active)

            self.canvas.create_line(
                node.parent.x,
                node.parent.y,
                node.x,
                node.y,
                fill=color,
                width=7 if active else 4,
                capstyle=tk.ROUND,
            )

            mx = (node.parent.x + node.x) / 2
            my = (node.parent.y + node.y) / 2
            flow = self.edge_flow(node)

            label = (
                f"cap {node.capacity_from_parent:.0f}"
                if not active
                else f"flow {flow:.0f} / cap {node.capacity_from_parent:.0f}"
            )
            self.canvas.create_text(
                mx,
                my - 12,
                text=label,
                fill="#333333",
                font=("TkDefaultFont", 9),
            )

        # Draw nodes on top.
        for node in self.all_nodes():
            r = self.NODE_RADIUS

            if node is self.start:
                fill = "#3a86ff"
            elif node is self.end:
                fill = "#8338ec"
            else:
                fill = "#ffffff"

            outline = "#111111"
            width = 3 if node is self.selected else 1

            self.canvas.create_oval(
                node.x - r,
                node.y - r,
                node.x + r,
                node.y + r,
                fill=fill,
                outline=outline,
                width=width,
            )

            text_color = "#ffffff" if node in (self.start, self.end) else "#111111"
            self.canvas.create_text(
                node.x,
                node.y,
                text=node.name,
                fill=text_color,
                font=("TkDefaultFont", 9, "bold"),
            )

        self._update_summary()

    def _update_summary(self) -> None:
        demand = self.demand_var.get()
        trip = self.total_trip_time()
        path = self.active_path()

        bottleneck = None
        bottleneck_u = -1.0
        for node in path[1:]:
            u = self.utilization(node)
            if u > bottleneck_u:
                bottleneck = node
                bottleneck_u = u

        path_text = " → ".join(node.name for node in path)

        if bottleneck is not None and bottleneck.parent is not None:
            bottleneck_text = (
                f"{bottleneck.parent.name}→{bottleneck.name} "
                f"({100*bottleneck_u:.0f}% utilized)"
            )
        else:
            bottleneck_text = "none"

        self.demand_label.configure(text=f"{demand:.0f} vehicles / toy time step")
        self.capacity_label.configure(
            text=(
                "Start has no incoming road"
                if self.selected is self.start
                else f"{self.capacity_var.get():.0f} vehicles / toy time step"
            )
        )

        self.summary_var.set(
            f"Path: {path_text}\n"
            f"Estimated trip time: {trip:.2f} toy min\n"
            f"Bottleneck: {bottleneck_text}"
        )

    # ---------------------------
    # Interaction
    # ---------------------------

    def find_node_at(self, x: float, y: float) -> Optional[TreeNode]:
        best = None
        best_d = float("inf")
        for node in self.all_nodes():
            d = math.hypot(node.x - x, node.y - y)
            if d <= self.NODE_RADIUS + 5 and d < best_d:
                best = node
                best_d = d
        return best

    def _on_mouse_down(self, event: tk.Event) -> None:
        node = self.find_node_at(event.x, event.y)
        if node is None:
            self.selected = None
            self.dragging = None
            self.status_var.set("Click an intersection to select it.")
            self.redraw()
            return

        self.selected = node
        self.dragging = node
        self.drag_dx = node.x - event.x
        self.drag_dy = node.y - event.y
        self._sync_selected_controls()
        self.status_var.set(
            f"Selected {node.name}. Drag it to change road geometry."
        )
        self.redraw()

    def _on_mouse_drag(self, event: tk.Event) -> None:
        if self.dragging is None:
            return

        w = max(self.canvas.winfo_width(), 100)
        h = max(self.canvas.winfo_height(), 100)
        margin = self.NODE_RADIUS + 5

        self.dragging.x = min(
            max(event.x + self.drag_dx, margin),
            w - margin,
        )
        self.dragging.y = min(
            max(event.y + self.drag_dy, 45),
            h - margin,
        )
        self.redraw()

    def _on_mouse_up(self, _event: tk.Event) -> None:
        self.dragging = None

    def _sync_selected_controls(self) -> None:
        if self.selected is None or self.selected.parent is None:
            self.capacity_scale.state(["disabled"])
            self.capacity_var.set(100.0)
        else:
            self.capacity_scale.state(["!disabled"])
            self.capacity_var.set(self.selected.capacity_from_parent)

    def _capacity_changed(self, _value: str) -> None:
        if self.selected is not None and self.selected.parent is not None:
            self.selected.capacity_from_parent = self.capacity_var.get()
        self.redraw()

    def add_child_to_selected(self) -> None:
        if self.selected is None:
            self.status_var.set("Select a parent node first.")
            return

        parent = self.selected
        angle = 0.65 if len(parent.children) % 2 == 0 else -0.65
        length = 130
        x = parent.x + length * math.cos(angle)
        y = parent.y + length * math.sin(angle)

        # Keep the new node roughly inside the current canvas.
        x = min(max(x, 30), max(self.canvas.winfo_width() - 30, 30))
        y = min(max(y, 55), max(self.canvas.winfo_height() - 30, 55))

        node = self._new_node(
            name=f"N{self.next_id}",
            x=x,
            y=y,
            parent=parent,
            capacity=100.0,
        )
        self.selected = node
        self._sync_selected_controls()
        self.status_var.set(
            f"Added {node.name} as a child of {parent.name}. "
            "The map remains a tree."
        )
        self.redraw()

    def delete_selected_branch(self) -> None:
        node = self.selected

        if node is None:
            self.status_var.set("Select a branch node first.")
            return

        if node is self.start:
            self.status_var.set("The Start/root node cannot be deleted.")
            return

        # Do not delete the unique End or an ancestor that contains it.
        if node.contains(self.end):
            self.status_var.set(
                "That branch contains the current End. "
                "Move the End first, then delete the branch."
            )
            return

        assert node.parent is not None
        parent = node.parent
        parent.remove_child(node)
        self.selected = parent
        self._sync_selected_controls()
        self.status_var.set(f"Deleted the branch rooted at {node.name}.")
        self.redraw()

    def set_selected_as_end(self) -> None:
        if self.selected is None:
            self.status_var.set("Select a node first.")
            return
        if self.selected is self.start:
            self.status_var.set(
                "For this toy example, Start and End must be different nodes."
            )
            return

        self.end = self.selected
        self.status_var.set(
            f"{self.end.name} is now the unique End node."
        )
        self.redraw()

    def reset_demo(self) -> None:
        self._build_initial_tree()
        self.selected = self.end
        self.demand_var.set(80.0)
        self._sync_selected_controls()
        self.status_var.set("Demo reset.")
        self.redraw()


def main() -> None:
    root = tk.Tk()
    TrafficTreeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
