import logging
import uvicorn

from infrastructure.bootstrap import create_app

logging.basicConfig(level=logging.INFO)

app = create_app()


def main() -> None:
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
