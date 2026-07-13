"""Jalankan cloudflared, deteksi URL tunnel, kirim ke Telegram."""
import subprocess
import re
import urllib.request
import urllib.parse
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "xxxxx")
CHAT_ID = os.getenv("OWNER_USER_IDS", "xxxxxx")

CLOUDFLARED = os.path.join(os.path.dirname(__file__), "cloudflared.exe")


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=10)
        print(f"[TG] Pesan terkirim: {text}")
    except Exception as e:
        print(f"[TG] Gagal kirim: {e}")


def main():
    print("[*] Menjalankan Cloudflare Tunnel...")
    proc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "--url", "http://127.0.0.1:8000", "--protocol", "http2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    url_sent = False
    for line in proc.stdout:
        print(line, end="")
        if not url_sent:
            match = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if match:
                tunnel_url = match.group(0)
                msg = (
                    f"✅ SN Panel Online!\n\n"
                    f"🔗 URL: {tunnel_url}/login\n\n"
                    f"Panel siap diakses."
                )
                send_telegram(msg)
                url_sent = True

    proc.wait()


if __name__ == "__main__":
    main()
