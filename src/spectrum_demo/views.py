"""Looking at annotated files through the ontology instead of the HDF5 hierarchy.

The HDF5 hierarchy tells where each dataset is stored (``/RawData/Spectrometer/Data1D/CH00/Data00``).
The annotations tell what it is. This module turns a set of loaded files into a tree whose nodes are
*concepts* of the ontology (or quantities and units), with the datasets of all files as leaves,
each leaf keeping the HDF5 path of its data.

Nothing here depends on a GUI: the model (``Node`` trees) is plain Python, so that the same code can
feed a text rendering, a matplotlib diagram (below), or later a Qt tree in a PyMoDAQ application
(double-clicking a leaf would load the data at ``leaf.path``).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

from pymodaq_data.data import DataToExport
from rdflib import URIRef
from rdflib.namespace import RDFS

from . import semantics as sem
from . import vocab as v


@dataclass
class Node:
    label: str
    kind: str                         # 'concept', 'dataset' or 'result'
    iri: Optional[str] = None         # ontology term of a concept node, or of the dataset
    path: Optional[str] = None        # HDF5 path of the data (datasets only): what a double-click loads
    file: Optional[str] = None        # which file the dataset comes from
    info: str = ""                    # short description shown under the label
    children: List["Node"] = field(default_factory=list)
    derived_from: List["Node"] = field(default_factory=list)   # provenance links (results)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def leaves(self):
        return [n for n in self.walk() if not n.children]

    def find(self, label: str, file: Optional[str] = None) -> Optional["Node"]:
        for node in self.walk():
            if node.label == label and (file is None or node.file == file):
                return node
        return None


def _concept_chain(concept) -> List[URIRef]:
    """Concepts from the top of the demo vocabulary down to ``concept`` (rdfs:subClassOf chain)."""
    g = sem.ontology()
    chain = [URIRef(concept)]
    while True:
        parents = [p for p in g.objects(chain[0], RDFS.subClassOf)
                   if isinstance(p, URIRef) and str(p).startswith(str(v.SPECTRO))]
        if not parents:
            return chain
        chain.insert(0, parents[0])


def _dataset_info(dwa) -> str:
    axis = dwa.axes[0]
    return (f"{sem.label(getattr(dwa, v.QUANTITY_KIND))} [{sem.label(getattr(dwa, v.UNIT_IRI))}] vs "
            f"{sem.label(getattr(axis, v.QUANTITY_KIND)).lower()} "
            f"[{sem.label(getattr(axis, v.UNIT_IRI))}]")


def concept_tree(files: Mapping[str, DataToExport], results: Optional[Mapping[str, object]] = None
                 ) -> Node:
    """Tree of ontology concepts with the datasets of every file as leaves.

    ``files`` maps a file label (for instance "Lab A") to its loaded data. ``results`` optionally
    maps the same labels to the analysis result, added as an absorbance spectrum derived from the
    datasets it used (provenance link).
    """
    root = Node("spectrum", "concept", iri=str(v.SPECTRO.Spectrum))
    concepts: Dict[str, Node] = {str(v.SPECTRO.Spectrum): root}
    leaves: Dict[tuple, Node] = {}

    def concept_node(concept) -> Node:
        parent = root
        for iri in _concept_chain(concept)[1:]:
            key = str(iri)
            if key not in concepts:
                node = Node(sem.label(iri), "concept", iri=key)
                parent.children.append(node)
                concepts[key] = node
            parent = concepts[key]
        return parent

    for file_label, dte in files.items():
        for dwa in dte:
            leaf = Node(dwa.name, "dataset", iri=getattr(dwa, v.SEMANTIC_IRI),
                        path=getattr(dwa, "path", None), file=file_label, info=_dataset_info(dwa))
            concept_node(getattr(dwa, v.SEMANTIC_IRI)).children.append(leaf)
            leaves[(file_label, dwa.name)] = leaf

    for file_label, result in (results or {}).items():
        leaf = Node("absorbance", "result", iri=str(v.SPECTRO.AbsorbanceSpectrum), file=file_label,
                    info=f"peak at {result.peak_wavelength_nm:.0f} nm, "
                         f"A = {result.peak_absorbance:.2f}")
        leaf.derived_from = [leaves[(file_label, name)] for name in result.used]
        concept_node(v.SPECTRO.AbsorbanceSpectrum).children.append(leaf)

    for node in concepts.values():
        node.children.sort(key=lambda n: (n.kind != "concept", n.label, n.file or ""))
    return root


def quantity_tree(files: Mapping[str, DataToExport]) -> Node:
    """Tree grouping the datasets by quantity kind and unit instead of by concept."""
    root = Node("all datasets", "concept")
    for file_label, dte in files.items():
        for dwa in dte:
            kind = sem.label(getattr(dwa, v.QUANTITY_KIND))
            unit = sem.label(getattr(dwa, v.UNIT_IRI))
            kind_node = next((n for n in root.children if n.label == kind), None)
            if kind_node is None:
                kind_node = Node(kind, "concept")
                root.children.append(kind_node)
            unit_node = next((n for n in kind_node.children if n.label == unit), None)
            if unit_node is None:
                unit_node = Node(unit, "concept")
                kind_node.children.append(unit_node)
            unit_node.children.append(Node(dwa.name, "dataset", iri=getattr(dwa, v.SEMANTIC_IRI),
                                           path=getattr(dwa, "path", None), file=file_label,
                                           info=_dataset_info(dwa)))
    return root


def hdf5_tree(files: Mapping[str, DataToExport]) -> Node:
    """What the HDF5 browser shows: the storage hierarchy, one subtree per file."""
    root = Node("files", "concept")
    for file_label, dte in files.items():
        file_node = Node(file_label, "concept")
        root.children.append(file_node)
        for dwa in dte:
            parent = file_node
            parts = [p for p in dwa.path.split("/") if p]
            for part in parts[:-1]:
                nxt = next((n for n in parent.children if n.label == part), None)
                if nxt is None:
                    nxt = Node(part, "concept")
                    parent.children.append(nxt)
                parent = nxt
            parent.children.append(Node(parts[-1], "dataset", path=dwa.path))
    return root


def render_text(root: Node, show_path: bool = True) -> str:
    """Indented text rendering of a tree (``├──`` style)."""
    lines = [root.label]

    def add(node: Node, prefix: str):
        for i, child in enumerate(node.children):
            last = i == len(node.children) - 1
            text = child.label
            if child.file and child.kind != "concept":
                text = f"{child.file}: {text}"
            if child.info:
                text += f"  [{child.info}]"
            if show_path and child.path:
                text += f"  -> {child.path}"
            if child.derived_from:
                text += "  <- " + ", ".join(d.label for d in child.derived_from)
            lines.append(prefix + ("└── " if last else "├── ") + text)
            add(child, prefix + ("    " if last else "│   "))

    add(root, "")
    return "\n".join(lines)


def draw_concept_tree(root: Node, ax, colors: Mapping[str, str], neutral: str = "#7a7a75"):
    """Draw a concept tree left to right with matplotlib: concepts in boxes, datasets as dots
    coloured by file, provenance links dashed. Only matplotlib is needed."""
    positions: Dict[int, tuple] = {}
    depth_of: Dict[int, int] = {}
    counter = [0]

    def layout(node: Node, depth: int):
        depth_of[id(node)] = depth
        if not node.children:
            y = -counter[0]
            counter[0] += 1
        else:
            ys = [layout(child, depth + 1) for child in node.children]
            y = sum(ys) / len(ys)
        positions[id(node)] = (depth, y)
        return y

    layout(root, 0)
    concept_depths = [depth_of[id(n)] for n in root.walk() if n.children or n.kind == "concept"]
    xs = {d: d * 3.0 for d in range(max(concept_depths) + 2)}
    leaf_x = xs[max(concept_depths) + 1]          # all datasets aligned in one column

    def point(node: Node):
        depth, y = positions[id(node)]
        return (xs[depth] if node.children or node.kind == "concept" else leaf_x), y

    def right_edge(node: Node) -> float:
        x, _ = point(node)
        return x + 0.085 * len(node.label) + 0.3     # approximate width of the box

    for node in root.walk():
        for child in node.children:
            xa, ya = right_edge(node), point(node)[1]
            xb, yb = point(child)[0] - (0.4 if child.kind != "concept" else 0.1), point(child)[1]
            xm = (xa + xb) / 2
            ax.plot([xa, xm, xm, xb], [ya, ya, yb, yb], color="#b8b7b0", lw=1, zorder=1)
    for node in root.walk():
        x, y = point(node)
        if node.kind == "concept":
            ax.text(x, y, node.label, ha="left", va="center", fontsize=9, color="#2b2b29", zorder=3,
                    bbox=dict(boxstyle="round,pad=0.3", fc="#efeee9", ec="#c9c8c0", lw=1))
        else:
            color = colors.get(node.file, neutral)
            marker = "D" if node.kind == "result" else "o"
            ax.plot([x - 0.25], [y], marker, color=color, ms=8, mec="white", mew=1.5, zorder=3)
            ax.text(x - 0.1, y + 0.12, f"{node.file}: {node.label}", ha="left", va="bottom",
                    fontsize=9, color="#2b2b29", zorder=3)
            if node.info:
                ax.text(x - 0.1, y - 0.05, node.info, ha="left", va="top", fontsize=7.5,
                        color="#5f5e58", zorder=3)
    # provenance: dashed arcs (bowing to the left of the dataset column) from a result to the
    # datasets it was derived from
    for node in root.walk():
        for source in node.derived_from:
            (x0, y0), (x1, y1) = point(node), point(source)
            rad = 0.45 if y1 < y0 else -0.45
            ax.annotate("", xy=(x1 - 0.25, y1), xytext=(x0 - 0.25, y0),
                        arrowprops=dict(arrowstyle="->", color=colors.get(node.file, neutral),
                                        lw=1.1, ls=(0, (4, 3)), shrinkA=5, shrinkB=5,
                                        connectionstyle=f"arc3,rad={rad}"), zorder=2)
    ax.set_xlim(-0.3, leaf_x + 5.2)
    ax.set_ylim(-counter[0] + 0.3, 0.9)
    ax.axis("off")
