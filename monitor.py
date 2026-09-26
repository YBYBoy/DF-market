from __future__ import annotations

import mimetypes
import os
import shutil
import smtplib
import tempfile
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


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


def first_visible(driver: webdriver.Chrome, selectors: tuple[str, ...]):
    for selector in selectors:
        for element in driver.find_elements(By.CSS_SELECTOR, selector):
            if element.is_displayed():
                return element
    return None


def load_url_with_retry(
    driver: webdriver.Chrome,
    url: str,
    attempts: int = 4,
) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            driver.get(url)
            WebDriverWait(driver, 30).until(
                lambda current: current.execute_script("return document.readyState")
                == "complete"
            )
            return
        except (TimeoutException, WebDriverException) as error:
            last_error = error
            if attempt == attempts:
                break
            delay = attempt * 10
            print(
                f"Website connection attempt {attempt}/{attempts} failed; "
                f"retrying in {delay} seconds"
            )
            try:
                driver.execute_script("window.stop();")
            except WebDriverException:
                pass
            time.sleep(delay)

    raise RuntimeError(
        f"Website did not become reachable after {attempts} attempts"
    ) from last_error


def login_if_needed(
    driver: webdriver.Chrome,
    site_username: str,
    site_password: str,
) -> None:
    load_url_with_retry(driver, "http://39.106.78.149/")

    password_box = first_visible(driver, ('input[type="password"]',))
    if password_box is None:
        return

    username_box = first_visible(
        driver,
        (
            'input[name="username"]',
            'input[name="user"]',
            'input[name="account"]',
            'input[type="email"]',
            'input[type="text"]',
        ),
    )
    if username_box is None:
        raise RuntimeError("Login page found, but the username field was not found")

    username_box.clear()
    username_box.send_keys(site_username)
    password_box.clear()
    password_box.send_keys(site_password)

    submit_button = first_visible(
        driver,
        ('button[type="submit"]', 'input[type="submit"]'),
    )
    if submit_button is not None:
        submit_button.click()
    else:
        password_box.send_keys(Keys.ENTER)

    try:
        WebDriverWait(driver, 30).until(
            lambda current: current.find_elements(By.ID, "floating-gun-bar")
            or "T0 / T1" in current.page_source
        )
    except TimeoutException as error:
        raise RuntimeError("Website login did not reach the market page") from error


def capture(
    chrome: str,
    output_dir: Path,
    site_username: str,
    site_password: str,
) -> list[Path]:
    screenshots: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="market-monitor-") as profile:
        options = webdriver.ChromeOptions()
        options.binary_location = chrome
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--hide-scrollbars")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument(f"--user-data-dir={profile}")
        options.add_argument("--window-size=1000,1200")

        driver = webdriver.Chrome(options=options)
        try:
            driver.set_page_load_timeout(60)
            login_if_needed(driver, site_username, site_password)

            for filename, window_size, url in PAGES:
                output = output_dir / filename
                width, height = (int(value) for value in window_size.split(",", 1))
                driver.set_window_size(width, height)
                load_url_with_retry(driver, url)
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.ID, "floating-gun-bar"))
                )
                if first_visible(driver, ('input[type="password"]',)) is not None:
                    raise RuntimeError("Website session returned to the login page")
                time.sleep(3)
                driver.save_screenshot(str(output))
                if not output.exists() or output.stat().st_size < 1024:
                    raise RuntimeError(f"Invalid screenshot: {output}")
                screenshots.append(output)
        finally:
            driver.quit()
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
    site_username = os.environ.get("SITE_USERNAME", "").strip()
    site_password = os.environ.get("SITE_PASSWORD", "").strip()
    if not all((email_address, auth_code, site_username, site_password)):
        raise RuntimeError(
            "QQ_EMAIL, QQ_SMTP_AUTH_CODE, SITE_USERNAME and SITE_PASSWORD secrets are required"
        )

    output_dir = Path("screenshots")
    output_dir.mkdir(exist_ok=True)
    screenshots = capture(
        find_chrome(),
        output_dir,
        site_username,
        site_password,
    )
    send_email(email_address, auth_code, screenshots)
    print("Screenshots captured and email sent successfully")


if __name__ == "__main__":
    main()
