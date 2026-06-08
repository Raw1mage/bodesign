"""Render a published 3D board model (glTF/.glb) to board-view PNGs.

Many open-hardware projects publish the *real* board as a glTF model with every
component placed (e.g. OpenMV's ``OPENMV_N6.glb``). This renders that model
directly — the actual board, not a from-scratch sketch — into top/iso views.

Pipeline (all optional deps; degrade gracefully if absent):
  - ``pygltflib`` parses the .glb container + scene graph,
  - ``DracoPy`` decodes ``KHR_draco_mesh_compression`` primitives,
  - node transforms are applied so geometry lands in world coordinates,
  - per-primitive ``baseColorFactor`` becomes vertex colour,
  - ``pyrender`` (EGL offscreen) rasterises — needs a GL stack, so this runs on
    the me worker, which already ships the build123d/VTK GL libraries.

No network and no Node tooling: Draco is decoded in-process via DracoPy.
"""

from dataclasses import dataclass, field
from pathlib import Path
import math
import os


@dataclass(slots=True)
class ModelRenderResult:
    source: str
    status: str                     # rendered | no-deps | no-gl | empty | error
    images: list[str] = field(default_factory=list)
    bounds_mm: list[float] | None = None
    primitive_count: int = 0
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "status": self.status,
            "images": list(self.images),
            "bounds_mm": self.bounds_mm,
            "primitive_count": self.primitive_count,
            "note": self.note,
        }


_VIEWS = {
    # name: (eye offset as fraction of model size, view-up)
    "top": ((0.0, 0.0, 1.15), (0.0, 1.0, 0.0)),
    "iso": ((-0.85, -0.85, 0.95), (0.0, 0.0, 1.0)),
}


def _node_matrix(node, np):
    if node.matrix:
        return np.array(node.matrix, float).reshape(4, 4).T
    m = np.eye(4)
    if node.translation:
        m[:3, 3] = node.translation
    if node.rotation:
        x, y, z, w = node.rotation
        m[:3, :3] = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ])
    if node.scale:
        m[:3, :3] = m[:3, :3] @ np.diag(node.scale)
    return m


def _decode_mesh(glb_path):
    """Return (vertices, faces, vertex_colors) in world coords, or None on failure."""
    import numpy as np
    from pygltflib import GLTF2
    import DracoPy

    g = GLTF2().load_binary(str(glb_path))
    blob = g.binary_blob()

    world: dict[int, "np.ndarray"] = {}

    def walk(ni, parent):
        node = g.nodes[ni]
        mat = parent @ _node_matrix(node, np)
        if node.mesh is not None:
            world.setdefault(node.mesh, mat)
        for child in (node.children or []):
            walk(child, mat)

    scene = g.scenes[g.scene or 0]
    for ni in scene.nodes:
        walk(ni, np.eye(4))

    verts, faces, colours = [], [], []
    voff = 0
    for mi, mesh in enumerate(g.meshes):
        mat = world.get(mi, np.eye(4))
        for prim in mesh.primitives:
            ext = (prim.extensions or {}).get("KHR_draco_mesh_compression")
            if not ext:
                continue  # non-draco primitives are skipped in this slice
            bv = g.bufferViews[ext["bufferView"]]
            off = bv.byteOffset or 0
            dm = DracoPy.decode(blob[off:off + bv.byteLength])
            pts = np.array(dm.points, float).reshape(-1, 3)
            fcs = np.array(dm.faces).reshape(-1, 3)
            pts = (mat[:3, :3] @ pts.T).T + mat[:3, 3]
            col = [180, 180, 185, 255]
            if prim.material is not None:
                pbr = g.materials[prim.material].pbrMetallicRoughness
                if pbr and pbr.baseColorFactor:
                    col = [int(c * 255) for c in pbr.baseColorFactor]
            verts.append(pts)
            faces.append(fcs + voff)
            colours.append(np.tile(col, (len(pts), 1)))
            voff += len(pts)
    if not verts:
        return None
    return np.vstack(verts), np.vstack(faces), np.vstack(colours)


def render_board_model(glb_path: str | Path, out_dir: str | Path,
                       views: tuple[str, ...] = ("top", "iso"),
                       width: int = 1700, height: int = 1300) -> ModelRenderResult:
    src = Path(glb_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    try:
        import numpy as np  # noqa: F401
        decoded = _decode_mesh(src)
    except ImportError as exc:
        return ModelRenderResult(str(src), "no-deps", note=f"missing parser/draco dep: {exc}")
    except Exception as exc:  # pragma: no cover - upstream parse variance
        return ModelRenderResult(str(src), "error", note=f"decode failed: {exc}")
    if decoded is None:
        return ModelRenderResult(str(src), "empty", note="no draco primitives decoded")

    import numpy as np
    V, F, C = decoded
    lo, hi = V.min(0), V.max(0)
    centre = (lo + hi) / 2
    size = float(np.linalg.norm(hi - lo)) or 1.0

    try:
        import trimesh
        import pyrender
        from PIL import Image
    except ImportError as exc:
        return ModelRenderResult(str(src), "no-deps", primitive_count=len(F),
                                 note=f"render dep missing: {exc}")

    try:
        mesh = pyrender.Mesh.from_trimesh(
            trimesh.Trimesh(vertices=V, faces=F, vertex_colors=C, process=False), smooth=False)
        cam = pyrender.PerspectiveCamera(yfov=np.pi / 5.5, aspectRatio=width / height)

        def pose(eye, up):
            eye = np.array(eye, float); up = np.array(up, float); tgt = np.array(centre, float)
            f = tgt - eye; f /= np.linalg.norm(f)
            s = np.cross(f, up); s /= np.linalg.norm(s); u = np.cross(s, f)
            m = np.eye(4); m[:3, 0] = s; m[:3, 1] = u; m[:3, 2] = -f; m[:3, 3] = eye
            return m

        images: list[str] = []
        for name in views:
            offs, up = _VIEWS.get(name, _VIEWS["iso"])
            eye = [centre[i] + offs[i] * size for i in range(3)]
            scene = pyrender.Scene(bg_color=[1, 1, 1, 1], ambient_light=[0.5, 0.5, 0.5])
            scene.add(mesh)
            p = pose(eye, up)
            scene.add(cam, pose=p)
            scene.add(pyrender.DirectionalLight(color=[1, 1, 1], intensity=4.0), pose=p)
            scene.add(pyrender.DirectionalLight(color=[1, 1, 1], intensity=2.0),
                      pose=pose([centre[0], centre[1], centre[2] + size], [0, 1, 0]))
            renderer = pyrender.OffscreenRenderer(width, height)
            colour, _ = renderer.render(scene)
            renderer.delete()
            path = out / f"{src.stem}_{name}.png"
            Image.fromarray(colour).save(path)
            images.append(str(path))
    except Exception as exc:  # pragma: no cover - GL/EGL availability varies
        return ModelRenderResult(str(src), "no-gl", primitive_count=len(F),
                                 note=f"offscreen GL render failed: {exc}")

    return ModelRenderResult(
        str(src), "rendered", images=images,
        bounds_mm=[round(float(x) * 1000, 2) for x in (*lo, *hi)],  # gltf metres -> mm
        primitive_count=len(F),
        note="rendered from the published 3D board model (real board, not auto-generated)")
