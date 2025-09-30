import math
import random
import time
from asyncio import sleep, gather, create_task, Semaphore
from typing import Optional, Literal

from loguru import logger

from config import RETRIES, PAUSE_BETWEEN_RETRIES, PAUSE_BETWEEN_MODULES
from src.modules.pi2.auth_client import AuthClient
from src.modules.pi2.file_utils import update_connected_info_file
from src.modules.pi2.types import UserResponse, UserDataResponse
from src.utils.common.wrappers.decorators import retry
from src.utils.proxy_manager import Proxy
from src.utils.request_client.curl_cffi_client import CurlCffiClient
from src.utils.user.social.discord.discord_client import DiscordClient
from src.utils.user.social.twitter.twitter_client import TwitterClient


class Pi2Client(CurlCffiClient):
    # noinspection PyMissingConstructor
    def __init__(
            self,
            email_login: str,
            email_password: str,
            refresh_token: Optional[str] = None,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            *,
            proxy: Proxy | None,
            twitter_token: str = None,
            discord_token: str = None
    ):
        self.email_login = email_login
        self.email_password = email_password
        self.email_refresh_token = refresh_token
        self.email_client_id = client_id
        self.email_client_secret = client_secret
        self.twitter_token = twitter_token
        self.discord_token = discord_token

        self._auth_client: Optional[AuthClient] = None
        self._twitter_client: Optional[TwitterClient] = None
        self._discord_client: Optional[DiscordClient] = None

        self.proxy = proxy
        if proxy:
            self.proxy.attach_client(self)
        self.reinitialize_proxy_clients()
        self.headers = None
        self._game_state = None
        self._stats: dict[str, Optional[float | int]] = {
            'started_at': None,
            'clicks_total': 0,
            'clicks_correct': 0,
        }

    def reinitialize_proxy_clients(self):
        CurlCffiClient.__init__(self, proxy=self.proxy)
        self._auth_client = AuthClient(
            email_login=self.email_login,
            email_password=self.email_password,
            refresh_token=self.email_refresh_token,
            client_id=self.email_client_id,
            proxy=self.proxy
        )
        if self.twitter_token:
            self._twitter_client = TwitterClient(auth_token=self.twitter_token, proxy=self.proxy)
        self._discord_client = DiscordClient(auth_token=self.discord_token, proxy=self.proxy)

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def authorize(self):
        authed = await self._auth_client.authorize()
        if authed:
            self.headers = self._auth_client.headers
            await self._auth_client.check_user_data()
            return True

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def get_all_uncompleted_tasks(self, task_type: Literal['social', 'other'] = None, return_ids: bool = False):
        task_type_map = {
            'social': 'Social Challenges',
            'other': 'Quiz Challenges'
        }

        response_json, status = await self.make_request(
            method="GET",
            url='https://pisquared-api.pulsar.money/api/v1/pulsar/challenges/pi-squared/tasks-status/1',
            headers=self.headers
        )
        if status == 200:
            if return_ids and task_type:
                return [
                    task['taskGuid'] for task in response_json['tasksStatus']
                    if task['type'] == task_type_map[task_type] and not task['taskName'] == 'create_media'
                       and task['isEnabled']
                ]
            else:
                return response_json['tasksStatus']

    async def get_auth_url(self, social: Literal['twitter', 'discord']):
        url = f'https://pisquared-api.pulsar.money/api/v1/pulsar/social-pay/register/{social}'
        all_uncompleted_tasks = await self.get_all_uncompleted_tasks(task_type='social', return_ids=True)
        task_id = all_uncompleted_tasks[0]

        json_data = {
            'type': 'register',
            'redirectUrl': f'https://portal.pi2.network/quests?taskId={task_id}',
        }
        response = await self.session.request(
            method="POST",
            url=url,
            json=json_data,
            headers=self.headers
        )
        return response.json()

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def prepare_account(self, user: UserResponse):
        if not user.twitter_metadata:
            logger.debug(f'[{self.email_login}] | Connecting twitter...')
            auth_url = await self.get_auth_url(social='twitter')
            connected = await self._twitter_client.connect_twitter(auth_url)
            if connected:
                logger.success(f'[{self.email_login}] | Successfully connected twitter!')
                await update_connected_info_file(
                    f'{self.email_login}:{self.email_password}',
                    self._twitter_client.auth_token
                )

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def confirm_quest(self, task_id: str, task_name: str = None, extra_args=None):
        json_data = {
            'taskGuid': task_id,
            'extraArguments': [],
        }
        if extra_args:
            json_data.update({'extraArguments': [extra_args]})

        response_json, status = await self.make_request(
            method="POST",
            url='https://pisquared-api.pulsar.money/api/v1/pulsar/challenges/do-task',
            headers=self.headers,
            json=json_data
        )
        if status == 201 and response_json['status']:
            return True
        logger.error(f'[{self.email_login}] | Failed to confirm {task_name} quest | {response_json}')

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def complete_quest(self, task_data: dict):
        task_id = task_data['taskGuid']
        if task_data['taskName'] in ['follow_twitter_account', 'retweet_post', 'pisquared_query', 'click_link']:
            confirmed = await self.confirm_quest(task_id=task_id, task_name=task_data['title'])
            if confirmed:
                logger.success(f'[{self.email_login}] | Successfully confirmed {task_data['title']} quest!')
                return True
        elif task_data['taskName'] == 'twitter_username':
            current_username = await self._twitter_client.get_account_username()
            if 'π²' in current_username:
                return await self.confirm_quest(task_id=task_id)

            name = current_username + ' π²'
            changed = await self._twitter_client.update_account_username(name)
            if changed:
                logger.success(f'[{self.email_login}] | Successfully added π² to twitter name!')
                confirmed = await self.confirm_quest(task_id=task_id)
                if confirmed:
                    logger.success(f'[{self.email_login}] | Successfully confirmed {task_data['title']} quest!')
                    return True

        elif task_data['taskName'] == 'quiz':
            if task_data['description'] == "Is FastSet a blockchain?":
                extra_args = "No"
            elif task_data['description'] == "Which one of the following best describes the TPS capacity of FastSet?":
                extra_args = "Above 100,000"
            elif task_data[
                'description'] == "As required by the FastSet protocol, a validator will send which one of the following messages to another validator?":
                extra_args = "None, because FastSet validators don’t need to talk to each other."
            else:
                logger.error(f'[{self.email_login}] | Unknown quiz.')
                return False

            confirmed = await self.confirm_quest(task_id=task_id, extra_args=extra_args)
            if confirmed:
                logger.success(f'[{self.email_login}] | Successfully confirmed {task_data['title']} quest!')
                return True

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def start_game(self):
        response_json, status = await self.make_request(
            method="POST",
            url='https://pisquared-api.pulsar.money/api/v1/game-sessions/start',
            headers=self.headers
        )
        if status == 201:
            game_id = response_json['id']
            logger.success(f'[{self.email_login}] | Successfully started game!')
            self._game_state = {
                'started_at': time.time(),
                'current_color': random.choice(['orange', 'green', 'red', 'blue', 'yellow']),
                'next_change_at': time.time() + random.uniform(8.0, 9.0),
                'omega': 2 * math.pi / 2.5,
                'cx': 470, 'cy': 380, 'r': 90
            }
            self._stats = {
                'started_at': time.time(),
                'clicks_total': 0,
                'clicks_correct': 0,
            }
            return game_id

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def end_game(self, score: int, game_id: str):
        if not self._stats['started_at']:
            self._stats['started_at'] = time.time() - 1.0

        duration = max(0.001, time.time() - self._stats['started_at'])
        correct = self._stats['clicks_correct']
        tps = correct / duration
        pi_stage = self._choose_pi_stage(tps=tps)

        json_data = {
            'score': score,
            'tps': int(round(tps)),
            'duration': int(duration),
            'level': 9,
            'piStageReached': pi_stage
        }
        response_json, status = await self.make_request(
            method="PUT",
            url=f'https://pisquared-api.pulsar.money/api/v1/game-sessions/{game_id}/end',
            headers=self.headers,
            json=json_data
        )
        # print(response_json)
        if status == 200:
            logger.success(f'[{self.email_login}] | Successfully finished game with score {score}. π² = {pi_stage}')
            return True

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def perform_click(self, game_id: str):
        if not self._game_state:
            self._game_state = {
                'started_at': time.time(),
                'current_color': random.choice(['orange', 'green', 'red', 'blue', 'yellow']),
                'next_change_at': time.time() + random.uniform(8.0, 9.0),
                'omega': 2 * math.pi / 2.5,
                'cx': 470, 'cy': 380, 'r': 90
            }

        now = time.time()
        gs = self._game_state

        if now >= gs['next_change_at']:
            new_color = gs['current_color']
            colors = ['orange', 'green', 'red', 'blue', 'yellow']
            while new_color == gs['current_color']:
                new_color = random.choice(colors)
            gs['current_color'] = new_color
            gs['next_change_at'] = now + random.uniform(2.0, 4.0)

        t = now - gs['started_at']
        theta = (t * gs['omega']) % (2 * math.pi)

        x = int(round(gs['cx'] + gs['r'] * math.sin(theta)))
        y = int(round(gs['cy'] - gs['r'] * math.cos(theta)))
        json_data = {
            'color': gs['current_color'],
            'isCorrect': True,
            'energyGenerated': 1,
            'x': x,
            'y': y,
            'timestamp': int(now * 1000),
        }

        response_json, status = await self.make_request(
            method="POST",
            url=f'https://pisquared-api.pulsar.money/api/v1/game-sessions/{game_id}/click',
            json=json_data,
            headers=self.headers
        )
        self._stats['clicks_total'] += 1
        if status == 201 and response_json.get('success'):
            self._stats['clicks_correct'] += 1
            # logger.success(f'[{self.email_login}] | Successfully clicked!')
            return True

        logger.error(f'[{self.email_login}] | Click failed: status={status}.')

    async def play_game(self):
        game_id = await self.start_game()
        if not game_id:
            return None

        await self.run_click_loop(
            game_id,
            duration_s=random.uniform(7.0, 12.0),
            target_tps=random.uniform(7.0, 15.0),
            max_inflight=8
        )
        successes = self._stats['clicks_correct']
        return await self.end_game(successes, game_id)

    @staticmethod
    def _choose_pi_stage(tps: float) -> str:
        stages = ['9', '9.8', '9.86', '9.869', '9.8696', '9.86960', '9.869604', '9.8696044']
        if tps < 4:   return stages[0]
        if tps < 6:   return stages[1]
        if tps < 8:   return stages[2]
        if tps < 10:   return stages[3]
        if tps < 13:  return stages[4]
        if tps < 14:  return stages[5]
        if tps < 16:  return stages[6]
        return stages[7]

    async def run_click_loop(
            self,
            game_id: str,
            duration_s: float = 18.0,
            target_tps: float = 12.0,
            max_inflight: int = 8,
            jitter: float = 0.12
    ):
        start = time.time()
        self._stats['started_at'] = start

        period = 1.0 / max(0.1, target_tps)
        sem = Semaphore(max_inflight)
        tasks = []

        async def _scheduled_click(eta: float):
            delay = eta - time.time()
            if delay > 0:
                await sleep(delay)
            try:
                await self.perform_click(game_id)
            finally:
                sem.release()

        next_eta = start
        while True:
            now = time.time()
            if now - start >= duration_s:
                break

            interval = max(0.02, random.gauss(period, period * jitter))
            next_eta += interval

            await sem.acquire()
            tasks.append(create_task(_scheduled_click(next_eta)))

        if tasks:
            await gather(*tasks)

    async def process_quests(self):
        authorized = await self.authorize()
        if not authorized:
            return None

        user = await self._auth_client.get_user_data()
        if not user:
            return None

        await self.prepare_account(user)

        uncompleted_quests = await self.get_all_uncompleted_tasks()

        successes = 0
        for task_data in uncompleted_quests:
            if not task_data['isEnabled']:
                continue
            if task_data['status'] == 'SUCCESSFUL':
                logger.success(f'[{self.email_login}] | Task {task_data['title']} has been already completed!')
                successes += 1
                continue
            if task_data['taskName'] == 'create_media':
                logger.warning(f'[{self.email_login}] | Task {task_data['title']} is not supported yet.')
                continue

            completed = await self.complete_quest(task_data)
            if completed == 'DISABLED':
                continue

            if completed:
                successes += 1

            random_sleep = random.randint(PAUSE_BETWEEN_MODULES[0], PAUSE_BETWEEN_MODULES[1]) \
                if isinstance(PAUSE_BETWEEN_MODULES, list) else PAUSE_BETWEEN_MODULES
            logger.info(f'Сплю {random_sleep} секунд перед следующим квестом...')
            await sleep(random_sleep)

        if successes > 0:
            return True

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def get_user(self) -> Optional[UserDataResponse]:
        headers = self.headers.copy()
        headers.update({'x-device-signature': self._auth_client.generate_fake_device_signature()})

        response_json, status = await self.make_request(
            method="GET",
            url='https://pisquared-api.pulsar.money/api/v1/pulsar/challenges/pi-squared/me/1',
            headers=headers
        )
        if status == 200:
            return UserDataResponse.from_dict(response_json)
        logger.error(f'[{self.email_login}] | Failed to get user data | Status: {status}')
