#!/usr/bin/env python3
"""What the editor knows about a scene's records.

`pleamar --lsp` is driven over its stdin the way an editor drives it: a scene is
opened, and then, inside `for r in rows { … }`, the fields offered after `r.`, where
`r.label` goes, and what that word says on hover. It is the half of G9 the compiler
already knew —which model each `for` reads— reaching the editor.

    python3 scripts/test-lsp.py ./target/release/pleamar

Exits 0 when all of it holds, and 1 with what came instead when it does not.
"""
import json
import subprocess
import sys

SCENE = """language 0.4
scene Lsp {
    surface { size: 200, 100 }
    model rows max 4 { label: text; enabled: bool = true }
    fact shown = false

    column list { at: 0, 0
        for r in rows {
            text r.label { at: 0, 0; show: r.enabled }
            box { at: 0, 20; size: 10, 10; show: shown }
        }
    }
}
"""

URI = "file:///tmp/pleamar-lsp-test.plm"
LINES = SCENE.split("\n")


def frame(msg):
    body = json.dumps(msg).encode()
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def read_answer(out):
    headers = b""
    while not headers.endswith(b"\r\n\r\n"):
        b = out.read(1)
        if not b:
            raise SystemExit("the language server closed before answering")
        headers += b
    length = int(headers.decode().split("Content-Length:")[1].split("\r\n")[0])
    return json.loads(out.read(length))


def ask(proc, msg):
    """One request, one answer: the notifications in between are read past."""
    proc.stdin.write(frame(msg))
    proc.stdin.flush()
    while True:
        body = read_answer(proc.stdout)
        if body.get("id") == msg["id"]:
            return body.get("result")


def main(binary):
    line = next(i for i, l in enumerate(LINES) if "text r.label" in l)
    after_dot = (line, LINES[line].index("r.label") + 2)
    on_label = (line, LINES[line].index("r.label") + 3)
    # A name written on its own, not after a dot: a model's fields do not belong there.
    bare = (line, LINES[line].index("r.label"))
    model = next(i for i, l in enumerate(LINES) if "model rows" in l)
    field_col = LINES[model].index("label")

    proc = subprocess.Popen([binary, "--lsp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        ask(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}})
        proc.stdin.write(frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": URI, "languageId": "plm", "version": 1, "text": SCENE}}}))
        proc.stdin.flush()

        def at(method, where, id):
            return ask(proc, {"jsonrpc": "2.0", "id": id, "method": method, "params": {"textDocument": {"uri": URI}, "position": {"line": where[0], "character": where[1]}}})

        fields = sorted(i["label"] for i in at("textDocument/completion", after_dot, 2)["items"])
        plain = sorted(i["label"] for i in at("textDocument/completion", bare, 3)["items"])
        where = at("textDocument/definition", on_label, 4)
        hover = (at("textDocument/hover", on_label, 5) or {}).get("contents", {}).get("value", "")
        ask(proc, {"jsonrpc": "2.0", "id": 6, "method": "shutdown"})
        proc.stdin.write(frame({"jsonrpc": "2.0", "method": "exit"}))
        proc.stdin.flush()
    finally:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    bad = []
    if fields != ["enabled", "index", "label"]:
        bad.append(f"after `r.` it offered {fields}, and the model's fields and `index` were due")
    if "label" in plain:
        bad.append("a model's field was offered where no dot came before it")
    start = (where or {}).get("range", {}).get("start", {})
    if (start.get("line"), start.get("character")) != (model, field_col):
        bad.append(f"`r.label` went to {start.get('line')}:{start.get('character')}, and the field is at {model}:{field_col}")
    if "rows.label" not in hover or "field" not in hover:
        bad.append(f"hover on `r.label` said {hover!r}")
    for b in bad:
        print(b)
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: test-lsp.py <path to pleamar>")
    sys.exit(main(sys.argv[1]))
