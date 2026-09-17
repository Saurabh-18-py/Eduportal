import os
from email.utils import parseaddr

import requests
from django.core.mail.backends.base import BaseEmailBackend


class BrevoAPIEmailBackend(BaseEmailBackend):
    """
    Sends email via Brevo's HTTPS API (api.brevo.com) instead of SMTP.

    Render's free tier blocks outbound traffic on SMTP ports 25/465/587, so
    Gmail-SMTP-based sending (django.core.mail.backends.smtp.EmailBackend)
    just hangs until the request times out there. This backend sends over
    plain HTTPS instead, which isn't blocked.

    Requires the BREVO_API_KEY env var (from Brevo dashboard -> SMTP & API ->
    API Keys), and DEFAULT_FROM_EMAIL to be an email address you've verified
    as a sender in Brevo (Senders & IP -> Senders -> Add a sender).
    """

    API_URL = "https://api.brevo.com/v3/smtp/email"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = os.environ.get('BREVO_API_KEY')
        if not api_key:
            if not self.fail_silently:
                raise ValueError(
                    "BREVO_API_KEY environment variable is not set - "
                    "get one from Brevo dashboard > SMTP & API > API Keys."
                )
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                self._send_one(message, api_key)
                sent_count += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent_count

    def _send_one(self, message, api_key):
        name, email = parseaddr(message.from_email)
        payload = {
            "sender": {"email": email, "name": name or "EduPortal"},
            "to": [{"email": addr} for addr in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }

        for alt_content, mimetype in getattr(message, 'alternatives', []):
            if mimetype == 'text/html':
                payload['htmlContent'] = alt_content

        if getattr(message, 'cc', None):
            payload['cc'] = [{"email": addr} for addr in message.cc]
        if getattr(message, 'bcc', None):
            payload['bcc'] = [{"email": addr} for addr in message.bcc]

        response = requests.post(
            self.API_URL,
            json=payload,
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "accept": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()
