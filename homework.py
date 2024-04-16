import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Dict

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600  # 10 minutes
CHECK_PERIOD = 259200 * 3
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

HISTORY: Dict[str, str] = {}

logger = logging.getLogger('telegram-bot-logger')
logger.setLevel(logging.DEBUG)

log_format = '%(asctime)s - %(levelname)s - %(message)s'
log_formatter = logging.Formatter(log_format, style='%')

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setFormatter(log_formatter)

logger.addHandler(stream_handler)


def check_tokens() -> bool:
    """Проверка токенов на наличие."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for token in tokens:
        if tokens[token] is None:
            logger.critical('Token %s not found', token)
            return False
    return True


def send_message(bot: Bot, message) -> None:
    """Отправка сообщения."""
    try:
        bot.send_message(
            text=message,
            chat_id=TELEGRAM_CHAT_ID)
        logger.debug('Message sent')
    except telegram.error.TelegramError as error:
        raise exceptions.FailedToSendMessageError(error)


def get_api_answer(timestamp) -> Dict:
    """Запрос к серверу Яндекс."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code == HTTPStatus.OK:
            logger.debug('Response: OK')
            return response.json()
        logger.error(
            'API can not reach ENDPOINT with args: %s, %s, %s',
            payload,
            ENDPOINT,
            HEADERS
        )
        raise exceptions.EmptyAPIResponseError
    except requests.RequestException as error:
        logger.error('get_api_answer() error %s', error.args)


def check_response(response) -> None:
    """Проверка ответа от сервера."""
    if not isinstance(response, dict):
        raise TypeError('response is not Dict type')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('"homeworks" in response is not List type')
    if 'current_date' not in response:
        raise TypeError('key "current_date" not in response')


def parse_status(homework: Dict) -> str:
    """Поиск статуса отдельной работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    status_answer = HOMEWORK_VERDICTS.get(homework_status)
    if not homework_name or not status_answer:
        logger.error('parse_status() income data error')
        raise exceptions.ParseStatusError
    HISTORY[homework_name] = status_answer
    return (
        'Изменился статус проверки работы '
        f'"{homework_name}"\n'
        f'{status_answer}'
    )


def history_status_check(homework):
    """Возвращает результат проверки статуса на обновления."""
    homework_name = homework.get('homework_name')
    homework_status = HOMEWORK_VERDICTS.get(homework.get('status'))
    history_status = HISTORY.get(homework_name)
    if history_status != homework_status:
        return parse_status(homework)
    logger.debug('No updates')
    return ''


def try_send_message(bot, message):
    """Предпринимает попытку отправки сообщения.
    Логирует неудачную отправку.
    """
    try:
        send_message(bot, message)
    except (exceptions.FailedToSendMessageError, SystemExit) as error:
        logger.error('Failed to send message %s', error)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Tokens not found')
        raise exceptions.TokenNotFoundError()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - CHECK_PERIOD

    while True:
        message: str = ''
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            for homework in homeworks:
                message = history_status_check(homework)
        except exceptions.EmptyAPIResponseError:
            message = 'API вернул пустой ответ'
        except TypeError:
            message = 'API вернул неправильный ответ'
        except requests.RequestException:
            message = 'Произошла ошибка запроса'
        except exceptions.ParseStatusError:
            message = 'Ошибка расшифровки статуса'
        finally:
            try_send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
