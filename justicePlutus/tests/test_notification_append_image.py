from types import SimpleNamespace

from src.notification import NotificationChannel, NotificationService
from src.core.pipeline import StockAnalysisPipeline
from src.enums import ReportType


def build_test_notifier(
    channels,
    append_image_after_text_notify,
    markdown_to_image_channels=None,
):
    notifier = NotificationService.__new__(NotificationService)
    notifier._source_message = None
    notifier._available_channels = list(channels)
    notifier._markdown_to_image_channels = set(markdown_to_image_channels or [])
    notifier._markdown_to_image_max_chars = 15000
    notifier._append_image_after_text_notify = append_image_after_text_notify
    notifier._stock_email_groups = []
    notifier.send_to_context = lambda content: False
    notifier.get_all_email_receivers = lambda: []
    notifier.get_receivers_for_stocks = lambda stock_codes: []
    return notifier


def build_test_pipeline(
    channels,
    append_image_after_text_notify,
    markdown_to_image_channels=None,
):
    pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
    pipeline.run_output_dir = None
    pipeline.config = SimpleNamespace(stock_email_groups=[])
    pipeline.notifier = build_test_notifier(
        channels=channels,
        append_image_after_text_notify=append_image_after_text_notify,
        markdown_to_image_channels=markdown_to_image_channels,
    )
    pipeline.notifier.is_available = lambda: True
    pipeline.notifier.get_available_channels = lambda: list(channels)
    pipeline.notifier.save_report_to_file = (
        lambda content, filename=None: "/tmp/summary.md"
    )
    pipeline._generate_aggregate_report = (
        lambda results, report_type: "summary-report"
    )
    return pipeline


def build_result():
    return SimpleNamespace(code="600519")


def test_send_appends_png_after_text_when_switch_enabled(monkeypatch):
    notifier = build_test_notifier(
        channels=[NotificationChannel.TELEGRAM],
        append_image_after_text_notify=True,
    )
    events = []
    notifier.send_to_telegram = lambda content: events.append(("text", content)) or True
    notifier._send_telegram_photo = (
        lambda image_bytes: events.append(("image", image_bytes)) or True
    )
    monkeypatch.setattr(
        "src.md2img.markdown_to_image",
        lambda content, max_chars=15000: b"png",
    )

    assert notifier.send("hello") is True
    assert events == [("text", "hello"), ("image", b"png")]


def test_send_keeps_text_success_when_image_render_fails(monkeypatch):
    notifier = build_test_notifier(
        channels=[NotificationChannel.TELEGRAM],
        append_image_after_text_notify=True,
    )
    events = []
    notifier.send_to_telegram = lambda content: events.append(("text", content)) or True
    notifier._send_telegram_photo = (
        lambda image_bytes: events.append(("image", image_bytes)) or True
    )
    monkeypatch.setattr(
        "src.md2img.markdown_to_image",
        lambda content, max_chars=15000: None,
    )

    assert notifier.send("hello") is True
    assert events == [("text", "hello")]


def test_send_preserves_legacy_replace_with_image_mode_when_append_switch_off(monkeypatch):
    notifier = build_test_notifier(
        channels=[NotificationChannel.TELEGRAM],
        append_image_after_text_notify=False,
        markdown_to_image_channels={"telegram"},
    )
    events = []
    notifier.send_to_telegram = lambda content: events.append(("text", content)) or True
    notifier._send_telegram_photo = (
        lambda image_bytes: events.append(("image", image_bytes)) or True
    )
    monkeypatch.setattr(
        "src.md2img.markdown_to_image",
        lambda content, max_chars=15000: b"png",
    )

    assert notifier.send("hello") is True
    assert events == [("image", b"png")]


def test_send_notifications_appends_image_after_summary_text(monkeypatch):
    pipeline = build_test_pipeline(
        channels=[NotificationChannel.TELEGRAM],
        append_image_after_text_notify=True,
    )
    events = []
    pipeline.notifier.send_to_telegram = lambda content: events.append(("text", content)) or True
    pipeline.notifier._send_telegram_photo = (
        lambda image_bytes: events.append(("image", image_bytes)) or True
    )
    monkeypatch.setattr(
        "src.md2img.markdown_to_image",
        lambda content, max_chars=15000: b"png",
    )

    pipeline._send_notifications([build_result()], ReportType.SIMPLE)

    assert events == [("text", "summary-report"), ("image", b"png")]


def test_send_notifications_appends_wechat_image_after_dashboard_text(monkeypatch):
    pipeline = build_test_pipeline(
        channels=[NotificationChannel.WECHAT],
        append_image_after_text_notify=True,
    )
    events = []
    pipeline.notifier.generate_wechat_dashboard = lambda results: "wechat-content"
    pipeline.notifier.send_to_wechat = lambda content: events.append(("text", content)) or True
    pipeline.notifier._send_wechat_image = (
        lambda image_bytes: events.append(("image", image_bytes)) or True
    )
    monkeypatch.setattr(
        "src.md2img.markdown_to_image",
        lambda content, max_chars=15000: b"png",
    )

    pipeline._send_notifications([build_result()], ReportType.SIMPLE)

    assert events == [("text", "wechat-content"), ("image", b"png")]


def test_send_notifications_keeps_wechat_text_when_png_is_oversized(monkeypatch):
    pipeline = build_test_pipeline(
        channels=[NotificationChannel.WECHAT],
        append_image_after_text_notify=True,
    )
    events = []
    pipeline.notifier.generate_wechat_dashboard = lambda results: "wechat-content"
    pipeline.notifier.send_to_wechat = lambda content: events.append(("text", content)) or True
    pipeline.notifier._send_wechat_image = (
        lambda image_bytes: events.append(("image", image_bytes)) or True
    )
    monkeypatch.setattr(
        "src.md2img.markdown_to_image",
        lambda content, max_chars=15000: b"x" * (2 * 1024 * 1024 + 1),
    )

    pipeline._send_notifications([build_result()], ReportType.SIMPLE)

    assert events == [("text", "wechat-content")]
