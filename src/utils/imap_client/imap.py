import asyncio
import re
import ssl
from datetime import datetime, timezone, timedelta
from imaplib import IMAP4_SSL
from typing import Optional, Literal
from urllib.parse import urlparse

import httpx
from loguru import logger
from imap_tools import MailBox

from config import REDIRECT, MAIN_ICLOUD_EMAIL_LOGIN, APP_PASSWORD
from src.utils.proxy_manager import Proxy


class MailBoxClient(MailBox):
    def __init__(
            self,
            host: str,
            *,
            proxy: Proxy | None,
            port: int = 993,
            timeout: float = None,
            ssl_context=None,
    ):
        self._proxy = proxy
        super().__init__(host=host, port=port, timeout=timeout, ssl_context=ssl_context)
        if self._proxy:
            self.parsed_proxy = self._parse_proxy(self._proxy.proxy_url)

    @staticmethod
    def _parse_proxy(proxy_url: str) -> dict:
        parsed = urlparse(proxy_url)
        return {
            'scheme': parsed.scheme,
            'host': parsed.hostname,
            'port': parsed.port,
            'username': parsed.username,
            'password': parsed.password,
        }

    def _get_mailbox_client(self):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        if self._proxy:
            proxy = self.parsed_proxy
            return IMAP4_SSL(
                proxy['host'],
                port=proxy['port'],
                timeout=self._timeout,
                ssl_context=ssl_context,
            )
        else:
            return IMAP4_SSL(
                self._host,
                port=self._port,
                timeout=self._timeout,
                ssl_context=ssl_context,
            )

    def login(self, username: str, password: str, initial_folder: str = "INBOX"):
        """
        Спец-формат пароля:
          - MS:     oauth2:ms:<client_id>:<refresh_token>:<client_secret?>
          - Gmail:  oauth2:google:<client_id>:<refresh_token>:<client_secret?>
        iCloud OAuth2 не поддерживает — используйте app-specific password.
        """
        if isinstance(password, str) and password.lower().startswith("oauth2:"):
            try:
                provider, payload = password.split(":", 2)[1:]
            except ValueError:
                provider, payload = "", ""

            p = provider.lower()

            if p in ("ms", "microsoft"):
                parts = payload.split(":")
                if len(parts) < 2:
                    raise ValueError("Invalid OAuth2 password format for Microsoft")
                client_id = parts[0]
                refresh_token = parts[1]
                client_secret = parts[2] if len(parts) >= 3 and parts[2] else None

                access_token = self._get_ms_access_token(client_id, refresh_token, client_secret)
                super().xoauth2(username, access_token, initial_folder=initial_folder)
                return self

            if p in ("google", "gmail"):
                parts = payload.split(":")
                if len(parts) < 2:
                    raise ValueError("Invalid OAuth2 password format for Google")
                client_id = parts[0]
                refresh_token = parts[1]
                client_secret = parts[2] if len(parts) >= 3 and parts[2] else None

                access_token = self._get_google_access_token(client_id, refresh_token, client_secret)
                super().xoauth2(username, access_token, initial_folder=initial_folder)
                return self

            if p in ("icloud", "apple"):
                raise ValueError("iCloud IMAP does not support OAuth2; use an app-specific password.")

            raise ValueError(f"Unsupported OAuth2 provider: {provider}")
        return super().login(username, password, initial_folder=initial_folder)

    def _get_ms_access_token(self, client_id: str, refresh_token: str, client_secret: Optional[str]) -> str:
        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        data = {
            "client_id": client_id,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        if client_secret:
            data["client_secret"] = client_secret

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        proxies = self._proxy.proxy_url if getattr(self, "_proxy", None) else None

        resp = httpx.post(token_url, data=data, headers=headers, timeout=20, proxy=proxies)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("error_description") or resp.json().get("error") or resp.text
            except Exception:
                detail = resp.text
            raise RuntimeError(f"OAuth error: {detail}")

        access_token = resp.json().get("access_token")
        if not access_token:
            raise RuntimeError("OAuth error: access_token not present in response")
        return access_token

    def _get_google_access_token(self, client_id: str, refresh_token: str, client_secret: Optional[str]) -> str:
        """
        Gmail IMAP XOAUTH2. При получении refresh_token приложение должно было запрашивать scope:
        https://mail.google.com/
        """
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": client_id,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        if client_secret:
            data["client_secret"] = client_secret

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        proxies = self._proxy.proxy_url if getattr(self, "_proxy", None) else None

        resp = httpx.post(token_url, data=data, headers=headers, timeout=20, proxy=proxies)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("error_description") or resp.json().get("error") or resp.text
            except Exception:
                detail = resp.text
            raise RuntimeError(f"OAuth error (Google): {detail}")

        access_token = resp.json().get("access_token")
        if not access_token:
            raise RuntimeError("OAuth error (Google): access_token not present in response")
        return access_token


class AsyncEmailChecker:
    def __init__(
        self,
        email: str,
        password: Optional[str],
        *,
        oauth_provider: Optional[Literal['ms', 'microsoft', 'google']] = None,
        client_id: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """
        Если переданы oauth_*:
          - microsoft → password = "oauth2:ms:<client_id>:<refresh_token>:<client_secret?>"
          - google    → password = "oauth2:google:<client_id>:<refresh_token>:<client_secret?>"
        iCloud: используем обычный password = app-specific password (без OAuth2).
        """
        self.email = email
        self.oauth_provider = oauth_provider.lower() if oauth_provider else None

        if self.oauth_provider in ("ms", "microsoft") and client_id and refresh_token:
            secret = client_secret or ""
            self.password = f"oauth2:ms:{client_id}:{refresh_token}:{secret}"
        elif self.oauth_provider in ("google", "gmail") and client_id and refresh_token:
            secret = client_secret or ""
            self.password = f"oauth2:google:{client_id}:{refresh_token}:{secret}"
        else:
            self.password = password

        self.imap_server = self._get_imap_server(email)

        if self.oauth_provider in ("google", "gmail"):
            self.imap_server = "imap.gmail.com"
        elif self.oauth_provider in ("icloud", "apple"):
            self.imap_server = "imap.mail.me.com"

        if REDIRECT:
            self.email = MAIN_ICLOUD_EMAIL_LOGIN
            self.password = APP_PASSWORD
            self.secret_mail = email

        self.search_start_time = datetime.now(timezone.utc)

    def _get_imap_server(self, email: str) -> str:
        e = email.lower()
        if e.endswith("@rambler.ru"):
            return "imap.rambler.ru"
        elif e.endswith("@gmail.com"):
            return "imap.gmail.com"
        elif "@gmx." in e:
            return "imap.gmx.com"
        elif e.endswith(("@outlook.com", "@hotmail.com")):
            return "imap-mail.outlook.com"
        elif e.endswith("@mail.ru"):
            return "imap.mail.ru"
        elif e.endswith(("@icloud.com", "@me.com", "@mac.com")):
            return "imap.mail.me.com"  # iCloud IMAP
        else:
            return "imap.firstmail.ltd"

    def _search_for_pattern(
            self, mailbox: MailBox, pattern: str | re.Pattern, is_regex: bool = True
    ) -> Optional[str]:
        time_threshold = self.search_start_time - timedelta(seconds=60)

        messages = sorted(
            mailbox.fetch(criteria=f'TO "{self.secret_mail}"' if REDIRECT else 'ALL'),
            key=lambda x: (x.date.replace(tzinfo=timezone.utc) if x.date.tzinfo is None else x.date),
            reverse=True,
        )
        rx = re.compile(pattern) if is_regex and isinstance(pattern, str) else pattern

        for msg in messages:
            # if REDIRECT:
            #     if self.secret_mail not in msg.to:
            #         continue

            msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
            if msg_date < time_threshold:
                continue

            subject = msg.subject or ""
            text = msg.text or ""
            html = msg.html or ""

            if is_regex:
                if rx:
                    m = rx.search(subject)
                    if m:
                        return m.group(0)
                    m = rx.search(text)
                    if m:
                        return m.group(0)
                    m = rx.search(html)
                    if m:
                        return m.group(0)
            else:
                if pattern in subject or pattern in text or pattern in html:
                    return pattern

        return None

    def _search_for_pattern_in_spam(
            self,
            mailbox: MailBox,
            spam_folder: str,
            pattern: str | re.Pattern,
            is_regex: bool = True,
    ) -> Optional[str]:
        if mailbox.folder.exists(spam_folder):
            mailbox.folder.set(spam_folder)
            return self._search_for_pattern(mailbox, pattern, is_regex)
        return None

    async def check_email_for_verification_link(
            self,
            pattern: str | re.Pattern,
            is_regex: bool = True,
            max_attempts: int = 20,
            delay_seconds: int = 3,
            proxy: Optional[Proxy] = None,
    ) -> Optional[str]:
        try:
            for attempt in range(max_attempts):
                def search_inbox():
                    with MailBoxClient(self.imap_server, proxy=proxy, timeout=30).login(
                            self.email, self.password
                    ) as mailbox:
                        return self._search_for_pattern(mailbox, pattern, is_regex)

                result = await asyncio.to_thread(search_inbox)
                if result:
                    return result
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay_seconds)

            logger.warning(
                f"Account: {self.email} | Pattern not found after {max_attempts} attempts, searching in spam folder..."
            )
            spam_folders = ("SPAM", "Spam", "spam", "Junk", "junk", "Spamverdacht")

            def search_spam():
                with MailBoxClient(self.imap_server, proxy=proxy, timeout=30).login(
                        self.email, self.password
                ) as mailbox:
                    for spam_folder in spam_folders:
                        result = self._search_for_pattern_in_spam(
                            mailbox, spam_folder, pattern, is_regex
                        )
                        if result:
                            logger.success(
                                f"Account: {self.email} | Found pattern in spam"
                            )
                            return result
                return None

            result = await asyncio.to_thread(search_spam)
            if result:
                return result

            logger.error(f"Account: {self.email} | Pattern not found in any folder")
            return None

        except Exception as error:
            logger.error(
                f"Account: {self.email} | Failed to check email for pattern: {error}"
            )
            return None
