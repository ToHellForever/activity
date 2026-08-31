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

BASE_DIR = Path(__file__).parent.parent
PROJECT_DIR = BASE_DIR.parent
TEMPLATES_DIR = BASE_DIR / "emails"

STATIC_DIRS = [
    PROJECT_DIR / "static",
    PROJECT_DIR / "staticfiles",
]

MOCK = {
    # booking_notification.html
    "{{ booking.name }}": "Иванов Иван",
    "{{ booking.phone }}": "+7 (999) 123-45-67",
    "{{ booking.email }}": "ivan@example.com",
    "{{ event.title }}": "Форум Цифровая экономика 2026",
    "{{ event_date }}": "25.09.2026 18:00",
    "{{ booking.participants_count }}": "150",
    "{{ formats }}": "Конференция",
    "{{ booking.comment }}": "Хочу разместить презентацию",

    # email_verification.html
    "{{ code }}": "847293",

    # order_canceled.html
    "{{ event.date }}": "25.09.2026",
    "{{ event.time }}": "18:00",
    "{{ ticket.type }}": "Взрослый",
    "{{ ticket.price }}": "2250",
    "{{ ticket.quantity }}": "2",
    "{{ event.url }}": "https://example.com/event/123",
    "{{ order.payment_status }}": "canceled",

    # order_confirmation.html
    "{{ order.id }}": "12847",
    "{{ ticket.name }}": "Взрослый",
    "{{ ticket.event.title }}": "Форум Цифровая экономика 2026",
    "{{ order.quantity }}": "2",
    "{{ order.total_price }}": "4500",
    "{{ order.created_at }}": "25.08.2026 14:30",
    "{{ order.payment_status }}": "reserved",
    "{{ participant_data.name }}": "Иванов Иван Иванович",
    "{{ participant_data.email }}": "ivan@example.com",
    "{{ participant_data.phone }}": "+7 (999) 123-45-67",
    "{{ qr_codes }}": "yes",
    "{{ forloop.counter }}": "1",
    "{{ qr.qr_base64 }}": "",
    "{{ qr.qr_text }}": "TICKET-12847-001",
    "{{ payment_url }}": "https://pay.example.com/pay/12847",

    # package_purchase_confirmation.html
    "{{ user.first_name }}": "Иван",
    "{{ package.name }}": "Про Starter",
    "{{ subscription.get_subscription_type_display }}": "Базовая",
    "{{ subscription.start_date|date:'d.m.Y H:i' }}": "01.08.2026 00:00",
    "{{ subscription.end_date|date:'d.m.Y H:i' }}": "01.09.2026 00:00",
    "{{ request.get_host }}": "127.0.0.1:8080",

    # reservation_canceled.html
    "{{ order.participant_data.first_name }}": "Иван",
    "{{ event.date_time|date:'d.m.Y H:i' }}": "25.09.2026 18:00",
    "{{ order.ticket.name }}": "Взрослый",
    "{{ order.payment_status }}": "canceled",

    # reservation_reminder.html
    "{{ hours_until_event }}": "24",
    "{{ order.payment_status }}": "reserved",

    # booking_cancellation.html
    "{{ ticket.name }}": "Взрослый",
    "{{ order.quantity }}": "2",
    "{{ order.total_price }}": "4500",
    "{{ order.payment_status }}": "canceled",

    # password_reset.html
    "{{ temp_password }}": "Xk9mP2vL",
    "{{ login_url }}": "http://127.0.0.1:8080/login/",

    # booking_notification.html

}def replace_context_vars(t):
    # 1. Сначала заменяем все переменные
    for var, val in MOCK.items():
        t = t.replace(var, val)

    # 2. Обработка {% if condition %}...\n{% else %}\n...\n{% endif %}
    # Оставляем содержимое ДО {% else %}, удаляем else и endif
    t = re.sub(
        r'\{%\s*if\s+[^%]+%\}\s*([\s\S]*?)(?:\{%\s*else\s*%\})[\s\S]*?\{%\s*endif\s*%\}',
        lambda m: m.group(1).strip(),
        t
    )

    # Обработка inline {% if condition %}text{% else %}text{% endif %}
    t = re.sub(
        r'\{%\s*if\s+[^%]+%\}(.*?)\{%\s*else\s*%\}(.*?)\{%\s*endif\s*%\}',
        lambda m: m.group(1).strip(),
        t
    )

    # 3. Обработка {% if condition %}...\n...\n{% endif %} (без else)
    t = re.sub(
        r'\{%\s*if\s+[^%]+%\}([\s\S]*?)\{%\s*endif\s*%\}',
        lambda m: m.group(1).strip(),
        t
    )

    # 4. Удаляем все оставшиеся Django-теги
    t = re.sub(r'\{%\s*[^%]*?%\}', '', t)

    # 5. Удаляем оставшиеся пустые {{ }}
    t = re.sub(r'\{\{[^}]*\}\}', '', t)
    t = re.sub(r'\{\s*\}', '', t)

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
            filename = parsed.path[len("/preview/"):]
            if not filename or filename.endswith("/"):
                filename = filename.rstrip("/")
            if not filename or filename.endswith("/"):
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Template not found")
                return
            filepath = TEMPLATES_DIR / filename
            if not filepath.exists() or not filepath.is_file():
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
            rendered = rendered.replace("data:image/png;base64,", f'src="{qr_stub}"')
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(rendered.encode("utf-8"))

        elif parsed.path.startswith("/static/"):
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
