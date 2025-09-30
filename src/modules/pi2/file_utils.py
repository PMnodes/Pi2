import os
import asyncio


async def update_connected_info_file(
        email: str,
        auth_token: str,
        file_path: str = 'connected_info.txt'
) -> None:
    async with asyncio.Lock():
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                lines = f.readlines()
        else:
            lines = []

        updated_lines = [line for line in lines if not line.startswith(f'{email}:')]
        updated_lines.append(f'{email}:{auth_token}\n')

        with open(file_path, 'w') as f:
            f.writelines(updated_lines)
