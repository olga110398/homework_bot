import logging
import os
import time

import requests
import telegram

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()


logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
print(PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

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
    if PRACTICUM_TOKEN is None and\
        TELEGRAM_TOKEN is None and\
            TELEGRAM_CHAT_ID is None:
        logging.critical('Один или несколько токенов не определены')
        raise NameError('Один или несколько токенов не определены')
    else:
        return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение успешно отправлено')
    except Exception:
        logging.error(f'Сбой при отправке сообщения: {message}')


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as error:
        logging.error(f'Ошибка при запросе к API: {error}')
        raise ConnectionError(f'Ошибка при запросе к API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise ConnectionError('Неверный статус ответа от API')
    logging.debug('Получен ответ')
    result = response.json()
    return result


def check_response(response):
    """Проверка ответа API на соответсвие документации."""
    if 'homeworks' not in response:
        logging.error('Ответ не содержит ключа "homeworks"')
        raise TypeError('Ответ не содержит ключа "homeworks"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logging.error('Поле "homeworks" не является списком')
        raise TypeError('Поле "homeworks" не является списком')
    if 'current_date' not in response:
        logging.error('Ответ не содержит ключа "current_date"')
        raise TypeError('Ответ не содержит ключа "current_date"')
    return response['homeworks']


def parse_status(homework):
    """Извлекает сатус конкретной домашней работы."""
    if homework is not None:
        if 'homework_name' in homework:
            homework_name = homework['homework_name']
        else:
            logging.error('В ответе отсутсвует ключ homework_name')
            raise ValueError('В ответе отсутсвует ключ homework_name')
        status = homework['status']
        if status is None:
            logging.error('В ответе отсутсвует ключ stutus')
            raise ValueError('В ответе отсутсвует ключ stutus')
        if status not in HOMEWORK_VERDICTS:
            logging.error('Недокументированный статус')
            raise ValueError('Недокументированный статус')
        verdict = HOMEWORK_VERDICTS[status]
        if verdict is None:
            return 'Статус проверки работы не изменился'
        else:
            return (f'Изменился статус проверки работы "{homework_name}".'
                    f'{verdict}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Переменные окружения отсутсвуют')
        raise Exception('Переменные окружения отсутсвуют')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    list_of_errors = []

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logging.info('Статус домашней работы ещё не обновился')
            list_of_errors.clear()
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message not in list_of_errors:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message
                )
                list_of_errors.append(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
