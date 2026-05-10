import threading
import requests
import time
import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def buy_ticket(user_id, event_id, ticket_id, quantity):
    url = f"http://127.0.0.1:8000/buy-ticket/{event_id}/"
    logger.debug(
        f"User {user_id}: Attempting to buy {quantity} tickets for event {event_id}"
    )

    data = {
        "email": f"user{user_id}@example.com",
        "first_name": f"User{user_id}",
        "last_name": f"Test{user_id}",
        "phone": "1234567890",
        f"quantity_{ticket_id}": quantity,
        "csrfmiddlewaretoken": "testcsrftoken",  # Временное решение для теста
    }

    headers = {
        "Referer": f"http://127.0.0.1:8000/buy-ticket/{event_id}/",
    }

    try:
        logger.debug(f"User {user_id}: Sending POST request to {url}")
        response = requests.post(url, data=data, headers=headers)
        logger.debug(f"User {user_id}: Response status {response.status_code}")

        print(f"User {user_id} response status: {response.status_code}")
        if response.status_code == 200:
            print(f"User {user_id} response content: {response.text[:200]}...")

        return response.status_code
    except Exception as e:
        logger.error(f"User {user_id}: Error occurred - {str(e)}")
        print(f"User {user_id} error: {str(e)}")
        return None


def main():
    event_id = 1  # Замените на ID вашего мероприятия
    ticket_id = 1  # Замените на ID билета, который вы хотите протестировать
    quantity = 1

    # Создаем потоки для имитации одновременной покупки билетов
    thread1 = threading.Thread(
        target=buy_ticket, args=(1, event_id, ticket_id, quantity)
    )
    thread2 = threading.Thread(
        target=buy_ticket, args=(2, event_id, ticket_id, quantity)
    )

    # Запускаем потоки
    logger.debug("Starting threads for concurrent ticket purchase")
    thread1.start()
    thread2.start()

    logger.debug("Threads started, waiting for completion")

    # Ждем завершения потоков
    thread1.join()
    thread2.join()

    logger.debug("Threads completed")


if __name__ == "__main__":
    main()
