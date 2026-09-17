"""Periodically compare crawl status with the files actually saved on disk."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time


def audit(root):
    state = json.loads((root / "status.json").read_text())
    findings = []
    sources = {}
    for name, stats in state["sources"].items():
        path = root / (name + ".pages.jsonl")
        data = []
        if path.exists():
            lines = path.read_text().splitlines()
            for index, line in enumerate(lines):
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    if index != len(lines) - 1:
                        findings.append(name + ": corrupt interior JSONL record")
        unique = {p["url"] for p in data}
        if len(unique) != len(data):
            findings.append(name + ": duplicate URLs")
        if any(hashlib.sha256(p["article_html"].encode()).hexdigest() != p["article_sha256"] for p in data):
            findings.append(name + ": article checksum mismatch")
        reported = stats.get("saved", 0)
        if abs(len(data) - reported) > 1:
            findings.append(name + ": status/file count mismatch")
        markdown = root / (name + ".source.md")
        sections = markdown.read_text().count("\n\nSource: https://") if markdown.exists() else 0
        if abs(sections - len(data)) > 1:
            findings.append(name + ": readable bundle/ledger count mismatch")
        sources[name] = dict(records=len(data), reported=reported, readable_sections=sections)
    count = len(list(root.iterdir()))
    if count > 300:
        findings.append("File limit exceeded")
    try:
        os.kill(state["pid"], 0)
        running = True
    except ProcessLookupError:
        running = False
    except PermissionError:
        running = None
    if running is False and state["phase"] != "finished":
        findings.append("Scraper exited before completion")
    return dict(time=time.time(), phase=state["phase"], scraper_running=running,
                files=count, sources=sources, ai=state["ai"], findings=findings)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    while True:
        result = audit(args.output)
        temp = args.output / "audit.tmp"
        temp.write_text(json.dumps(result, indent=2))
        temp.replace(args.output / "audit.json")
        with (args.output / "audit.jsonl").open("a") as handle:
            handle.write(json.dumps(result) + "\n")
        print(json.dumps(result), flush=True)
        if result["phase"] == "finished" or result["scraper_running"] is False:
            break
        time.sleep(30)
