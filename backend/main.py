import uvicorn

from infrastructure.bootstrap import create_app
from infrastructure.config import load_settings
from infrastructure.logging import configure_logging

settings = load_settings()
configure_logging(log_json=settings.log_json, log_level=settings.log_level)

app = create_app(settings)


def main() -> None:
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
