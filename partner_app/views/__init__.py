"""
Пакет view приложения partner_app.

Разбит на модули по доменам:
- decorators     — общие декораторы и хелперы
- dashboard      — дашборд и чаты
- events         — мероприятия и медиафайлы
- reports        — отчёты, участники, экспорт
- finances       — финансы и выплаты
- profile        — профиль и пароль
- portfolio      — портфолио
- entry_control  — контроль входа и сканер

Все имена реэкспортируются здесь, чтобы `from partner_app.views import X`
и `from . import views` продолжали работать без изменений в urls.py.
"""
from .decorators import check_partner_status, get_rejection_messages
from .dashboard import partner_dashboard, partner_chats, partner_chats_list
from .events import (
    create_event,
    edit_event,
    notify_organizer,
    partner_event_list,
    delete_event,
    bulk_delete_events,
    remove_media,
    remove_event_image,
    set_primary_image,
    send_partner_all_tickets_sold_notification,
    check_video_status,
)
from .reports import (
    reports,
    participant_list,
    export_participant_list,
    mark_attendance,
    generate_report,
    report_schedule,
    delete_reports,
)
from .finances import (
    finances,
    request_payout,
    payout_details,
    set_default_payout_detail,
    get_partner_revenue_and_commission,
)
from .profile import profile_edit, change_password, save_field
from .portfolio import (
    portfolio_list,
    portfolio_create,
    portfolio_edit,
    portfolio_delete,
    portfolio_image_delete,
)
from .entry_control import (
    enable_entry_control,
    disable_entry_control,
    toggle_entry_control,
    delete_entry_control,
    entry_control_status,
    scanner_view,
    scanner_scan,
    scanner_end_shift,
)

__all__ = [
    # decorators
    "check_partner_status",
    "get_rejection_messages",
    # dashboard
    "partner_dashboard",
    "partner_chats",
    "partner_chats_list",
    # events
    "create_event",
    "edit_event",
    "notify_organizer",
    "partner_event_list",
    "delete_event",
    "bulk_delete_events",
    "remove_media",
    "remove_event_image",
    "set_primary_image",
    "send_partner_all_tickets_sold_notification",
    "check_video_status",
    # reports
    "reports",
    "participant_list",
    "export_participant_list",
    "mark_attendance",
    "generate_report",
    "report_schedule",
    "delete_reports",
    # finances
    "finances",
    "request_payout",
    "payout_details",
    "set_default_payout_detail",
    "get_partner_revenue_and_commission",
    # profile
    "profile_edit",
    "change_password",
    "save_field",
    # portfolio
    "portfolio_list",
    "portfolio_create",
    "portfolio_edit",
    "portfolio_delete",
    "portfolio_image_delete",
    # entry_control
    "enable_entry_control",
    "disable_entry_control",
    "toggle_entry_control",
    "delete_entry_control",
    "entry_control_status",
    "scanner_view",
    "scanner_scan",
    "scanner_end_shift",
]
