from __future__ import annotations

import mimetypes
import os
import shutil
import smtplib
import subprocess
import tempfile
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo


PAGES = (
    (
        "T0-T1.png",
        "1000,1350",
        "http://39.106.78.149/api/market/index.php?gun_name=__t0_t1_templates__&page=1",
    ),
    (
        "triple.png",
        "1000,1800",
        "http://39.106.78.149/api/market/index.php?gun_name=__triple__&page=1",
    ),
)


def find_chrome() -> str:
    for executable in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(executable)
        if path:
            return path
    raise RuntimeError("Chrome or Chromium was not found on the GitHub runner")


def capture(chrome: str, output_dir: Path) -> list[Path]:
    screenshots: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="market-monitor-") as profile:
        for filename, window_size, url in PAGES:
            output = output_dir / filename
            command = [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--hide-scrollbars",
                "--no-first-run",
                "--no-default-browser-check",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=8000",
                f"--user-data-dir={profile}",
                f"--window-size={window_size}",
                f"--screenshot={output}",
                url,
            ]
            subprocess.run(command, check=True, timeout=90)
            if not output.exists() or output.stat().st_size < 1024:
                raise RuntimeError(f"Invalid screenshot: {output}")
            screenshots.append(output)
    return screenshots


def send_email(email_address: str, auth_code: str, screenshots: list[Path]) -> None:
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    message = EmailMessage()
    message["From"] = email_address
    message["To"] = email_address
    message["Subject"] = f"Delta Force skin market monitor {timestamp}"
    message.set_content(
        f"Captured at: {timestamp}\n"
        "Attachment 1: T0/T1\n"
        "Attachment 2: Triple\n"
    )

    for screenshot in screenshots:
        mime_type, _ = mimetypes.guess_type(screenshot.name)
        main_type, sub_type = (mime_type or "image/png").split("/", 1)
        message.add_attachment(
            screenshot.read_bytes(),
            maintype=main_type,
            subtype=sub_type,
            filename=screenshot.name,
        )

    with smtplib.SMTP("smtp.qq.com", 587, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(email_address, auth_code)
        smtp.send_message(message)


def main() -> None:
    email_address = os.environ.get("QQ_EMAIL", "").strip()
    auth_code = os.environ.get("QQ_SMTP_AUTH_CODE", "").strip()
    if not email_address or not auth_code:
        raise RuntimeError("QQ_EMAIL and QQ_SMTP_AUTH_CODE secrets are required")

    output_dir = Path("screenshots")
    output_dir.mkdir(exist_ok=True)
    screenshots = capture(find_chrome(), output_dir)
    send_email(email_address, auth_code, screenshots)
    print("Screenshots captured and email sent successfully")


if __name__ == "__main__":
    main()

