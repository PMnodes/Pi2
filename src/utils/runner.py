from asyncio import sleep
from typing import Optional
import random

from loguru import logger

from config import GameSettings, PAUSE_BETWEEN_MODULES
from src.models.route import Route
from src.modules.pi2.pi2_client import Pi2Client
from src.utils.proxy_manager import Proxy


async def process_quests(route: Route) -> Optional[bool]:
    email_data = route.wallet.email.split(":")
    if len(email_data) == 2:
        email_login, email_password, refresh_token, client_id = email_data[0], email_data[1], None, None
    elif len(email_data) == 4:
        email_login, email_password, refresh_token, client_id = email_data[0], email_data[1], email_data[2], email_data[3]
    else:
        raise Exception('Invalid email format.')

    pi2_client = Pi2Client(
        email_login=email_login,
        email_password=email_password,
        refresh_token=refresh_token,
        client_id=client_id,
        proxy=route.wallet.proxy,
        twitter_token=route.wallet.twitter_token,
        discord_token=route.wallet.discord_token
    )

    return await pi2_client.process_quests()


async def process_play_game(route: Route) -> Optional[bool]:
    email_data = route.wallet.email.split(":")
    if len(email_data) == 2:
        email_login, email_password, refresh_token, client_id = email_data[0], email_data[1], None, None
    elif len(email_data) == 4:
        email_login, email_password, refresh_token, client_id = email_data[0], email_data[1], email_data[2], email_data[
            3]
    else:
        raise Exception('Invalid email format.')

    pi2_client = Pi2Client(
        email_login=email_login,
        email_password=email_password,
        refresh_token=refresh_token,
        client_id=client_id,
        proxy=route.wallet.proxy,
        twitter_token=route.wallet.twitter_token,
        discord_token=route.wallet.discord_token
    )
    authorized = await pi2_client.authorize()
    if not authorized:
        return None

    num_plays = random.randint(GameSettings.num_plays[0], GameSettings.num_plays[1])
    successes = 0
    for _ in range(num_plays):
        played = await pi2_client.play_game()
        if played:
            successes += 1

        random_sleep = random.randint(PAUSE_BETWEEN_MODULES[0], PAUSE_BETWEEN_MODULES[1]) if isinstance(
            PAUSE_BETWEEN_MODULES, list) else PAUSE_BETWEEN_MODULES

        logger.info(f'Sleeping {random_sleep} seconds before next play...')
        await sleep(random_sleep)

    if successes > 0:
        return True


async def process_stats_checker(email: str, proxy: Proxy | None):
    email_data = email.split(":")
    if len(email_data) == 2:
        email_login, email_password, refresh_token, client_id = email_data[0], email_data[1], None, None
    elif len(email_data) == 4:
        email_login, email_password, refresh_token, client_id = email_data[0], email_data[1], email_data[2], email_data[
            3]
    else:
        raise Exception('Invalid email format.')

    pi2_client = Pi2Client(
        email_login=email_login,
        email_password=email_password,
        refresh_token=refresh_token,
        client_id=client_id,
        proxy=proxy,
    )
    authorized = await pi2_client.authorize()
    if not authorized:
        return (
            "Ошибка подключения к Pi2",
            False,
            False,
        )

    user_data = await pi2_client.get_user()
    if not user_data:
        return (
            "Ошибка подключения к Pi2",
            False,
            False,
        )

    points = str(int(user_data.totalPoints))
    rank = user_data.rank

    return (
        email_login,
        points,
        rank
    )
