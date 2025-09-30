import random
from typing import Any

from aiohttp import ClientSession
from asyncio import sleep
from loguru import logger

from src.utils.data.helper import proxies


class Proxy:
    def __init__(self, proxy_url: str, change_link: str | None = None):
        self.change_link = change_link
        self.proxy_url = proxy_url
        self._client = None

    def attach_client(self, client: Any):
        self._client = client

    def _get_random_proxy(self) -> str:
        proxy_str = random.choice(proxies)
        return f"http://{proxy_str}"

    async def change(self):
        self.proxy_url = self._get_random_proxy()
        if self._client:
            self._client.reinitialize_proxy_clients()

    async def _change_ip(self):
        while True:
            try:
                async with ClientSession() as session:
                    response = await session.get(self.change_link)
                    if response.status == 200:
                        logger.debug("Successfully changed IP via change_link")
                        return
                    logger.error(f'Failed to change IP, status={response.status}')
            except Exception as ex:
                logger.error(f"Error during IP change: {ex}")
            await sleep(3)
