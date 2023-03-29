import logging
import sys
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        non_token = ''
        if token is None:
            non_token += f'"{token}" '
    if non_token != '':
        logging.critical(f'Токены {non_token} не определены')
        raise NameError(f'Токены {non_token} не определены')


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Сообщение {message} успешно отправлено')
    except Exception:
        logging.error(f'Сбой при отправке сообщения: {message}')


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    logging.debug(f'Началась проверка запроса к API: "{ENDPOINT}" '
                  f'с параметрами {payload}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        logging.debug(f'Запрос к API: "{ENDPOINT}" осуществлен успешно')
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка при запросе к API "{ENDPOINT}"'
                              f'c параметрами {payload}: {error}')
    if response.status_code != HTTPStatus.OK:
        raise ConnectionError('Неверный статус ответа от API')
    logging.debug('Получен ответ')
    return response.json()


def check_response(response):
    """Проверка ответа API на соответсвие документации."""
    logging.debug(f'Началась проверка ответа API: "{response}" '
                  'на соответсвие документации')
    if not isinstance(response, dict):
        raise TypeError('Ответ не является словарем')
    if 'homeworks' not in response:
        raise TypeError('Ответ не содержит ключа "homeworks"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Поле "homeworks" не является списком')
    if 'current_date' not in response:
        raise TypeError('Ответ не содержит ключа "current_date"')
    return response['homeworks']


def parse_status(homework):
    """Извлекает сатус конкретной домашней работы."""
    logging.debug(f'Началась проверка статуса домашней работы: "{homework}"')
    if 'homework_name' in homework:
        homework_name = homework['homework_name']
    else:
        raise ValueError('В ответе отсутсвует ключ homework_name')
    status = homework.get('status')
    if status is None:
        raise ValueError('В ответе отсутсвует ключ stutus')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError('Недокументированный статус')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    errors = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logging.info('Статус домашней работы ещё не обновился')
            errors = ''
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            if message != errors:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message
                )
                errors = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.StreamHandler(sys.stdout)],
        format="%(asctime)s — %(name)s — %(levelname)s —"
        "%(message)s - %(funcName)s - %(lineno)d")
    main()
