"""
Email Preview Server.
Запуск: python templates/emails/preview_server.py
Откройте http://127.0.0.1:8080 в браузере.
"""
import re
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent  # D:\python\activity	emplates
PROJECT_DIR = BASE_DIR.parent  # D:\python\activity
TEMPLATES_DIR = BASE_DIR / "emails"

# Статические папки для раздачи
STATIC_DIRS = [
    PROJECT_DIR / "static",
    PROJECT_DIR / "staticfiles",
]

MOCK = {
    "{{ order.id }}": "12847",
    "{{ order.quantity }}": "2",
    "{{ order.total_price }}": "4500",
    "{{ order.created_at }}": "25.08.2026 14:30",
    "{{ ticket.name }}": "Взрослый",
    "{{ ticket.event.title }}": "Форум Цифровая экономика 2026",
    "{{ ticket.event.date_time|date:'d.m.Y H:i' }}": "25.09.2026 18:00",
    "{{ ticket.event.place }}": "г. Новосибирск, ул. Красный проспект, 1",
    "{{ order.ticket.name }}": "Взрослый",
    "{{ order.ticket.event.title }}": "Форум Цифровая экономика 2026",
    "{{ order.ticket.event.date_time|date:'d.m.Y H:i' }}": "25.09.2026 18:00",
    "{{ order.ticket.event.place }}": "г. Новосибирск, ул. Красный проспект, 1",
    "{{ order.payment_deadline|date:'d.m.Y H:i' }}": "27.08.2026 12:00",
    "{{ payment_link }}": "https://example.com/pay/12847",
    "{{ participant_data.name }}": "Иванов Иван Иванович",
    "{{ participant_data.email }}": "ivan@example.com",
    "{{ participant_data.phone }}": "+7 (999) 123-45-67",
    "{{ qr_codes }}": "yes",
    "{{ qr.qr_base64 }}": "",
    "{{ qr.qr_text }}": "TICKET-12847-001",
    "{{ payment_url }}": "https://pay.example.com/pay/12847",
    "{{ order.participant_data.first_name }}": "Иван",
    "{{ event.title }}": "Форум Цифровая экономика 2026",
    "{{ order.ticket.name }}": "Взрослый",
    "{{ site_name }}": "БИЗНЕС АФИША",
    "{{ user.first_name }}": "Иван",
    "{{ package.name }}": "Про Starter",
    "{{ subscription.get_subscription_type_display }}": "Базовая",
    "{{ subscription.start_date|date:'d.m.Y H:i' }}": "01.08.2026 00:00",
    "{{ subscription.end_date|date:'d.m.Y H:i' }}": "01.09.2026 00:00",
    "{{ event.date_time|date:'d.m.Y H:i' }}": "25.09.2026 18:00",
    "{{ request.get_host }}": "127.0.0.1:8080",
    "{{ forloop.counter }}": "1",
}

DJANGO_TAGS = re.compile(r"\{%.*?%\}", re.DOTALL)


def replace_context_vars(t):
    # Сначала заменяем переменные
    for var, val in MOCK.items():
        t = t.replace(var, val)
    # Удаляем все Django-теги (включая for/if/url)
    t = DJANGO_TAGS.sub("", t)
    # Удаляем оставшиеся пустые { }
    t = re.sub(r"\{\s*\}", "", t)
    return t


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            templates = sorted(
                [
                    f.name
                    for f in TEMPLATES_DIR.iterdir()
                    if f.suffix == ".html" and f.name != "preview_server.py"
                ]
            )
            links = "".join(
                '<a href="/preview/' + t + '" class="tpl-link">' + t + '</a>' for t in templates
            )
            html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Email Preview</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; display: flex; min-height: 100vh; background: #1a1a2e; color: #fff; }}
.sidebar {{ width: 300px; background: #16213e; padding: 20px 0; overflow-y: auto; flex-shrink: 0; border-right: 1px solid #0f3460; }}
.sidebar h2 {{ padding: 0 20px 16px; font-size: 1rem; color: #e94560; border-bottom: 1px solid #0f3460; margin-bottom: 12px; }}
.tpl-link {{ display: block; padding: 10px 20px; color: #a8a8b8; text-decoration: none; font-size: 0.82rem; border-left: 3px solid transparent; transition: all 0.2s; word-break: break-word; }}
.tpl-link:hover {{ background: #0f3460; color: #fff; border-left-color: #e94560; }}
.tpl-link.active {{ background: #0f3460; color: #e94560; border-left-color: #e94560; }}
.content {{ flex: 1; padding: 24px; overflow-y: auto; background: #f0f0f0; }}
iframe {{ width: 100%; height: calc(100vh - 48px); border: 1px solid #ddd; border-radius: 8px; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
</style>
</head>
<body>
<div class="sidebar">
    <h2>Email Preview</h2>
    {links}
</div>
<div class="content">
    <iframe id="preview-frame" src=""></iframe>
</div>
<script>
const links = document.querySelectorAll('.tpl-link');
const frame = document.getElementById('preview-frame');
links.forEach(link => {{
    link.addEventListener('click', function(e) {{
        links.forEach(l => l.classList.remove('active'));
        this.classList.add('active');
        frame.src = this.getAttribute('href');
    }});
}});
if (links.length > 0) {{
    links[0].classList.add('active');
    frame.src = links[0].getAttribute('href');
}}
</script>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        elif parsed.path.startswith("/preview/"):
            filename = parsed.path[len("/preview/") :]
            filepath = TEMPLATES_DIR / filename
            if not filepath.exists():
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Template not found")
                return
            with open(filepath, "r", encoding="utf-8") as f:
                tc = f.read()
            rendered = replace_context_vars(tc)
            qr_stub = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTUwIiBoZWlnaHQ9IjE1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTUwIiBoZWlnaHQ9IjE1MCIgZmlsbD0iI2ZmZiIgc3Ryb2tlPSIjZGRkIiBzdHJva2Utd2lkdGg9IjIiLz48dGV4dCB4PSI3NSIgeT0iNzUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0iIzk5OSI+UVItY29kZTwvdGV4dD48L3N2Zz4="
            rendered = rendered.replace("data:image/png;base64,[данные]", f'src="{qr_stub}"')
            rendered = rendered.replace("src=\"data:image/png;base64,[данные]\"", f'src="{qr_stub}"')
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(rendered.encode("utf-8"))

        elif parsed.path.startswith("/static/"):
            # Раздача статических файлов из static/ и staticfiles/
            static_path = parsed.path[len("/static/"):]
            for static_dir in STATIC_DIRS:
                target = static_dir / static_path
                if target.exists() and target.is_file():
                    self.send_response(200)
                    content_type, _ = mimetypes.guess_type(str(target))
                    if content_type:
                        self.send_header("Content-Type", content_type)
                    self.end_headers()
                    with open(target, "rb") as f:
                        self.wfile.write(f.read())
                    return
            self.send_response(404)
            self.end_headers()

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def run(port=8080):
    server = HTTPServer(("127.0.0.1", port), Handler)
    print()
    print("=" * 50)
    print("  Email Preview Server запущен!")
    print(f"  Откройте: http://127.0.0.1:{port}")
    print(f"  Папка: {TEMPLATES_DIR}")
    templates = sorted(
        [
            f.name
            for f in TEMPLATES_DIR.iterdir()
            if f.suffix == ".html" and f.name != "preview_server.py"
        ]
    )
    print(f"  Шаблонов: {len(templates)}")
    for t in templates:
        print(f"    - {t}")
    print("=" * 50)
    print()
    print("Нажмите Ctrl+C для остановки.")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
        server.server_close()


if __name__ == "__main__":
    run()
