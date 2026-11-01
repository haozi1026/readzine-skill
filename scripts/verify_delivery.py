#!/usr/bin/env python3
"""Verify compiled HTML, offline assets, JavaScript syntax and HTTP preview identity."""
import argparse
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.request import urlopen


class Artifact(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.images, self.scripts = [], [], []
        self.current = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "img":
            self.images.append(a.get("src", ""))
        if tag == "script":
            if a.get("src"):
                raise ValueError("成品依赖外部脚本")
            self.current = dict(id=a.get("id"), type=a.get("type"), text="")

    def handle_data(self, text):
        if self.current is not None:
            self.current["text"] += text

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append(self.current)
            self.current = None


def verify(path, url=None, node=None):
    path = path.resolve()
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if path.name == "reader.html" or re.search(r"\{\{[A-Z_]+\}\}", text):
        raise ValueError("这是源模板或未组装文件；请验证 outputs/<主题>/magazine.html")
    artifact = Artifact()
    artifact.feed(text)
    required = {"cover", "reader", "start", "home", "readzine-data", "help-dialog"}
    if not required.issubset(artifact.ids) or len(artifact.ids) != len(set(artifact.ids)):
        raise ValueError("成品缺少必需节点或存在重复 ID")
    payloads = [s for s in artifact.scripts if s["id"] == "readzine-data"]
    if len(payloads) != 1:
        raise ValueError("缺少唯一的成品数据")
    payload = json.loads(payloads[0]["text"])
    if not payload.get("dictionary", {}).get("entries") or not payload.get("metadata", {}).get("templateId"):
        raise ValueError("词典或模板元数据为空")
    if len(artifact.images) < 2:
        raise ValueError("封面或正文图片缺失")
    for src in artifact.images:
        match = re.fullmatch(r"data:image/[^;]+;base64,(.+)", src, re.S)
        if not match or not base64.b64decode(match[1], validate=True):
            raise ValueError("图片未正确离线嵌入")
    executable = [s for s in artifact.scripts if s["type"] != "application/json"]
    runtime = node or shutil.which("node")
    if not runtime or not executable:
        raise ValueError("缺少 JavaScript 或 Node；请用 --node 指定运行时")
    with tempfile.TemporaryDirectory(prefix="readzine-delivery-") as folder:
        for i, script in enumerate(executable):
            source = Path(folder) / f"script-{i}.js"
            source.write_text(script["text"])
            result = subprocess.run([runtime, "--check", str(source)], capture_output=True, text=True)
            if result.returncode:
                raise ValueError("JavaScript 语法错误：" + result.stderr)
    preview = None
    if url:
        with urlopen(url, timeout=8) as response:
            if response.status != 200 or "text/html" not in response.headers.get("Content-Type", ""):
                raise ValueError("预览服务未返回 HTML 200")
            if response.read() != raw:
                raise ValueError("预览内容与当前成品不一致，可能是旧版本或错误入口")
            preview = dict(url=url, status=response.status, matchesArtifact=True)
    return dict(passed=True, file=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                embeddedImages=len(artifact.images), javascriptSyntax=True, preview=preview,
                visualBrowserCheck=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--node")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.file, args.url, args.node)
    except Exception as error:
        print(json.dumps(dict(passed=False, error=str(error)), ensure_ascii=False))
        return 1
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(output)
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
