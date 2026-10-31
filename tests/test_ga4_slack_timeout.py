from unittest.mock import patch

from ga4_report.slack import send_webhook


def test_send_webhook_default_timeout():
    with patch("ga4_report.slack.urllib.request.urlopen") as m:
        m.return_value.__enter__.return_value.status = 200
        send_webhook("http://x", [])
    assert m.call_args.kwargs["timeout"] == 60
