import os
import time
import logging
from typing import Dict
import requests
from dotenv import load_dotenv
from telegram import Bot


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
CHECK_PERIOD = 2592000 * 2  # ~ 2 month
STATUS_OK = 200
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
ERROR_MESSAGES = []

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger('telegram-bot-logger')
logger.setLevel(logging.DEBUG)

log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_formatter = logging.Formatter(log_format, style='%')

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

logger.addHandler(stream_handler)


def check_tokens() -> None:
    """Проверка токенов на наличие."""
    err = False
    if PRACTICUM_TOKEN is None:
        logger.critical('PRACTICUM_TOKEN not found')
        err = True
    if TELEGRAM_TOKEN is None:
        logger.critical('TELEGRAM_TOKEN not found')
        err = True
    if PRACTICUM_TOKEN is TELEGRAM_TOKEN:
        logger.critical('PRACTICUM_TOKEN and TELEGRAM_TOKEN not found')
        err = True
    if err:
        raise ValueError('Tokens not found')


def send_message(bot: Bot, message) -> None:
    """Отправка сообщения."""
    try:
        bot.send_message(
            text=message,
            chat_id=TELEGRAM_CHAT_ID)
        logger.debug('message sent')
    except Exception as error:
        logger.error(f'Failed to send message: {error}')


def get_api_answer(timestamp) -> [Dict]:
    """Запрос к серверу Яндекс."""
    global ERROR_MESSAGES
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != STATUS_OK:
            print(response.status_code)
            logger.error('Failed connection')
            ERROR_MESSAGES.append('Ошибка соединения с сервером')
            raise Exception
        else:
            return response.json()
    except requests.RequestException as error:
        logger.error(error.args)


def check_response(response) -> None:
    """Проверка ответа от сервера."""
    global ERROR_MESSAGES
    if not isinstance(response, dict):
        logger.error('Unexpected data in check_response()')
        ERROR_MESSAGES.append('Ошибка в функции check_response()')
        raise TypeError
    if not isinstance(response.get('homeworks'), list):
        logger.error('"homeworks" does not contain list')
        ERROR_MESSAGES.append('Ошибка в функции check_response()')
        raise TypeError


def parse_status(homework: Dict):
    """Поиск статуса отдельной работы."""
    global ERROR_MESSAGES
    try:
        return (
                'Изменился статус проверки работы '
                f'"{homework["homework_name"]}"'
                f'{HOMEWORK_VERDICTS[homework["status"]]}'
        )
    except KeyError:
        logger.error('parse_status() function error')
        ERROR_MESSAGES.append('')
        raise KeyError(homework.get('name'))


def main():
    """Основная логика работы бота."""

    logger.info('starting ...')
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - CHECK_PERIOD

    while True:
        response = get_api_answer(timestamp)
        check_response(response)
        homeworks = response.get('homeworks')

        for homework in homeworks:
            status = parse_status(homework)
            if status:
                send_message(bot, status)
        if ERROR_MESSAGES:
            send_message(bot, '\n'.join(ERROR_MESSAGES))
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
