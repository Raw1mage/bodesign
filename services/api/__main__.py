import uvicorn


def main() -> None:
    uvicorn.run("services.api.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
