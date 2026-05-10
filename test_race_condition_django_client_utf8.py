# -*- coding: utf-8 -*-
import threading
from django.test import Client
from core.models import Event, Ticket, Order
import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def buy_ticket_with_client(client, user_id, event_id, ticket_id, quantity):
    logger.debug(
        f"User {user_id}: Attempting to buy {quantity} tickets for event {event_id}"
    )

    # Получаем страницу покупки для установки CSRF токена
    response = client.get(f"/buy-ticket/{event_id}/")

    # Данные для покупки
    data = {
        "email": f"user{user_id}@example.com",
        "first_name": f"User{user_id}",
        "last_name": f"Test{user_id}",
        "phone": "1234567890",
        f"quantity_{ticket_id}": quantity,
    }

    # Используем CSRF токен из куки
    data["csrfmiddlewaretoken"] = response.cookies["csrftoken"].value

    try:
        logger.debug(f"User {user_id}: Sending POST request")
        response = client.post(f"/buy-ticket/{event_id}/", data=data)
        logger.debug(f"User {user_id}: Response status {response.status_code}")

        print(f"User {user_id} response status: {response.status_code}")
        if response.status_code == 302:  # Ожидаем редирект после успешной покупки
            print(f"User {user_id}: Purchase successful, redirected to {response.url}")
        elif response.status_code == 200:
            print(
                f"User {user_id} response content: {response.content.decode('utf-8')[:200]}..."
            )

        return response.status_code
    except Exception as e:
        logger.error(f"User {user_id}: Error occurred - {str(e)}")
        print(f"User {user_id} error: {str(e)}")
        return None


def check_ticket_quantity(ticket_id):
    ticket = Ticket.objects.get(id=ticket_id)
    logger.debug(
        f"Ticket {ticket_id} available quantity: {ticket.get_available_count()}"
    )
    return ticket.get_available_count()


def main():
    event_id = 1
    ticket_id = 1
    quantity = 1

    # Создаем тестовых клиентов
    client1 = Client()
    client2 = Client()

    # Проверяем начальное количество билетов
    initial_quantity = check_ticket_quantity(ticket_id)
    print(f"Initial available quantity: {initial_quantity}")

    # Создаем потоки для имитации одновременной покупки билетов
    thread1 = threading.Thread(
        target=buy_ticket_with_client, args=(client1, 1, event_id, ticket_id, quantity)
    )
    thread2 = threading.Thread(
        target=buy_ticket_with_client, args=(client2, 2, event_id, ticket_id, quantity)
    )

    logger.debug("Starting threads for concurrent ticket purchase")

    # Запускаем потоки
    thread1.start()
    thread2.start()

    logger.debug("Threads started, waiting for completion")

    # Ждем завершения потоков
    thread1.join()
    thread2.join()

    logger.debug("Threads completed")

    # Проверяем итоговое количество билетов
    final_quantity = check_ticket_quantity(ticket_id)
    print(f"Final available quantity: {final_quantity}")

    # Проверяем количество заказов
    orders_count = Order.objects.filter(ticket_id=ticket_id).count()
    print(f"Total orders created: {orders_count}")

    # Анализ результатов
    if initial_quantity - final_quantity > 1:
        print("RACE CONDITION DETECTED: More tickets sold than available!")
    else:
        print("No race condition detected")


if __name__ == "__main__":
    main()
