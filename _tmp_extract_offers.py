"""Временный скрипт: вытаскивает блоки offer-content из текущего шаблона оферт."""
import io
import re
import pathlib

OUT = pathlib.Path("core/legal_documents_defaults")
html = io.open("templates/other/offer.html", encoding="utf-8").read()

for match in re.finditer(r'<div class="offer-content"[^>]*data-policy-content="([a-z-]+)"[^>]*>', html):
    key = match.group(1)
    target = OUT / f"offer-{key}.html"
    if target.exists() and target.stat().st_size > 500:
        print("skip:", target.name, target.stat().st_size)
        continue
    # поиск закрывающего </div> того же уровня вложенности
    depth = 0
    pos = match.end()
    for token in re.finditer(r"<div\b|</div>", html[match.end():]):
        depth += 1 if token.group(0) == "<div" else -1
        if depth == 0:
            pos = match.end() + token.start()
            break
    body = html[match.end():pos].strip() + "\n"
    io.open(target, "w", encoding="utf-8", newline="\n").write(body)
    print("ok:", target.name, len(body))
