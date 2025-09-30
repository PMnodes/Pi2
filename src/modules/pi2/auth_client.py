import hashlib
import uuid
from asyncio import sleep
import platform
from typing import Optional

from loguru import logger

from config import RETRIES, PAUSE_BETWEEN_RETRIES
from src.modules.pi2.types import UserResponse
from src.utils.common.wrappers.decorators import retry
from src.utils.imap_client.imap import AsyncEmailChecker
from src.utils.proxy_manager import Proxy
from src.utils.request_client.curl_cffi_client import CurlCffiClient


class AuthClient(CurlCffiClient):
    def __init__(
        self,
        email_login: str,
        email_password: str,
        refresh_token: Optional[str] = None,
        client_id: Optional[str] = None,
        *,
        proxy: Proxy | None
    ):
        super().__init__(proxy=proxy)

        self.email_login = email_login
        self.email_password = email_password

        domain = email_login.lower().split("@")[-1]
        has_oauth = bool(refresh_token and client_id)

        provider: Optional[str] = None
        if has_oauth:
            if domain in ("gmail.com", "googlemail.com"):
                provider = "google"
            elif domain in ("outlook.com", "hotmail.com", "live.com", "msn.com", "office365.com"):
                provider = "microsoft"

        self._email_client = AsyncEmailChecker(
            email=email_login,
            password=email_password,
            oauth_provider=provider,
            client_id=client_id if provider else None,
            refresh_token=refresh_token if provider else None,
        )

        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/json',
            'origin': 'https://portal.pi2.network',
            'priority': 'u=1, i',
            'referer': 'https://portal.pi2.network/',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        }

    async def _request_otp(self):
        json_data = {
            'email': self.email_login
        }
        response_json, status = await self.make_request(
            method="POST",
            url='https://pisquared-api.pulsar.money/api/v1/auth/request-otp',
            headers=self.headers,
            json=json_data
        )
        if status == 201 and response_json['success']:
            logger.success(f'[{self.email_login}] | Code sent!')
            return True
        logger.error(f'[{self.email_login}] | Failed to send code | {response_json}')

    async def _verify_otp(self, code: str):
        json_data = {
            'email': self.email_login,
            'code': code,
        }
        response = await self.session.request(
            method="POST",
            url='https://pisquared-api.pulsar.money/api/v1/auth/verify-otp',
            headers=self.headers,
            json=json_data
        )
        if response.status_code == 201:
            jwt_token = response.headers['x-access-token']
            logger.success(f'[{self.email_login}] | Successfully authorized into portal.pi2.network!')
            self.headers.update({'authorization': f'Bearer {jwt_token}'})
            return True

    async def authorize(self):
        code_sent = await self._request_otp()
        if not code_sent:
            return None
        await sleep(5)
        code = await self._email_client.check_email_for_verification_link(pattern=r"(?<!\d)\d{6}(?!\d)")
        authed = await self._verify_otp(code)
        if authed:
            return True

    def generate_fake_device_signature(self) -> str:
        ua = self.headers['user-agent']
        os_info = platform.platform()
        mac = hex(uuid.getnode())

        raw = f"{ua}|{os_info}|{mac}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def check_user_data(self):
        headers = self.headers.copy()
        headers.update({'x-device-signature': self.generate_fake_device_signature()})
        await self.make_request(
            method="GET",
            url='https://pisquared-api.pulsar.money/api/v1/pulsar/challenges/pi-squared/me/1',
            headers=headers
        )

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def get_user_data(self) -> Optional[UserResponse]:
        response_json, status = await self.make_request(
            method="GET",
            url='https://pisquared-api.pulsar.money/api/v1/pulsar/social-pay/me',
            headers=self.headers
        )
        if status in [200, 304]:
            return UserResponse.from_dict(response_json)
        logger.error(f'[{self.email_login}] | Failed to get user data.')
