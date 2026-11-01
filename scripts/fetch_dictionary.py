#!/usr/bin/env python3
"""Download an immutable ECDICT snapshot, verifying GitHub blob hashes."""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/skywind3000/ECDICT"


def request(url, accept="application/vnd.github+json"):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        "User-Agent": "ReadZine/0.1", "Accept": accept}), timeout=60)


def git_hash(path):
    digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with request(API + "/commits/master") as response:
        commit = json.load(response)["sha"]
    records = {}
    for filename in ("ecdict.csv", "LICENSE"):
        with request(API + f"/contents/{filename}?ref={commit}") as response:
            info = json.load(response)
        target = directory / filename
        if not target.exists() or git_hash(target) != info["sha"]:
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
                    temporary = Path(stream.name)
                    with request(API + f"/contents/{filename}?ref={commit}", "application/vnd.github.raw+json") as response:
                        for chunk in iter(lambda: response.read(1024 * 1024), b""):
                            stream.write(chunk)
                if temporary.stat().st_size != info["size"] or git_hash(temporary) != info["sha"]:
                    raise ValueError(filename + " 下载不完整或校验失败；未替换现有缓存")
                os.replace(temporary, target)
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()
        records[filename] = {"path": str(target.resolve()), "gitBlob": info["sha"],
                             "bytes": target.stat().st_size,
                             "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    record = {"source": "https://github.com/skywind3000/ECDICT", "commit": commit, "files": records}
    (directory / "provenance.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(fetch(args.directory), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError) as error:
        print(f"词典获取失败：{error}", file=sys.stderr)
        sys.exit(1)
