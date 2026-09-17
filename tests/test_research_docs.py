import runpy
import hashlib
import json
from unittest.mock import patch

MODULE = runpy.run_path("scripts/research_docs.py")


def test_research_scope():
    scope = MODULE["in_scope"]
    assert scope("https://fluxcd.io/flux/installation/", "https://fluxcd.io/flux/")
    assert not scope("https://fluxcd.io/blog/", "https://fluxcd.io/flux/")
    assert not scope("https://docs.gitea.com/1.22/installation/", "https://docs.gitea.com/")
    assert not scope("https://elsewhere.test/", "https://docs.gitea.com/")


def test_canonical_removes_query_fragment():
    assert MODULE["canonical"]("https://flox.dev/docs?a=1#x") == "https://flox.dev/docs/"


def test_article_code_is_not_truncated():
    code = "line one\n  indented\n" + "x" * 12000
    title, text, html = MODULE["extract"](
        "<title>Example</title><main><nav>menu</nav><h1>Article</h1>"
        "<pre>" + code + "</pre></main>"
    )
    assert title == "Example"
    assert code in text
    assert "```" in text
    assert "menu" not in text
    assert "<pre>" in html


def test_highlighted_code_lines_keep_newlines_and_indentation():
    text = MODULE["article_text"](
        '<pre><code><div class="ec-line"><div class="code">services:</div></div>'
        '<div class="ec-line"><div class="code">  runner:</div></div></code></pre>'
    )
    assert "services:\n  runner:" in text
    text = MODULE["article_text"](
        '<pre><code><span class="line">one</span>\n<span class="line">  two</span></code></pre>'
    )
    assert "one\n  two" in text


def test_periodic_audit_detects_corrupted_article(tmp_path):
    watcher = runpy.run_path("scripts/watch_research_docs.py")
    (tmp_path / "status.json").write_text(json.dumps({
        "pid": 123, "phase": "crawl", "sources": {"kind": {"saved": 1}}, "ai": {},
    }))
    page = {"url": "https://kind.sigs.k8s.io/", "article_html": "changed",
            "article_sha256": hashlib.sha256(b"original").hexdigest()}
    (tmp_path / "kind.pages.jsonl").write_text(json.dumps(page) + "\n")
    (tmp_path / "kind.source.md").write_text("\n\nSource: https://kind.sigs.k8s.io/\n")
    with patch("os.kill"):
        result = watcher["audit"](tmp_path)
    assert result["findings"] == ["kind: article checksum mismatch"]
