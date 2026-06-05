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

        self.assertIn("/bodesign", routes)
        self.assertIn("/bodesign/", routes)
        self.assertIn("/bodesign/health", routes)
        self.assertIn("/bodesign/api/projects", routes)
        self.assertIn("/bodesign/api/artifacts/detect", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/knowledge/datasheets", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/reports/design", routes)


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
