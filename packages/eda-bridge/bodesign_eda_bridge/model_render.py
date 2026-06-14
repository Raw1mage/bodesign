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


_GLTF_CT = {5120: ("i1", 1), 5121: ("u1", 1), 5122: ("<i2", 2),
            5123: ("<u2", 2), 5125: ("<u4", 4), 5126: ("<f4", 4)}
_GLTF_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _read_accessor(g, blob, idx, np):
    """Read a glTF accessor (uncompressed) into an (count, ncomp) numpy array."""
    acc = g.accessors[idx]
    bv = g.bufferViews[acc.bufferView]
    dt, sz = _GLTF_CT[acc.componentType]
    nc = _GLTF_NC[acc.type]
    base = (bv.byteOffset or 0) + (acc.byteOffset or 0)
    stride = bv.byteStride or (sz * nc)
    if stride == sz * nc:
        return np.frombuffer(blob, dtype=dt, count=acc.count * nc, offset=base).reshape(acc.count, nc)
    rows = np.empty((acc.count, nc), dtype=dt)
    for i in range(acc.count):
        rows[i] = np.frombuffer(blob, dtype=dt, count=nc, offset=base + i * stride)
    return rows


def _decode_mesh(glb_path):
    """Return (vertices, faces, vertex_colors) in world coords, or None on failure.

    Handles both Draco-compressed (KHR_draco_mesh_compression) and plain glTF
    primitives, so e.g. OpenMV's Draco .glb and a build123d STEP->glb both render.
    """
    import numpy as np
    from pygltflib import GLTF2
    try:
        import DracoPy
    except ImportError:
        DracoPy = None

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
            if ext and DracoPy is not None:
                bv = g.bufferViews[ext["bufferView"]]
                off = bv.byteOffset or 0
                dm = DracoPy.decode(blob[off:off + bv.byteLength])
                pts = np.array(dm.points, float).reshape(-1, 3)
                fcs = np.array(dm.faces).reshape(-1, 3)
            else:
                pos = getattr(prim.attributes, "POSITION", None)
                if pos is None:
                    continue
                pts = _read_accessor(g, blob, pos, np).astype(float)
                if prim.indices is not None:
                    fcs = _read_accessor(g, blob, prim.indices, np).reshape(-1, 3).astype(int)
                else:
                    fcs = np.arange(len(pts) // 3 * 3).reshape(-1, 3)
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


def _render_mesh_views(V, F, C, out: Path, stem: str,
                       views: tuple[str, ...], width: int, height: int):
    """Rasterise (vertices, faces, vertex_colours) to top/iso PNGs via pyrender/EGL.

    Shared rendering backend for both the glTF board path and the STL enclosure
    path — the only difference upstream is how V/F/C were decoded. Returns
    (images, status, note); status is "rendered" | "no-deps" | "no-gl".
    """
    import numpy as np
    lo, hi = V.min(0), V.max(0)
    centre = (lo + hi) / 2
    size = float(np.linalg.norm(hi - lo)) or 1.0

    try:
        import trimesh
        import pyrender
        from PIL import Image
    except ImportError as exc:
        return [], "no-deps", f"render dep missing: {exc}"

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
            path = out / f"{stem}_{name}.png"
            Image.fromarray(colour).save(path)
            images.append(str(path))
    except Exception as exc:  # pragma: no cover - GL/EGL availability varies
        return [], "no-gl", f"offscreen GL render failed: {exc}"

    return images, "rendered", ""


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

    images, status, note = _render_mesh_views(V, F, C, out, src.stem, views, width, height)
    if status != "rendered":
        return ModelRenderResult(str(src), status, primitive_count=len(F), note=note)

    return ModelRenderResult(
        str(src), "rendered", images=images,
        bounds_mm=[round(float(x) * 1000, 2) for x in (*lo, *hi)],  # gltf metres -> mm
        primitive_count=len(F),
        note="rendered from the published 3D board model (real board, not auto-generated)")


# Named CMF colours (EN + 中文) -> RGB. Single-colour design intent only; not a
# material/PBR system. Alpha defaults to 255 (opaque) unless a #RRGGBBAA hex is given.
_CMF_COLOR_NAMES = {
    "white": (245, 246, 248), "白": (245, 246, 248), "白色": (245, 246, 248),
    "black": (28, 30, 34), "黑": (28, 30, 34), "黑色": (28, 30, 34),
    "grey": (176, 180, 188), "gray": (176, 180, 188), "灰": (176, 180, 188), "灰色": (176, 180, 188),
    "silver": (200, 204, 209), "銀": (200, 204, 209), "銀色": (200, 204, 209),
    "red": (200, 60, 55), "紅": (200, 60, 55), "紅色": (200, 60, 55),
    "green": (60, 160, 90), "綠": (60, 160, 90), "綠色": (60, 160, 90),
    "blue": (60, 110, 200), "藍": (60, 110, 200), "藍色": (60, 110, 200),
    "navy": (35, 55, 110), "深藍": (35, 55, 110),
    "orange": (230, 140, 50), "橘": (230, 140, 50), "橘色": (230, 140, 50), "橙": (230, 140, 50),
    "yellow": (235, 205, 60), "黃": (235, 205, 60), "黃色": (235, 205, 60),
}

_DEFAULT_ENCLOSURE_RGBA = (176, 180, 188, 255)  # neutral enclosure grey


def _resolve_cmf_color(color) -> tuple[int, int, int, int] | None:
    """Resolve a CMF colour spec to an (R,G,B,A) tuple of ints 0..255, or None.

    Accepts:
      - None                       -> None (caller keeps neutral grey)
      - "#RRGGBB" / "#RRGGBBAA"     -> parsed hex (A defaults 255)
      - a named colour (EN/中文)    -> from _CMF_COLOR_NAMES, A=255
      - (r,g,b) / (r,g,b,a) tuple   -> clamped to 0..255 ints
    Returns None on any unparseable input — the caller then falls back to grey
    rather than crashing. This is a single-colour resolver, NOT a material system.
    """
    if color is None:
        return None
    if isinstance(color, (tuple, list)):
        try:
            vals = [max(0, min(255, int(round(float(c))))) for c in color]
        except (TypeError, ValueError):
            return None
        if len(vals) == 3:
            return (vals[0], vals[1], vals[2], 255)
        if len(vals) == 4:
            return (vals[0], vals[1], vals[2], vals[3])
        return None
    if isinstance(color, str):
        s = color.strip()
        if not s:
            return None
        if s.startswith("#"):
            hexpart = s[1:]
            if len(hexpart) == 6 or len(hexpart) == 8:
                try:
                    r = int(hexpart[0:2], 16)
                    g = int(hexpart[2:4], 16)
                    b = int(hexpart[4:6], 16)
                    a = int(hexpart[6:8], 16) if len(hexpart) == 8 else 255
                    return (r, g, b, a)
                except ValueError:
                    return None
            return None
        named = _CMF_COLOR_NAMES.get(s) or _CMF_COLOR_NAMES.get(s.lower())
        if named is not None:
            return (named[0], named[1], named[2], 255)
        return None
    return None


def render_enclosure_model(stl_path: str | Path, out_dir: str | Path,
                           views: tuple[str, ...] = ("top", "iso"),
                           width: int = 1700, height: int = 1300,
                           color=None) -> ModelRenderResult:
    """Render a C02 enclosure STL (top/iso) so a generated draft is *viewable*.

    Closes the C02 'voice-to-design' loop: c02_export_stl produces a real STL,
    this turns it into a design-sketch PNG using the same pyrender/EGL backend as
    the board path. STL is already in mm (no glTF metres->mm scaling). trimesh
    reads STL natively; faces get a neutral enclosure grey since STL carries no
    colour — unless a CMF ``color`` (hex / named EN+中文 / RGB(A) tuple) is given,
    in which case every face takes that single colour. An unparseable colour falls
    back to grey and is noted (never crashes). Degrades to no-deps/no-gl otherwise.
    """
    src = Path(stl_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

    if not src.exists():
        return ModelRenderResult(str(src), "error", note=f"STL not found: {src}")

    try:
        import numpy as np
        import trimesh
    except ImportError as exc:
        return ModelRenderResult(str(src), "no-deps", note=f"trimesh/numpy missing: {exc}")

    try:
        tm = trimesh.load(str(src), force="mesh")
    except Exception as exc:  # pragma: no cover - STL parse variance
        return ModelRenderResult(str(src), "error", note=f"STL load failed: {exc}")
    if tm is None or getattr(tm, "vertices", None) is None or len(tm.vertices) == 0:
        return ModelRenderResult(str(src), "empty", note="STL had no geometry")

    V = np.asarray(tm.vertices, float)
    F = np.asarray(tm.faces, int)
    rgba = _resolve_cmf_color(color)
    color_note = ""
    if rgba is None:
        rgba = _DEFAULT_ENCLOSURE_RGBA  # neutral enclosure grey
        if color is not None:
            color_note = f" (unparseable CMF colour {color!r}, fell back to grey)"
    C = np.tile(list(rgba), (len(V), 1))
    lo, hi = V.min(0), V.max(0)

    images, status, note = _render_mesh_views(V, F, C, out, src.stem, views, width, height)
    if status != "rendered":
        return ModelRenderResult(str(src), status, primitive_count=len(F), note=note)

    return ModelRenderResult(
        str(src), "rendered", images=images,
        bounds_mm=[round(float(x), 2) for x in (*lo, *hi)],  # STL already in mm
        primitive_count=len(F),
        note=("rendered from the generated C02 enclosure STL "
              "(prototype draft, not ME approval)" + color_note))
