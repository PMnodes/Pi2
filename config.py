# Версия софта от 16:20 07.09.2025
LICENSE_KEY = ''  # Брать ключ в боте, по кнопке "Софты"

MOBILE_PROXY = False  # True - мобильные proxy/False - обычные proxy
ROTATE_IP = False  # Настройка только для мобильных proxy

TG_BOT_TOKEN = ''  # str ('2282282282:NTQxMjU0NTUwsKqQSWIMqsU-T0RaKWBTnx8IKdbNiATf4y_Dy2s6TLs')
TG_USER_ID = 123  # int (22822822) or None

SHUFFLE_WALLETS = False
PAUSE_BETWEEN_WALLETS = [1, 1]
PAUSE_BETWEEN_MODULES = [1, 1]
MAX_PARALLEL_ACCOUNTS = 10
REDIRECT = False  # Использовать ли редирект на одну почту (для icloud)
MAIN_ICLOUD_EMAIL_LOGIN = ''
APP_PASSWORD = ''

RETRIES = 3  # Сколько раз повторять 'зафейленное' действие
PAUSE_BETWEEN_RETRIES = 10  # Пауза между повторами

COMPLETE_QUESTS = False
PLAY_GAME = False  # Настройка в GameSettings


class GameSettings:
    num_plays = [2, 4]
