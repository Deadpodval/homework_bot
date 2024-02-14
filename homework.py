import logging
import os
import time
import exceptions
from typing import Dict

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TOKENS = {
    'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
}

RETRY_PERIOD = 600
CHECK_PERIOD = 259200  # ~ 72 hours
STATUS_OK = 200
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

HISTORY = {}

logger = logging.getLogger('telegram-bot-logger')
logger.setLevel(logging.DEBUG)

log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_formatter = logging.Formatter(log_format, style='%')

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

logger.addHandler(stream_handler)


def check_tokens() -> bool:
    """Проверка токенов на наличие."""
    for token in TOKENS:
        if TOKENS[token] is None:
            logger.critical('Token not found: %s', token)
            return False
    return True


def send_message(bot: Bot, message) -> None:
    """Отправка сообщения."""
    try:
        bot.send_message(
            text=message,
            chat_id=TELEGRAM_CHAT_ID)
        logger.debug('message sent')
    except exceptions.SendMessageError as error:
        logger.error('send_message() function error: %s', error)


def get_api_answer(timestamp) -> Dict:
    """Запрос к серверу Яндекс."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != STATUS_OK:
            err_data = {
                'status_code': response.status_code,
                'headers': HEADERS,
                'payload': payload
            }
            logger.error('Failed connection. Response code: %s', err_data)
            raise exceptions.ServerConnectionError
        else:
            return response.json()
    except requests.RequestException as error:
        logger.error(error.args)


def check_response(response) -> None:
    """Проверка ответа от сервера."""
    if not isinstance(response, dict):
        logger.error('Unexpected data in check_response()')
        raise TypeError('Unexpected data in check_response()')
    if not isinstance(response.get('homeworks'), list):
        logger.error('"homeworks" does not contain list')
        raise TypeError('"homeworks" does not contain list')
    if 'current_date' not in response.keys():
        logger.error('"current_date" not in response')
        raise TypeError('key "current_date" not in response')


def parse_status(homework: Dict) -> str:
    """Поиск статуса отдельной работы."""
    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        status_answer = HOMEWORK_VERDICTS.get(homework_status)
        if not homework_name or not status_answer:
            logger.error('parse_status() income data error')
            raise exceptions.ParseStatusError
        else:
            HISTORY[homework_name] = status_answer
            return (
                f'Изменился статус проверки работы '
                f'"{homework_name}"'
                f'{status_answer}'
            )

    except exceptions.ParseStatusError:
        logger.error('parse_status() function error')
        raise KeyError(homework.get('name'))


def main():
    """Основная логика работы бота."""
    logger.info('starting ...')
    token_check = check_tokens()
    if not token_check:
        logger.critical('shutting down...')
        raise exceptions.TokenNotFoundError
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - CHECK_PERIOD

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            for homework in homeworks:
                homework_name = homework.get('homework_name')
                homework_status = homework.get('status')
                current_status = HOMEWORK_VERDICTS[homework_status]
                history_status = HISTORY.get(homework_name)
                if current_status:
                    message = parse_status(homework)
                    if history_status != current_status:
                        send_message(bot, message)
                        logger.debug('message sent')
                    else:
                        logger.debug('no updates')
        except exceptions.GlobalException as error:
            logger.critical('Failed main() function %s', error.args)
            try:
                send_message(bot, error)
                logger.debug('message sent')
            except exceptions.SendMessageError:
                logger.error('Send message error')

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
