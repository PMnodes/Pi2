import random
from typing import Optional

from loguru import logger

from src.utils.proxy_manager import Proxy
from src.utils.request_client.curl_cffi_client import CurlCffiClient
from src.utils.user.social.discord.utils import create_x_context_properties, create_x_super_properties


class DiscordClient(CurlCffiClient):
    def __init__(
            self,
            auth_token: str,
            proxy: Proxy | None
    ):
        self.auth_token = auth_token
        super().__init__(proxy=proxy)

        self.discord_headers = {
            "accept": "*/*",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
            "authorization": auth_token,
            "content-type": "application/json",
            "origin": "https://discord.com",
            "priority": "u=1, i",
            "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="131", "Chromium";v="131"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "en-US",
            "x-discord-timezone": "Etc/GMT-2",
        }

    async def get_location_url(self, auth_url: str) -> Optional[str]:
        json_data = {
            'permissions': '0',
            'authorize': True,
            'integration_type': 0,
        }
        response_json, status = await self.make_request(
            method="POST",
            url=auth_url,
            headers=self.discord_headers,
            json=json_data
        )
        if status == 200:
            return response_json['location']
        logger.error(f'Bad discord token: {self.auth_token}. | Status: {status}')

    async def connect_discord(self, auth_url: str) -> Optional[str]:
        tried_tokens = set()

        while True:
            try:
                location_url = await self.get_location_url(auth_url)
                if not location_url:
                    raise
                return location_url
            except:
                logger.error(f'Error during Discord connection')

            logger.error(f'Something went wrong while connecting discord')

            with open('data/reserve/discord_tokens.txt', 'r') as file:
                discord_tokens = [line.strip() for line in file if line.strip() not in tried_tokens]

            if discord_tokens:
                new_token = random.choice(discord_tokens)
                tried_tokens.add(new_token)

                self.auth_token = new_token

                self.discord_headers = {
                    "accept": "*/*",
                    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
                    "authorization": new_token,
                    "content-type": "application/json",
                    "origin": "https://discord.com",
                    "priority": "u=1, i",
                    "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="131", "Chromium";v="131"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "x-debug-options": "bugReporterEnabled",
                    "x-discord-locale": "en-US",
                    "x-discord-timezone": "Etc/GMT-2",
                }

                discord_tokens.remove(new_token)
                with open('data/reserve/discord_tokens.txt', 'w') as file:
                    for token in discord_tokens:
                        file.write(f'{token}\n')

                logger.debug(f'Retrying with new Discord token...')
                continue
            else:
                logger.warning(f'There are no reserve Discord tokens left.')
                break

    async def get_guild_ids(self, invite_code: str):
        params = {
            'with_counts': 'true',
            'with_expiration': 'true',
            'with_permissions': 'false',
        }
        response_json, status = await self.make_request(
            method="GET",
            url=f'https://discord.com/api/v9/invites/{invite_code}',
            params=params,
            headers=self.discord_headers
        )
        location_guild_id = response_json['guild_id']
        location_channel_id = response_json['channel']['id']
        return location_guild_id, location_channel_id

    async def init_cookies(self):
        response = await self.session.get(
            url="https://discord.com/login",
            headers={
                'authority': 'discord.com',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-US,en;q=0.9',
                'sec-ch-ua': '"Chromium";v="131", "Not A(Brand";v="24", "Google Chrome";v="131"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
            }
        )
        cookies = {}
        cookies_list = response.headers.get_list("set-cookie")
        for cookie in cookies_list:
            key, value = cookie.split(';')[0].strip().split("=")
            cookies.update({key: value})

        return cookies

    async def join_server(self, invite_code: str):
        cookies = await self.init_cookies()
        guild_id, channel_id = await self.get_guild_ids(invite_code)

        self.discord_headers.update({"referer": f"https://discord.com/invite/{invite_code}"})
        self.discord_headers.update({"x-context-properties": create_x_context_properties(guild_id, channel_id)})
        self.discord_headers.update({"x-super-properties": create_x_super_properties(), })

        json_data = {
            "session_id": None,
        }
        response = await self.session.post(
            url=f"https://discord.com/api/v9/invites/{invite_code}",
            headers=self.discord_headers,
            json=json_data,
            cookies=cookies,
        )
        if (
                "You need to update your app to join this server." in response.text
                or "captcha_rqdata" in response.text
        ):
            logger.error(f"Captcha detected. Can't solve it.")
            return None

        elif response.status_code == 200 and response.json()["type"] == 0:
            return True
