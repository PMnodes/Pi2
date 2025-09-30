from typing import List, Optional

from loguru import logger
from sqlalchemy import select

from src.database.models import Wallet, async_session


async def generate_database(
    private_keys: List[str],
    proxies: List[Optional[str]]
) -> None:
    """
    Генерирует базу данных с кошельками

    Args:
        private_keys: Список приватных ключей
        proxies: Список прокси
    """
    logger.info(f"Начинается генерация базы данных с {len(private_keys)} кошельками")

    async with async_session() as session:
        for i, private_key in enumerate(private_keys):
            proxy = proxies[i] if i < len(proxies) else None

            # Проверяем, существует ли уже кошелек
            result = await session.execute(
                select(Wallet).where(Wallet.private_key == private_key)
            )
            existing_wallet = result.scalar_one_or_none()

            if existing_wallet:
                logger.warning(f"Кошелек {private_key[:10]}... уже существует")
                continue

            wallet = Wallet(
                private_key=private_key,
                proxy=proxy,
            )
            session.add(wallet)

        await session.commit()
        logger.success(f"База данных с {len(private_keys)} кошельками успешно сгенерирована")