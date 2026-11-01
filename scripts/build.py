#!/usr/bin/env python3
"""Validate editorial data and build one offline HTML file. No runtime dependencies."""
import argparse
import base64
import html
import json
import random
import re
import sys
from pathlib import Path

from dictionary import extract, normalize

ROOT = Path(__file__).resolve().parent.parent
STYLES = {"warm", "cinema", "modern", "newspaper", "gallery", "science", "bright"}
VERSION = "0.1.0"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def string(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label} 必须为非空文字")


def span(item, text, label, lower=0, upper=None):
    upper = len(text) if upper is None else upper
    start, end = item.get("start"), item.get("end")
    require(type(start) is int and type(end) is int and lower <= start < end <= upper,
            f"{label} 字符位置无效（使用 Unicode 字符，左闭右开）")
    return start, end


def validate_blocks(blocks, text, lower=0, upper=None):
    require(isinstance(blocks, list) and blocks, "详细拆解必须包含结构块")
    previous = lower
    for block in blocks:
        start, end = span(block, text, "拆解块", lower, upper)
        require(start >= previous, "同层拆解块必须按原文顺序且不可重叠")
        for key in ("title", "meaning", "explanation"):
            string(block.get(key), "拆解块 " + key)
        if block.get("children"):
            validate_blocks(block["children"], text, start, end)
        previous = end


def validate(data):
    require(isinstance(data, dict) and data.get("schemaVersion") == 1, "需要 schemaVersion: 1")
    for key in ("title", "intro", "topic"):
        string(data.get(key), key)
    require(data.get("titleOrigin") in {"original", "editorial"}, "titleOrigin 需为 original 或 editorial")
    require(isinstance(data.get("source"), dict), "需要原文来源说明 source")
    string(data["source"].get("label"), "source.label")
    if "url" in data["source"]:
        safe_url(data["source"]["url"])
    paragraphs = data.get("paragraphs")
    require(isinstance(paragraphs, list) and paragraphs, "正文不能为空")
    by_id = {}
    for p in paragraphs:
        require(isinstance(p, dict), "段落必须为对象")
        require(re.fullmatch(r"p[1-9][0-9]*", p.get("id", "")) is not None, "段落 ID 如 p1")
        require(p["id"] not in by_id, "段落 ID 重复")
        string(p.get("text"), "段落原文")
        if "translation" in p:
            string(p["translation"], "段落译文")
        by_id[p["id"]] = p
    analyses = data.get("analyses", [])
    require(isinstance(analyses, list), "analyses 必须为数组，可为空")
    previous = (-1, -1)
    for index, a in enumerate(analyses, 1):
        require(a.get("id") == f"S{index:02d}", "难句编号必须按原文顺序连续，从 S01 开始")
        require(a.get("paragraph") in by_id, "难句段落不存在")
        p = by_id[a["paragraph"]]
        start, end = span(a, p["text"], a["id"])
        current = (list(by_id).index(p["id"]), start)
        require(current >= previous, "难句必须依原文排序，且不可重叠")
        previous = (current[0], end)
        require(p["text"][start:end] == a.get("text"), f"{a['id']} 原句与段落位置不一致")
        for key in ("translation", "key", "reason", "readingPath"):
            string(a.get(key), a["id"] + "." + key)
        require(isinstance(a.get("tags"), list) and a["tags"], "需要具体难点标签")
        for tag in a["tags"]:
            string(tag, "难点标签")
        require(isinstance(a.get("backbone"), dict), "需要主干")
        for key in ("en", "zh"):
            string(a["backbone"].get(key), "backbone." + key)
        segments = a.get("segments", [])
        require(isinstance(segments, list) and segments, "需要结构颜色映射")
        last = 0
        for s in segments:
            begin, finish = span(s, a["text"], "结构片段")
            require(begin >= last, "同层结构颜色不可重叠")
            require(s.get("role") in {"main", "clause", "modifier"}, "未知结构角色")
            string(s.get("label"), "结构片段标签")
            last = finish
        validate_blocks(a.get("blocks"), a["text"])
    require(isinstance(data.get("images"), dict), "需要封面及正文配图")
    for role in ("cover", "body"):
        image = data["images"].get(role)
        require(isinstance(image, dict), f"需要 {role} 图片")
        for key in ("path", "alt", "credit"):
            string(image.get(key), role + "." + key)
        require(image.get("kind") in {"photo", "illustration", "diagram"}, "图片 kind 无效")
        require(image.get("origin") in {"generated", "sourced", "user"}, "图片 origin 无效")
        if image["origin"] == "sourced":
            safe_url(image.get("sourceUrl", ""))
        if image.get("sourceUrl"):
            safe_url(image["sourceUrl"])
        require(re.fullmatch(r"(?:100|[0-9]{1,2})% (?:100|[0-9]{1,2})%", image.get("position", "50% 50%")) is not None,
                "图片 position 需为百分比，如 50% 50%")
    contexts = data.get("context", {})
    require(isinstance(contexts, dict), "context 必须按段落提供")
    for pid, words in contexts.items():
        require(pid in by_id and isinstance(words, dict), "语境义必须关联有效段落")
        for word, value in words.items():
            string(word, "语境词")
            require(word == normalize(word), "语境义键需小写")
            string(value, "语境义")
    data.setdefault("level", "考研")
    string(data["level"], "level")


def safe_url(url):
    require(isinstance(url, str) and re.match(r"^https?://[^\s]+$", url) is not None, "来源链接需为 http(s) URL")
    return html.escape(url, quote=True)


def choose_style(data, override=None):
    selection = data.get("styleSelection", {})
    require(isinstance(selection, dict), "styleSelection 必须为对象")
    if override or selection.get("selected"):
        selected = override or selection["selected"]
        require(selected in STYLES, "未知固定风格")
        return selected, selection.get("reason", "沿用已选模板" if not override else "用户指定模板")
    candidates = selection.get("candidates", [])
    require(isinstance(candidates, list), "风格 candidates 必须为数组")
    eligible = []
    for item in candidates:
        require(item.get("id") in STYLES and item.get("rank") in {"best", "usable", "unsuitable"}, "候选风格无效")
        string(item.get("reason"), "风格匹配理由")
        if item["rank"] == "best" and item.get("layoutSuitable") is True:
            image = data["images"]["cover"]
            if item["id"] == "cinema" and not image.get("overlaySafe"):
                continue
            if item["id"] == "bright" and image["kind"] != "illustration":
                continue
            eligible.append(item)
    require(len({c["id"] for c in candidates}) == len(candidates), "风格候选不可重复")
    if eligible:
        item = random.SystemRandom().choice(eligible)
        return item["id"], item["reason"]
    return "warm", "内容或图片条件不明确，使用暖纸编辑式回退"


def esc(value):
    return html.escape(str(value), quote=True)


def embed_image(image, base):
    path = (base / image["path"]).resolve()
    raw = path.read_bytes()
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif raw.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif raw.startswith((b"GIF87a", b"GIF89a")):
        mime = "image/gif"
    elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError(f"配图必须为 PNG/JPEG/GIF/WebP：{path}")
    src = "data:" + mime + ";base64," + base64.b64encode(raw).decode("ascii")
    attribution = esc(image["credit"])
    if image.get("sourceUrl"):
        attribution = f'<a href="{safe_url(image["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{attribution}</a>'
    if image["origin"] == "generated":
        attribution = "AI 生成 · " + attribution
    caption = f'<span>{esc(image.get("caption", ""))}</span><span>{attribution}</span>'
    return (f'<img src="{src}" alt="{esc(image["alt"])}" '
            f'style="object-position:{esc(image.get("position", "50% 50%"))}">', caption)


def colored(a):
    parts, offset = [], 0
    for s in a["segments"]:
        parts.append(esc(a["text"][offset:s["start"]]))
        parts.append(f'<span class="structure {s["role"]}" title="{esc(s["label"])}">{esc(a["text"][s["start"]:s["end"]])}</span>')
        offset = s["end"]
    parts.append(esc(a["text"][offset:]))
    return "".join(parts)


def prose(data):
    rendered = []
    for index, p in enumerate(data["paragraphs"], 1):
        offset, pieces = 0, []
        for a in (a for a in data.get("analyses", []) if a["paragraph"] == p["id"]):
            pieces.append(esc(p["text"][offset:a["start"]]))
            pieces.append(f'<span class="sentence" id="sentence-{a["id"]}">{colored(a)}</span>')
            pieces.append(f'<button class="sentence-number" data-sentence="{a["id"]}" aria-label="查看第 {int(a["id"][1:])} 句解析" aria-controls="drawer" aria-expanded="false">{a["id"]}</button>')
            offset = a["end"]
        pieces.append(esc(p["text"][offset:]))
        translation_attrs = ' tabindex="0" aria-keyshortcuts="Space"' if p.get("translation") else ''
        rendered.append(f'<p class="paragraph" data-paragraph="{p["id"]}" id="{p["id"]}"{translation_attrs}><span class="paragraph-number" aria-hidden="true">{index:02d}</span><span class="paragraph-text">{"".join(pieces)}</span></p>')
    return rendered


def block_html(blocks, text):
    parts = []
    for b in blocks:
        children = block_html(b["children"], text) if b.get("children") else ""
        parts.append(f'<li><h4>{esc(b["title"])}</h4><p class="block-en" lang="en">{esc(text[b["start"]:b["end"]])}</p><p>{esc(b["meaning"])}</p><p class="muted">{esc(b["explanation"])}</p>{children}</li>')
    return '<ol class="blocks">' + "".join(parts) + '</ol>'


def analysis_html(a):
    tags = " · ".join(esc(t) for t in a["tags"])
    restoration = f'<h4>语序还原</h4><p lang="en">{esc(a["restoration"])}</p>' if a.get("restoration") else ""
    return f'''<section class="analysis" id="analysis-{a['id']}">
      <h3><button class="analysis-toggle" data-analysis="{a['id']}" aria-controls="detail-{a['id']}" aria-expanded="false"><span class="analysis-label">{a['id']} <span>{tags}</span></span><span class="preview" lang="en">{esc(a['text'])}</span></button></h3>
      <div class="analysis-content" id="detail-{a['id']}" hidden>
        <p class="analysis-original" lang="en">{colored(a)}</p>
        <div class="legend"><span class="main">主干</span><span class="clause">从句</span><span class="modifier">修饰</span></div>
        <h4>整句翻译</h4><p>{esc(a['translation'])}</p>
        <h4>句子主干</h4><p class="backbone" lang="en">{esc(a['backbone']['en'])}</p><p>{esc(a['backbone']['zh'])}</p>
        <h4>读懂关键</h4><p>{esc(a['key'])}</p>
        <details class="breakdown"><summary>展开详细拆解</summary>{block_html(a['blocks'], a['text'])}{restoration}<h4>连起来理解</h4><p>{esc(a['readingPath'])}</p></details>
        <button class="return-to-text" data-return="{a['id']}">回到原文 ↗</button>
      </div></section>'''


def build(manifest, dictionary, license_path, output, override=None, force=False):
    data = json.loads(manifest.read_text(encoding="utf-8"))
    validate(data)
    style, reason = choose_style(data, override)
    all_text = "\n".join([data["title"], data.get("subtitle", ""), data["intro"]] + [p["text"] for p in data["paragraphs"]])
    lexicon = extract(dictionary, all_text)
    license_text = license_path.read_text(encoding="utf-8")
    require("Permission is hereby granted" in license_text and "Copyright" in license_text, "请提供 ECDICT 官方 MIT LICENSE")
    images = {role: embed_image(img, manifest.parent) for role, img in data["images"].items() if role in {"cover", "body"}}
    paragraphs = prose(data)
    body_image = f'<figure class="body-figure">{images["body"][0]}<figcaption>{images["body"][1]}</figcaption></figure>'
    insert = {"warm": 1, "bright": 1, "gallery": 1, "newspaper": max(1, len(paragraphs) // 2), "cinema": 0, "modern": 0, "science": 0}[style]
    if style != "cinema":
        paragraphs.insert(insert, body_image)
    source = esc(data["source"]["label"])
    if data["source"].get("url"):
        source = f'<a href="{safe_url(data["source"]["url"])}" target="_blank" rel="noopener noreferrer">{source}</a>'
    origin_note = " · Cover title supplied by the editor." if data["titleOrigin"] == "editorial" else ""
    payload = {"dictionary": lexicon, "context": data.get("context", {}),
               "translations": {p["id"]: p["translation"] for p in data["paragraphs"] if p.get("translation")},
               "uiTranslations": data.get("uiTranslations", {}), "mobileUrl": data.get("mobileUrl", ""),
               "metadata": {"templateId": style, "templateVersion": VERSION, "reason": reason,
                            "level": data["level"], "schemaVersion": 1}}
    # An application/json script is still parsed by HTML: escape literal closing tags.
    payload_json = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    count = len(data.get("analyses", []))
    substitutions = {
        "TITLE": esc(data["title"]), "SUBTITLE": esc(data.get("subtitle", "")),
        "INTRO": esc(data["intro"]), "TOPIC": esc(data["topic"]), "STYLE": style,
        "COVER_IMAGE": images["cover"][0], "COVER_CAPTION": images["cover"][1],
        "BEFORE_TITLE": body_image if style == "cinema" else "",
        "PROSE": "".join(paragraphs), "COUNT": str(count),
        "ANALYSES": "".join(analysis_html(a) for a in data.get("analyses", [])) if count else '<p class="empty">本文没有需要单独拆解的长难句，可以安心继续阅读。</p>',
        "SOURCE": source + origin_note, "LICENSE": esc(license_text),
        "DATA": payload_json, "CSS": (ROOT / "assets/reader.css").read_text(encoding="utf-8"),
        "JS": (ROOT / "assets/vendor/qrcode.js").read_text(encoding="utf-8") + "\n" + (ROOT / "assets/reader.js").read_text(encoding="utf-8")}
    template = (ROOT / "assets/reader.html").read_text(encoding="utf-8")
    template = re.sub(r"<!-- READZINE_TEMPLATE_ONLY_START -->.*?<!-- READZINE_TEMPLATE_ONLY_END -->", "", template, flags=re.S)
    result = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: substitutions[m[1]], template)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w" if force else "x", encoding="utf-8") as stream:
        stream.write(result)
    return {"output": str(output.resolve()), "bytes": output.stat().st_size,
            "templateId": style, "dictionaryMatched": lexicon["matchedCount"],
            "dictionaryTokens": lexicon["tokenCount"], "missing": lexicon["missing"], "analyses": count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--ecdict", required=True, type=Path)
    parser.add_argument("--license", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--style", choices=sorted(STYLES), help="用户指定或验证固定模板时使用")
    parser.add_argument("--force", action="store_true", help="明确允许覆盖已有输出")
    args = parser.parse_args()
    try:
        report = build(args.manifest, args.ecdict, args.license, args.output, args.style, args.force)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print("生成失败：" + str(error), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
