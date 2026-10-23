"""Monolith Dockerfile must ship the toolchains of every group it serves locally.

When running as a monolith (`SERVED_GROUPS == {"all"}`), `bodesign_init` reports
`available: true, route: "local"` for both `ee` and `me` conditional tool families.
Previously, `ngspice`, `freerouting.jar`, `atopile`, and `elkjs` were added only to
`Dockerfile.ee`, and `requirements-me.txt` (`build123d` + GL/X libs) was added only
to `Dockerfile.me`, leaving the monolith `Dockerfile` claiming local availability
while lacking the binaries/packages at runtime.

This test guards the monolith `Dockerfile` against toolchain drift relative to
`Dockerfile.ee` and `Dockerfile.me`.
"""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCKERFILE_MONOLITH = REPO / "Dockerfile"
DOCKERFILE_EE = REPO / "Dockerfile.ee"
DOCKERFILE_ME = REPO / "Dockerfile.me"


class MonolithDockerfileParityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.monolith = DOCKERFILE_MONOLITH.read_text(encoding="utf-8")
        cls.ee = DOCKERFILE_EE.read_text(encoding="utf-8")
        cls.me = DOCKERFILE_ME.read_text(encoding="utf-8")

    def test_monolith_ships_ngspice_with_build_time_probe(self):
        self.assertIn("ngspice", self.ee)
        self.assertIn("ngspice", self.monolith)
        self.assertIn("ngspice --version", self.monolith)

    def test_monolith_ships_me_requirements_and_build123d_probe(self):
        self.assertIn("requirements-me.txt", self.me)
        self.assertIn("requirements-me.txt", self.monolith)
        self.assertIn("import build123d", self.monolith)
        for gl_lib in ("libgl1", "libglx-mesa0", "libglu1-mesa", "libxrender1"):
            self.assertIn(gl_lib, self.monolith, f"missing GL/X lib {gl_lib} in monolith Dockerfile")

    def test_monolith_ships_ee_freerouting_atopile_and_elkjs(self):
        for token in (
            "/opt/freerouting.jar",
            "FREEROUTING_JAR=/opt/freerouting.jar",
            "atopile==0.12.5",
            "BODESIGN_NODE_BIN=/opt/node/bin/node",
            "packages/eda-bridge/elk/package-lock.json",
            "require('elkjs/lib/elk.bundled.js')",
        ):
            self.assertIn(token, self.ee, f"expected {token} in Dockerfile.ee")
            self.assertIn(token, self.monolith, f"monolith Dockerfile drifted from Dockerfile.ee on {token}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
