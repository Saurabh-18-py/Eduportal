"""Send push notifications through Expo's push service."""
import requests

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'


def send_expo_push(tokens, title, body, data=None):
    """Returns (sent, failed, dead_tokens)."""
    sent = failed = 0
    dead = []
    tokens = [t for t in dict.fromkeys(tokens) if t]
    for i in range(0, len(tokens), 100):
        chunk = tokens[i:i + 100]
        messages = [
            {
                'to': t,
                'title': title,
                'body': body,
                'sound': 'default',
                'channelId': 'default',
                'data': data or {},
            }
            for t in chunk
        ]
        try:
            r = requests.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
                timeout=20,
            )
            r.raise_for_status()
            tickets = r.json().get('data', [])
        except Exception:
            failed += len(chunk)
            continue
        for tok, tk in zip(chunk, tickets):
            if tk.get('status') == 'ok':
                sent += 1
            else:
                failed += 1
                if (tk.get('details') or {}).get('error') == 'DeviceNotRegistered':
                    dead.append(tok)
    return sent, failed, dead
