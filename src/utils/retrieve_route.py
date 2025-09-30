from typing import List, Optional

from loguru import logger

from src.database.base_models.pydantic_manager import DataBaseManagerConfig
from src.database.utils.db_manager import DataBaseUtils
from src.models.route import Route, Wallet


async def get_routes() -> Optional[List[Route]]:
    db_utils = DataBaseUtils(
        manager_config=DataBaseManagerConfig(
            action='working_wallets'
        )
    )
    result = await db_utils.get_uncompleted_wallets()
    if not result:
        logger.success(f'Все кошельки с данной базы данных уже отработали')
        return None

    routes = []

    for wallet in result:
        email_tasks = await db_utils.get_wallet_pending_tasks(wallet.email)
        tasks = []
        for task in email_tasks:
            tasks.append(task.task_name)

        routes.append(
            Route(
                tasks=tasks,
                wallet=Wallet(
                    email=wallet.email,
                    twitter_token=wallet.twitter_token,
                    discord_token=wallet.discord_token,
                    proxy=wallet.proxy,
                )
            )
        )
    return routes
