"""Integrate any local JPEG/PNG/PDF with the HTTP API; no cloud credentials required."""

import argparse
import json
import urllib.request
from pathlib import Path
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:18083/api/recognize")
    args = parser.parse_args()
    boundary = uuid4().hex
    # Fixed upload filename prevents local path disclosure in multipart metadata.
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + args.file.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        args.url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        print(json.dumps(json.load(response), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
