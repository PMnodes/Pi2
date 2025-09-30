from colorama import Fore

with open('config.py', 'r', encoding='utf-8-sig') as file:
    module_config = file.read()

exec(module_config)

with open('data/emails.txt', 'r', encoding='utf-8-sig') as file:
    emails = [line.strip() for line in file]

with open('data/proxies.txt', 'r', encoding='utf-8-sig') as file:
    proxies = [line.strip() for line in file]
    if not proxies:
        proxies = [None for _ in range(len(emails))]

with open('data/twitter_tokens.txt', 'r', encoding='utf-8-sig') as file:
    twitter_tokens = [line.strip() for line in file]

with open('data/discord_tokens.txt', 'r', encoding='utf-8-sig') as file:
    discord_tokens = [line.strip() for line in file]

print(Fore.BLUE + f'Loaded {len(emails)} emails:')
print('\033[39m')
