import binascii
import random
from typing import Optional

from loguru import logger

from src.utils.proxy_manager import Proxy
from src.utils.request_client.curl_cffi_client import CurlCffiClient
import twitter


class TwitterClient(CurlCffiClient):
    def __init__(
            self,
            auth_token: str,
            proxy: Proxy | None
    ):
        super().__init__(proxy=proxy)

        self.auth_token = auth_token
        csrf_token = self.get_csrf_token()
        self.cookies = {
            "ct0": csrf_token,
            "auth_token": auth_token
        }

        self.twitter_headers = {
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-client-language": "en",
            "referrer-policy": "strict-origin-when-cross-origin",
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "accept": "*/*",
            "accept-language": "ru-RU,ru;q=0.8",
            "x-csrf-token": csrf_token,
            "Cookie": f"lang=en; auth_token={self.auth_token}; ct0={csrf_token};",
            "content-type": "application/x-www-form-urlencoded",
        }
        self.twitter_account = twitter.Account(auth_token=auth_token)
        self.twitter_args = {"account": self.twitter_account, "proxy": proxy.proxy_url if proxy else None}

    def get_csrf_token(self):
        data = random.getrandbits(16 * 8).to_bytes(16, "big")
        csrf_token = binascii.hexlify(data).decode()
        return csrf_token

    async def get_oauth2_code(self, auth_url: str) -> str:
        updated_url = auth_url.replace(
            "https://x.com/i/oauth2/authorize",
            "https://x.com/i/api/2/oauth2/authorize",
        )
        response_json, status = await self.make_request(
            method="GET",
            url=updated_url,
            headers=self.twitter_headers,
        )
        return response_json['auth_code']

    async def get_redirect_url(self, oauth2_code: str) -> str:
        json_data = {
            'approval': 'true',
            'code': oauth2_code
        }
        response = await self.session.post(
            url='https://twitter.com/i/api/2/oauth2/authorize',
            headers=self.twitter_headers,
            data=json_data,
            verify=False
        )
        return response.json()['redirect_uri']

    async def oauth2(self, auth_url: str) -> tuple[str, str]:
        oauth2_code = await self.get_oauth2_code(auth_url)
        redirect_url = await self.get_redirect_url(oauth2_code)
        return redirect_url, oauth2_code

    async def connect_twitter(self, auth_url: str) -> Optional[bool]:
        tried_tokens = set()

        while True:
            try:
                redirect_url, code = await self.oauth2(auth_url)
                await self.session.get(url=redirect_url, verify=False)
                return True
            except Exception as ex:
                logger.error(f'Error during Twitter connection: {ex}')

            logger.error(f'Something went wrong while connecting twitter')

            with open('data/reserve/twitter_tokens.txt', 'r') as file:
                twitter_tokens = [line.strip() for line in file if line.strip() not in tried_tokens]

            if twitter_tokens:
                new_token = random.choice(twitter_tokens)
                tried_tokens.add(new_token)

                self.auth_token = new_token
                csrf_token = self.get_csrf_token()
                self.cookies = {
                    "ct0": csrf_token,
                    "auth_token": self.auth_token
                }
                self.twitter_headers = {
                    "x-twitter-active-user": "yes",
                    "x-twitter-auth-type": "OAuth2Session",
                    "x-twitter-client-language": "en",
                    "referrer-policy": "strict-origin-when-cross-origin",
                    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                    "accept": "*/*",
                    "accept-language": "ru-RU,ru;q=0.8",
                    "x-csrf-token": csrf_token,
                    "Cookie": f"lang=en; auth_token={self.auth_token}; ct0={csrf_token};",
                    "content-type": "application/x-www-form-urlencoded",
                }
                self.twitter_account = twitter.Account(auth_token=new_token)

                twitter_tokens.remove(new_token)
                with open('data/reserve/twitter_tokens.txt', 'w') as file:
                    for token in twitter_tokens:
                        file.write(f'{token}\n')

                logger.debug(f'Retrying with new Twitter token...')
                continue
            else:
                logger.warning(f'There are no reserve Twitter tokens left.')
                break

        return None

    async def follow(self, user_id: int):
        async with twitter.Client(**self.twitter_args) as twitter_client:
            return await twitter_client.follow(user_id=user_id)

    async def get_account_username(self):
        async with twitter.Client(**self.twitter_args) as twitter_client:
            await twitter_client.update_account_info()
            return self.twitter_account.username

    async def tweet(self, text: str):
        async with twitter.Client(**self.twitter_args) as twitter_client:
            return await twitter_client.tweet(text)

    async def update_account_username(self, name: str):
        async with twitter.Client(**self.twitter_args) as twitter_client:
            return await twitter_client.update_profile(name=name)

    async def like(self, tweet_id: int):
        async with twitter.Client(**self.twitter_args) as twitter_client:
            return await twitter_client.like(tweet_id)

    async def retweet(self, tweet_id: int):
        async with twitter.Client(**self.twitter_args) as twitter_client:
            return await twitter_client.repost(tweet_id)

    async def post_for_binding(self, galxe_id: str) -> tuple[int, str]:
        tweet_text = f'Verifying my Twitter account for my #GalxeID gid:{galxe_id} @Galxe \n\n galxe.com/galxeid'
        tweet = await self.tweet(tweet_text)
        username = tweet.user.username
        return tweet.id, username
