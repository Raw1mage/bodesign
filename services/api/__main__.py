import os

import uvicorn


def main() -> None:
    host = os.environ.get("BODESIGN_HOST", "127.0.0.1")
    port = int(os.environ.get("BODESIGN_PORT", "8765"))
    uvicorn.run("services.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
