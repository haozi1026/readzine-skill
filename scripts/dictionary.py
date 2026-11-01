"""Extract an article-sized dictionary from an official ECDICT CSV (stdlib only)."""
import csv
import hashlib
import re
from pathlib import Path

TOKEN = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*")
SOURCE = "https://github.com/skywind3000/ECDICT"


def normalize(word):
    return word.lower().replace("’", "'")


def tokens(text):
    return {normalize(m.group()) for m in TOKEN.finditer(text)}


def exchanges(value):
    result = {}
    for item in value.split("/"):
        if ":" in item:
            key, forms = item.split(":", 1)
            result[key] = [normalize(s.strip()) for s in forms.split(",") if s.strip()]
    return result


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"word", "translation", "phonetic", "pos", "exchange"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("ECDICT CSV 缺少字段：" + ", ".join(sorted(required)))
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"ECDICT CSV 第 {reader.line_num} 行不完整或字段错位，请检查下载")
            yield row


def entry(row):
    return {"word": row["word"], "phonetic": row.get("phonetic", ""),
            "pos": row.get("pos", ""),
            "translation": row.get("translation", "").replace("\\n", "\n"),
            "definition": row.get("definition", "").replace("\\n", "\n")}


def extract(path, text):
    wanted = tokens(text)
    bases = {word[:-2] for word in wanted if word.endswith("'s")}
    direct, variants, needed = {}, {}, set()
    for row in read_rows(path):
        word = normalize(row["word"])
        forms = exchanges(row.get("exchange", ""))
        if word in wanted or word in bases:
            direct[word] = row
            needed.update(forms.get("0", []))
        # Only attested forms; no suffix guessing (e.g. news -> new).
        for kind, words in forms.items():
            if kind not in {"p", "d", "i", "3", "r", "t", "s"}:
                continue
            for form in words:
                if form in wanted and form != word:
                    variants.setdefault(form, []).append(row)
    lemmas = {}
    if needed:
        for row in read_rows(path):
            if normalize(row["word"]) in needed:
                lemmas[normalize(row["word"])] = row
    entries, lookup = {}, {}
    for word in sorted(wanted):
        row = direct.get(word)
        if row:
            base = exchanges(row.get("exchange", "")).get("0", [])
            if base and base[0] in lemmas:
                row = lemmas[base[0]]
        elif word in variants:
            # Stable tie break. Direct lexical entries take precedence.
            row = sorted(variants[word], key=lambda r: normalize(r["word"]))[0]
        elif word.endswith("'s") and word[:-2] in direct:
            row = direct[word[:-2]]
        if row:
            key = normalize(row["word"])
            entries[key] = entry(row)
            lookup[word] = key
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"entries": entries, "lookup": lookup,
            "missing": sorted(wanted - lookup.keys()),
            "source": SOURCE, "sha256": digest.hexdigest(),
            "tokenCount": len(wanted), "matchedCount": len(lookup)}
