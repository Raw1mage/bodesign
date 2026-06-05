import importlib
import sys
import types
import unittest


class ApiRouteRegistrationTests(unittest.TestCase):
    def test_bodesign_routes_are_registered_without_fastapi_runtime(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        routes = {route.path for route in api_main.app.routes}

        self.assertIn("/", routes)
        self.assertIn("/bodesign", routes)
        self.assertIn("/bodesign/", routes)
        self.assertIn("/bodesign/projects/{project_id}", routes)
        self.assertIn("/bodesign/projects/{project_id}/artifacts/{artifact_id}", routes)
        self.assertIn("/bodesign/routes", routes)
        self.assertIn("/bodesign/health", routes)
        self.assertIn("/bodesign/api/routes", routes)
        self.assertIn("/bodesign/api/projects", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/artifacts", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/artifacts/{artifact_id}", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/geometry", routes)
        self.assertIn("/bodesign/api/artifacts/detect", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/knowledge/datasheets", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/reports/design", routes)

    def test_bodesign_route_index_is_visible_without_fastapi_runtime(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        route_index = api_main.bodesign_route_index()
        route_registry = api_main.bodesign_route_registry()

        self.assertIn("bodesign visible routes", route_index)
        self.assertIn("/bodesign/", route_index)
        self.assertIn("/bodesign/api/routes", {route["path"] for route in route_registry["routes"]})

    def test_bodesign_viewer_has_file_workspace_tabs(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        html = api_main.bodesign_viewer()

        self.assertIn("Projects", html)
        self.assertIn("Rockbox reference board", html)
        self.assertIn("imported-fixture", html)
        self.assertIn("/bodesign/projects/rockbox", html)
        self.assertIn("Source Documents", api_main.bodesign_project_workspace("rockbox"))
        self.assertIn("Source Documents", html)
        self.assertIn("Gerber Layers", html)
        self.assertIn("IPC-356 Nets", html)
        self.assertIn("Components", html)
        self.assertIn("BoardDesign IR", html)
        self.assertIn("Reconstruction Report", html)
        self.assertIn("Evidence-based geometry preview", html)
        self.assertIn("L1_top.art", html)
        self.assertIn("ROCKBOX_V2-1-6.drl", html)
        self.assertIn("<svg", html)

    def test_project_api_lists_imported_rockbox_project(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        projects = api_main.list_projects()

        self.assertEqual("rockbox", projects[0]["id"])
        self.assertEqual("imported-fixture", projects[0]["status"])
        self.assertIn("viewer_url", projects[0])

    def test_project_artifact_api_and_viewer_expose_rockbox_files(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        artifacts = api_main.list_project_artifacts("rockbox")
        artifact = artifacts[0]
        artifact_detail = api_main.get_project_artifact("rockbox", artifact["id"])
        artifact_html = api_main.bodesign_artifact_viewer("rockbox", artifact["id"])

        self.assertGreater(len(artifacts), 0)
        self.assertEqual("rockbox", artifact["project_id"])
        self.assertIn("viewer_url", artifact)
        self.assertIn("preview", artifact_detail)
        self.assertIn(str(artifact["filename"]), artifact_html)
        self.assertIn("Preview", artifact_html)

    def test_project_geometry_api_exposes_gerber_and_drill_summary(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        geometry = api_main.get_project_geometry("rockbox")

        self.assertEqual("geometry-preview", geometry["status"])
        self.assertEqual("L1_top.art", geometry["gerber"]["filename"])
        self.assertEqual("ROCKBOX_V2-1-6.drl", geometry["drill"]["filename"])
        self.assertGreater(geometry["gerber"]["draw_count"], 1000)
        self.assertEqual(789, geometry["drill"]["hit_count"])


def install_fastapi_stub() -> None:
    fastapi_module = types.ModuleType("fastapi")
    responses_module = types.ModuleType("fastapi.responses")

    class Route:
        def __init__(self, path: str, method: str) -> None:
            self.path = path
            self.method = method

    class FastAPI:
        def __init__(self, *args, **kwargs) -> None:
            self.routes = []

        def get(self, path: str, **kwargs):
            return self._register(path, "GET")

        def post(self, path: str, **kwargs):
            return self._register(path, "POST")

        def _register(self, path: str, method: str):
            def decorator(function):
                self.routes.append(Route(path, method))
                return function

            return decorator

    class HTMLResponse:
        pass

    class RedirectResponse:
        def __init__(self, url: str) -> None:
            self.url = url

    fastapi_module.FastAPI = FastAPI
    responses_module.HTMLResponse = HTMLResponse
    responses_module.RedirectResponse = RedirectResponse
    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.responses"] = responses_module


if __name__ == "__main__":
    unittest.main()
