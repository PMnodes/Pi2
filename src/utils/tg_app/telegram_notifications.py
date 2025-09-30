from contextlib import suppress

from src.database.base_models.pydantic_manager import DataBaseManagerConfig
from src.database.utils.db_manager import DataBaseUtils

from src.utils.request_client.curl_cffi_client import CurlCffiClient


class TGApp(CurlCffiClient):
    def __init__(
            self,
            token: str,
            tg_id: int,
            email: str,
            processed_index: int,
    ):
        self.processed_index = processed_index
        self.email = email

        self.token = token
        self.tg_id = tg_id
        super().__init__(proxy=None)

        self.__db_utils = DataBaseUtils(
            manager_config=DataBaseManagerConfig(
                action='wallets_tasks'
            )
        )

    async def _get_text(self) -> str:
        completed_tasks, uncompleted_tasks = await self.__db_utils.get_tasks_info(self.email)

        completed_tasks_list = "\n".join(f"- {task.task_name}" for task in completed_tasks) or "No tasks completed."
        uncompleted_tasks_list = "\n".join(
            f"- {task.task_name}" for task in uncompleted_tasks) or "All tasks completed."

        completed_wallets_count = await self.__db_utils.get_completed_wallets_count()
        total_wallets_count = await self.__db_utils.get_total_wallets_count()
        completed_tasks_list = escape_markdown_v2(completed_tasks_list)
        uncompleted_tasks_list = escape_markdown_v2(uncompleted_tasks_list)

        text = (
            f"💼 **Wallet completed its work:**\n"
            f"`{self.email.split(":")[0]}`\n\n"
            f"📋 **Task Summary:**\n"
            f"✅ **Completed Tasks:** {len(completed_tasks)}\n"
            f"❌ **Uncompleted Tasks:** {len(uncompleted_tasks)}\n\n"
            f"🔍 **Details:**\n\n"
            f"**Completed Tasks:**\n{completed_tasks_list}\n\n"
            f"**Uncompleted Tasks:**\n{uncompleted_tasks_list}\n\n"
            f"📊 **Overall Progress:**\n"
            f"**Completed Wallets:** {completed_wallets_count}/{total_wallets_count}\n"
            f"**Processed Wallets:** {self.processed_index}/{total_wallets_count}"
        )

        return text

    async def send_message(self) -> None:
        text = await self._get_text()

        await self.make_request(
            method='GET',
            url=f'https://api.telegram.org/bot{self.token}/sendMessage',
            params={
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": 1,
                "chat_id": self.tg_id,
                "text": text,
            }
        )
        with suppress(Exception):
            await self.session.close()


def escape_markdown_v2(text: str) -> str:
    specials = r"_-*[]()~`>#+=|{}.!"
    for char in specials:
        text = text.replace(char, f"\\{char}")
    return text
