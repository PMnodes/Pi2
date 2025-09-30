import os, platform
from asyncio import run, set_event_loop_policy, gather, create_task, sleep, Lock
from typing import Awaitable, Callable
import random
import asyncio
import logging
import sys

from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn, TaskID

from src.utils.runner import process_stats_checker
from src.utils.version import print_logo

plat = platform.system().lower()
pyver = "py31210"
root = os.path.dirname(__file__)
rt_base = os.path.join(root, 'runtimes', f"{plat}_{pyver}")
sys.path.insert(0, rt_base)

from questionary import select, Choice
from loguru import logger
from rich.console import Console

from src.database.base_models.pydantic_manager import DataBaseManagerConfig
from src.database.utils.db_manager import DataBaseUtils
from config import *
from src.utils.data.helper import proxies, twitter_tokens, discord_tokens, emails
from src.database.generate_database import generate_database
from src.database.models import init_models, engine
from src.utils.data.mappings import module_handlers
from src.utils.manage_tasks import manage_tasks
from src.utils.proxy_manager import Proxy
from src.utils.retrieve_route import get_routes
from src.models.route import Route
from src.utils.tg_app.telegram_notifications import TGApp

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.CRITICAL)

if sys.platform == 'win32':
    set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

processed_wallets_counter = 0
processed_wallets_lock = Lock()


async def initialize_processed_wallets_counter():
    global processed_wallets_counter
    db_utils = DataBaseUtils(
        manager_config=DataBaseManagerConfig(action='working_wallets')
    )
    processed_wallets_counter = await db_utils.get_completed_wallets_count()


def get_module():
    result = select(
        message="Choose module",
        choices=[
            Choice(title="1) Generate new database", value=1),
            Choice(title="2) Work with existing database", value=2),
            Choice(title="3) Check stats", value=3),
        ],
        qmark="⚙️ ",
        pointer="🍒 "
    ).ask()
    return result


async def process_task(routes: list[Route]) -> None:
    if not routes:
        logger.success(f'All tasks are completed')
        return

    semaphore = asyncio.Semaphore(MAX_PARALLEL_ACCOUNTS)

    async def process_route_with_semaphore(route: Route) -> None:
        async with semaphore:
            await process_route(route)

    wallet_tasks = []
    for i, route in enumerate(routes):
        wallet_tasks.append(create_task(process_route_with_semaphore(route)))

        if i < len(routes) - 1:
            time_to_pause = random.randint(PAUSE_BETWEEN_WALLETS[0], PAUSE_BETWEEN_WALLETS[1]) \
                if isinstance(PAUSE_BETWEEN_WALLETS, list) else PAUSE_BETWEEN_WALLETS
            logger.info(f'Сплю {time_to_pause} секунд перед следующим кошельком...')
            await sleep(time_to_pause)

    await gather(*wallet_tasks)


async def process_route(route: Route) -> None:
    if route.wallet.proxy:
        if route.wallet.proxy.proxy_url and MOBILE_PROXY and ROTATE_IP:
            await route.wallet.proxy.change_ip()

    email = route.wallet.email

    for task in route.tasks:
        await process_module(task, route)

        random_sleep = random.randint(PAUSE_BETWEEN_MODULES[0], PAUSE_BETWEEN_MODULES[1]) \
            if isinstance(PAUSE_BETWEEN_MODULES, list) else PAUSE_BETWEEN_MODULES
        logger.info(f'Сплю {random_sleep} секунд перед следующим модулем...')
        await sleep(random_sleep)

    if TG_BOT_TOKEN and TG_USER_ID:
        global processed_wallets_counter
        global processed_wallets_lock

        async with processed_wallets_lock:
            processed_wallets_counter += 1
            current_index = processed_wallets_counter

        tg_app = TGApp(
            token=TG_BOT_TOKEN,
            tg_id=TG_USER_ID,
            email=email,
            processed_index=current_index,
        )
        await tg_app.send_message()


async def process_module(task: str, route: Route) -> None:
    completed = await module_handlers[task](route)

    if completed:
        await manage_tasks(route.wallet.email, task)


async def main(module: Callable) -> None:
    await init_models(engine)
    if module == 1:
        if SHUFFLE_WALLETS:
            random.shuffle(emails)
        logger.debug("Generating new database")
        await generate_database(engine, emails, proxies, twitter_tokens, discord_tokens)
    elif module == 2:
        logger.debug("Working with the database")
        await initialize_processed_wallets_counter()
        routes = await get_routes()
        await process_task(routes)
    elif module == 3:
        console = Console()
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        )

        logger.debug("Checking stats...")
        proxy_index = 0

        async def run_with_progress(email: str, proxy: str, task_id: TaskID):
            proxy_instance = None
            if proxy:
                proxy_instance = Proxy(proxy_url='http://' + proxy, change_link=None)
            result = await process_stats_checker(email, proxy_instance)
            progress.update(task_id, advance=1)
            return result

        with progress:
            task_id = progress.add_task("Проверка аккаунтов...", total=len(emails))
            tasks = []

            for email in emails:
                proxy = proxies[proxy_index]
                proxy_index = (proxy_index + 1) % len(proxies)

                task = create_task(run_with_progress(email, proxy, task_id))
                tasks.append(task)

                time_to_pause = random.randint(PAUSE_BETWEEN_WALLETS[0], PAUSE_BETWEEN_WALLETS[1]) \
                    if isinstance(PAUSE_BETWEEN_WALLETS, list) else PAUSE_BETWEEN_WALLETS
                await sleep(time_to_pause)

            results = await gather(*tasks)

        table = Table(title="Статистика по аккаунтам", show_header=True, header_style="bold magenta")
        table.add_column("Account", style="cyan", justify='center')
        table.add_column("Points", style="green", justify='center')
        table.add_column("Rank", style="green", justify='center')

        total_points = 0
        valid_wallets = 0

        for result in results:
            if isinstance(result, tuple) and len(result) == 3:
                email, points, rank = result

                table.add_row(
                    email,
                    str(points),
                    str(rank),
                )
                total_points += int(points)
                valid_wallets += 1
            else:
                table.add_row("[red]Ошибка[/red]", "[red]Нет данных[/red]")

        table.add_row("—" * 20, "—" * 10, "-" * 10)
        table.add_row("[bold]ИТОГО:[/bold]", f"[bold green]{total_points}[/bold green]")

        console.print(table)
        console.print(f"[bold yellow]Обработано аккаунтов:[/bold yellow] {valid_wallets}/{len(results)}")

    else:
        print("Wrong choice")
        return


def start_event_loop(awaitable: Awaitable[None]) -> None:
    run(awaitable)


if __name__ == '__main__':
    console = Console()
    print_logo(console)
    module = get_module()
    start_event_loop(main(module))
