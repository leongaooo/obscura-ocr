"""Portable service and explicit model preparation commands."""

import argparse

import uvicorn

from obscura_ocr.config import Settings
from obscura_ocr.engines.paddle import PaddleOcrEngine


def main():
    parser = argparse.ArgumentParser(prog="obscura-ocr")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="Download and verify OCR models before offline use")
    serve = sub.add_parser("serve", help="Start the local API and browser workbench")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=18083)
    args = parser.parse_args()
    if args.command == "prepare":
        settings = Settings(allow_model_download=True)
        PaddleOcrEngine(settings).load()
        settings.model_ready_marker.write_text("prepared\n", encoding="utf-8")
        print("OCR models prepared. Offline service can now start.")
    else:
        uvicorn.run("obscura_ocr.app:create_app", factory=True, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
