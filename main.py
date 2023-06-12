from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from vkbottle import BaseStateGroup
from vkbottle.dispatch.rules.base import CommandRule
from vkbottle import DocMessagesUploader
from typing import Tuple
import psycopg2
import os
import fpdf

connection_string = os.environ.get("DATABASE_URL", "none")
database_connection = ""


def database_request(request_str, return_result=True):
    cur = database_connection.cursor()
    cur.execute(request_str)
    database_connection.commit()
    if return_result:
        return cur.fetchall()
    else:
        return ""


DEFAULT_KEYBOARD = Keyboard(one_time=True, inline=False)
DEFAULT_KEYBOARD.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
DEFAULT_KEYBOARD = DEFAULT_KEYBOARD.get_json()


admin_ids = [127362323, 340079031]
customer_ids = []
contractor_ids = []
accountant_ids = []

global_user_data = {}

bot = Bot(token="vk1.a.XssyEwFYP0booLZmLd5pLlns-lukHTVaQz6t5LnM3K10dqWi5QYN4eWcxtroVor-YsZQtbqBSHIWPrGEs8qDZ6FXdwgQw570xuEGXfQ4ZjqTBW6X2TdmhMuIwmeZym6rwufoThA43HwIOjcJFDnodF6HwZbw2jEn4fHc8asFSVwe68bIKjb0xqSyaKY82MnLdKFbAz0PKGBQx3tacuaGWA")

if connection_string == "none":
    print("entering test mode")
    connection_string = input("manually enter connection_string: ")
database_connection = psycopg2.connect(connection_string)


result = database_request("SELECT customer_vk_id FROM public.customer;")
for element in result:
    customer_ids.append(int(element[0]))

result = database_request("SELECT contractor_vk_id FROM public.contractor")
for element in result:
    contractor_ids.append(int(element[0]))

result = database_request("SELECT accountant_vk_id FROM public.accountant")
for element in result:
    accountant_ids.append(int(element[0]))

'''
ФУНКЦИИ РАБОТЫ С БД
'''


async def create_new_customer(vk_id):
    user_info = await bot.api.users.get(vk_id)
    name = user_info[0].first_name
    surname = user_info[0].last_name
    database_request("INSERT INTO public.customer(customer_surname, customer_name, customer_vk_id) VALUES ('{0}', '{1}', '{2}');".format(
        surname, name, vk_id), False)
    customer_ids.append(vk_id)


async def create_new_order(vk_id, oblast, price, description):
    if not vk_id in customer_ids:
        await create_new_customer(vk_id)

    customer_id = database_request(
        "SELECT customer_id FROM public.customer WHERE customer_vk_id LIKE '{0}'".format(vk_id))
    customer_id = customer_id[0][0]

    order_id = database_request("INSERT INTO public.order (customer_id, order_desiredprice, order_subjectarea, order_requirements) VALUES ('{0}', '{1}', '{2}', '{3}');SELECT LASTVAL();".format(
        customer_id, price, oblast, description), True)
    order_id = order_id[0][0]
    database_request(
        f"INSERT INTO public.account(order_id, account_login, account_password, account_socialnetwork) VALUES ('{order_id}', 'отсутствует', 'отсутствует', 'отсутствует');", False)

    new_message = "У нас новый заказ!\n" + await get_order_data(order_id)
    for element in contractor_ids:
        await bot.api.messages.send(peer_id=element, message=new_message, random_id=0)


async def get_order_data(order_id):
    result = database_request(
        f"SELECT order_desiredprice, order_subjectarea, order_requirements FROM public.order WHERE order_id={order_id}")
    return f"Номер Заказа: {order_id}\nПредметная область: {result[0][1]}\nЖелаемая цена: {result[0][0]}\nТребования: {result[0][2]}"


async def get_order_data_detailed(order_id):
    result = database_request(
        f"SELECT order_desiredprice, order_subjectarea, order_requirements, account_socialnetwork, account_login, account_password FROM public.order, public.account WHERE public.account.order_id={order_id} AND public.order.order_id={order_id}")
    result = result[0]
    return f"Номер Заказа: {order_id}\nПредметная область: {result[1]}\nЖелаемая цена: {result[0]}\nТребования: {result[2]}\n\nДанные от аккаунта:\nСоциальная сеть: {result[3]}\nЛогин: {result[4]}\nПароль: {result[5]}"


async def add_new_content_to_order(order_id, text):
    database_request(
        f"INSERT INTO public.content(order_id, content_text) VALUES ('{order_id}', '{text}');", False)
    contractor_id = database_request(
        f"SELECT contractor_vk_id FROM public.contractor WHERE contractor_id IN (SELECT contractor_id FROM public.order WHERE order_id={order_id})")
    contractor_id = contractor_id[0][0]
    await bot.api.messages.send(peer_id=contractor_id, message=f"Новый контент!\nНомер заказа: {order_id}\nСообщение заказчика:\n{text}", random_id=0)


def get_user_data(user_id):
    if global_user_data.get(user_id, None) == None:
        global_user_data[user_id] = {"state": "default_state"}
    return global_user_data[user_id]


async def contractor_accept_order(vk_id, order_id):
    contractor_id = database_request(
        f"SELECT contractor_id, contractor_name FROM public.contractor WHERE contractor_vk_id LIKE '{vk_id}'")
    contractor_name = contractor_id[0][1]
    contractor_id = contractor_id[0][0]
    user_vk_id = database_request(
        f"SELECT customer_vk_id FROM public.customer WHERE customer_id IN (SELECT customer_id FROM public.order WHERE order_id={order_id})")
    user_vk_id = user_vk_id[0][0]
    database_request(
        f"UPDATE public.order SET contractor_id='{contractor_id}' WHERE order_id='{order_id}';", False)
    await bot.api.messages.send(peer_id=user_vk_id, message=f"Оператор @id{vk_id} ({contractor_name}) работает над вашим заказом! Ожидайте сообщение от него вскоре", random_id=0)


async def contractor_send_message(order_id, text):
    user_vk_id = database_request(
        f"SELECT customer_vk_id FROM public.customer WHERE customer_id IN (SELECT customer_id FROM public.order WHERE order_id={order_id})")
    user_vk_id = user_vk_id[0][0]
    message_text = f"Вам сообщение от эксперта!\nНомер заказа:{order_id}\nТекст:\n{text}"
    await bot.api.messages.send(peer_id=user_vk_id, message=message_text, random_id=0)


async def create_new_contractor(vk_id):
    user_info = await bot.api.users.get(vk_id)
    name = user_info[0].first_name
    surname = user_info[0].last_name
    database_request("INSERT INTO public.contractor(contractor_surname, contractor_name, contractor_vk_id) VALUES ('{0}', '{1}', '{2}');".format(
        surname, name, vk_id), False)
    contractor_ids.append(vk_id)


async def create_new_accountant(vk_id):
    user_info = await bot.api.users.get(vk_id)
    name = user_info[0].first_name
    surname = user_info[0].last_name
    database_request("INSERT INTO public.accountant(accountant_surname, accountant_name, accountant_vk_id) VALUES ('{0}', '{1}', '{2}');".format(
        surname, name, vk_id), False)
    accountant_ids.append(vk_id)


async def update_account_info(order_id, social, login, password):

    database_request(
        f"UPDATE public.account SET account_login='{login}', account_password='{password}', account_socialnetwork='{social}' WHERE order_id={order_id};", False)


async def create_new_report(order_id, contractor_vk_id, scope, numberpublications):
    contractor_id = database_request(
        f"SELECT contractor_id FROM public.contractor WHERE contractor_vk_id LIKE '{contractor_vk_id}'")[0][0]
    database_request(
        f"INSERT INTO public.report(order_id, contractor_id, report_startdate, report_scope, report_numberpublications) VALUES ({order_id}, {contractor_id}, CURRENT_DATE, '{scope}', '{numberpublications}');", False)

    user_vk_id = database_request(
        f"SELECT customer_vk_id FROM public.customer WHERE customer_id IN (SELECT customer_id FROM public.order WHERE order_id={order_id})")[0][0]
    await bot.api.messages.send(peer_id=user_vk_id, message=f"Новый отчёт от исполнителя!\nНомер заказа: {order_id}\nОхват: {scope}\nКол-во публикаций: {numberpublications}", random_id=0)


async def create_new_profit(accountant_id, order_id, initialcost, costmaintenance, totalcost):
    database_request(
        f"INSERT INTO public.profit(accountant_id, order_id, profit_initialcost, profit_costmaintenance, profit_totalcost) VALUES ('{accountant_id}', '{order_id}', '{initialcost}', '{costmaintenance}', '{totalcost}');", False)

    user_vk_id = database_request(
        f"SELECT customer_vk_id FROM public.customer WHERE customer_id IN (SELECT customer_id FROM public.order WHERE order_id={order_id})")[0][0]
    await bot.api.messages.send(peer_id=user_vk_id, message=f"Вам выписан счёт!\nНомер заказа: {order_id}\nНачальная стоимость: {initialcost}\nСтоимость ведения: {costmaintenance}\n Всего к выплате: {totalcost}", random_id=0)


'''
ФУНКЦИИ ОБРАБОТЧИКИ СОСТОЯНИЙ
'''


def default_state(user_data, message: Message):
    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(Text("Создать Заказ"), color=KeyboardButtonColor.POSITIVE)

    if message.from_id in customer_ids:
        my_keyboard.row()
        my_keyboard.add(Text("Мои Заказы"))
        my_keyboard.add(Text("Мои счета"))
        my_keyboard.row()
        my_keyboard.add(Text("Добавить Контент"))
        my_keyboard.add(Text("Обновить Аккаунт"))

    if message.from_id in contractor_ids:
        my_keyboard.row()
        my_keyboard.add(Text("Доступные Заказы"),
                        color=KeyboardButtonColor.POSITIVE)
        my_keyboard.row()
        my_keyboard.add(Text("Принятые Заказы"))
        my_keyboard.row()
        my_keyboard.add(Text("Сообщение Заказчику"))
        my_keyboard.add(Text("Отправить Отчёт"))

    if message.from_id in accountant_ids:
        my_keyboard.row()
        my_keyboard.add(Text("Выписать счёт"),
                        color=KeyboardButtonColor.POSITIVE)
        my_keyboard.add(Text("Получить отчёт"))

    if message.from_id in admin_ids:
        my_keyboard.row()
        my_keyboard.add(Text("Добавить Исполнителя"),
                        color=KeyboardButtonColor.POSITIVE)
        my_keyboard.add(Text("Добавить Бухгалтера"),
                        color=KeyboardButtonColor.POSITIVE)

    my_keyboard = my_keyboard.get_json()
    return {
        "text": "Главное меню",
        "keyboard": my_keyboard,
    }


def new_order_get_oblast_state(user_data, message: Message):
    user_data["new_order_oblast"] = message.text
    user_data["state"] = "new_order_get_price_state"
    return {
        "text": "Спасибо, теперь напиши желаемую цену",
        "keyboard": DEFAULT_KEYBOARD,
    }


def new_order_get_price_state(user_data, message: Message):
    user_data["new_order_price"] = message.text
    user_data["state"] = "new_order_get_description_state"
    return {
        "text": "Спасибо, теперь напиши требования к заказу",
        "keyboard": DEFAULT_KEYBOARD,
    }


def new_order_get_description_state(user_data, message: Message):
    user_data["new_order_description"] = message.text
    user_data["state"] = "default_state"

    oblast = user_data["new_order_oblast"]
    price = user_data["new_order_price"]
    description = user_data["new_order_description"]

    final_answer = "Данные вашего заказа:\nПредметная область: {0}\nЖелаемая цена: {1}\nТребования: {2}\n\nВсё верно?".format(
        oblast, price, description)

    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(Text("Принять Заказ"), color=KeyboardButtonColor.POSITIVE)
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()

    return {
        "text": final_answer,
        "keyboard": my_keyboard,
    }


def new_content_text(user_data, message: Message):
    user_data["new_content_text"] = message.text
    user_data["state"] = "default_state"

    order_id = user_data["content_order_id"]
    user_data["content_text"] = message.text
    new_text = user_data["content_text"]
    final_answer = f"Введённые данные:\nНомер заказа: {order_id}\nСообщение: {new_text}\nВсё верно?"

    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(Text("Отправить контент"),
                    color=KeyboardButtonColor.POSITIVE)
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    return {
        "text": final_answer,
        "keyboard": my_keyboard,
    }


def new_order_message_text(user_data, message: Message):
    user_data["order_message_text"] = message.text
    user_data["state"] = "default_state"
    order_id = user_data["order_message_order_id"]
    final_answer = "Отправляем?"

    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(Text("Отправить Сообщение Заказчику"),
                    color=KeyboardButtonColor.POSITIVE)
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    return {
        "text": final_answer,
        "keyboard": my_keyboard,
    }


def new_contractor_vk_id(user_data, message: Message):
    user_data["new_contractor_vk_id"] = message.text
    user_data["state"] = "default_state"
    final_answer = "Добавляем исполнителя?"
    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(Text("Добавить Нового Исполнителя"),
                    color=KeyboardButtonColor.POSITIVE)
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    return {
        "text": final_answer,
        "keyboard": my_keyboard,
    }


def new_accountant_vk_id(user_data, message: Message):
    user_data["new_accountant_vk_id"] = message.text
    user_data["state"] = "default_state"
    final_answer = "Добавляем бухгалтера?"
    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(Text("Добавить Нового Бухгалтера"),
                    color=KeyboardButtonColor.POSITIVE)
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    return {
        "text": final_answer,
        "keyboard": my_keyboard,
    }


def update_account_text(user_data, message: Message):
    user_data["update_account_text"] = message.text
    user_data["state"] = "default_state"

    final_answer = "Всё верно?"

    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(Text("Обновить Аккаунт!"),
                    color=KeyboardButtonColor.POSITIVE)
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    return {
        "text": final_answer,
        "keyboard": my_keyboard,
    }


def new_report_scope(user_data, message: Message):
    user_data["new_report_scope"] = message.text
    user_data["state"] = "new_report_numberpublications"
    return {
        "text": "Спасибо, теперь напиши кол-во публикаций",
        "keyboard": DEFAULT_KEYBOARD,
    }


def new_report_numberpublications(user_data, message: Message):
    user_data["new_report_numberpublications"] = message.text
    user_data["state"] = "default_state"

    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(Text("Отправить Отчёт!"),
                    color=KeyboardButtonColor.POSITIVE)
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()

    return {
        "text": "Отправить отчёт?",
        "keyboard": my_keyboard,
    }


def new_profit_initialcost(user_data, message: Message):
    user_data["new_profit_initialcost"] = message.text
    user_data["state"] = "new_profit_costmaintenance"

    return {
        "text": "Спасибо, теперь укажи стоимость ведения",
        "keyboard": DEFAULT_KEYBOARD,
    }


def new_profit_costmaintenance(user_data, message: Message):
    user_data["new_profit_costmaintenance"] = message.text
    user_data["state"] = "default_state"

    order_id = user_data["new_profit_order_id"]
    initialcost = user_data["new_profit_initialcost"]
    costmaintenance = user_data["new_profit_costmaintenance"]
    if not (initialcost.isdigit() and costmaintenance.isdigit()):
        return {
            "text": "Неверно введены данные. Перепроверьте",
            "keyboard": DEFAULT_KEYBOARD,
        }
    totalcost = int(costmaintenance)
    user_data["new_profit_totalcost"] = totalcost

    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(Text("Выписать счёт!"), color=KeyboardButtonColor.POSITIVE)
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()

    return {
        "text": f"Вы ввели:\nНомер заказа: {order_id}\nНачальная стоимость: {initialcost}\nСтоимость ведения: {costmaintenance}\n Всего к выплате: {totalcost}\n\nВсё верно?",
        "keyboard": my_keyboard,
    }


'''
ОБРАБОТЧИКИ КОНКРЕТНЫХ СООБЩЕНИЙ/КОМАНД
'''


@bot.on.message(text="Отмена")
async def get_to_default_state(message: Message):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_data["state"] = "default_state"
    answer = default_state(user_data, message)
    await message.answer(answer["text"], keyboard=answer["keyboard"])


@bot.on.message(text="Создать Заказ")
async def new_order(message: Message):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_data["state"] = "new_order_get_oblast_state"
    await message.answer("Напиши предметную область", keyboard=DEFAULT_KEYBOARD)


@bot.on.message(text="Принять Заказ")
async def confirm_order(message: Message):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    oblast = user_data["new_order_oblast"]
    price = user_data["new_order_price"]
    description = user_data["new_order_description"]
    if not price.isdigit():
        await message.answer("Неправильно указана цена. Цена должна быть числом.")
        await get_to_default_state(message)
        return

    await create_new_order(user_id, oblast, price, description)
    await message.answer("Спасибо! Ваша заявка на рассмотрении. Наш оператор вскоре свяжется с вами")
    await get_to_default_state(message)


@bot.on.message(text="Мои Заказы")
async def my_orders(message: Message):
    my_orders = database_request(
        f"SELECT order_id, order_subjectarea FROM public.order WHERE customer_id IN (SELECT customer_id FROM public.customer WHERE customer_vk_id='{message.from_id}')")
    my_keyboard = Keyboard(one_time=True, inline=False)
    for element in my_orders:
        subject_area = element[1].replace(" ", "_")
        my_keyboard.row()
        my_keyboard.add(Text(f"!мой_заказ {element[0]} {subject_area}"))
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()

    await message.answer("меню", keyboard=my_keyboard)


@bot.on.message(command=("мой_заказ", 2))
async def my_order(message: Message, args: Tuple[str]):
    answer = await get_order_data_detailed(args[0])
    await message.answer(answer)
    await get_to_default_state(message)


@bot.on.message(text="Добавить Контент")
async def new_content(message: Message):
    my_orders = database_request(
        f"SELECT order_id FROM public.order WHERE customer_id IN (SELECT customer_id FROM public.customer WHERE customer_vk_id='{message.from_id}')")
    my_keyboard = Keyboard(one_time=True, inline=False)
    for element in my_orders:
        my_keyboard.row()
        my_keyboard.add(Text(f"!добавить_контент {element[0]}"))
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()

    await message.answer("меню", keyboard=my_keyboard)


@bot.on.message(command=("добавить_контент", 1))
async def add_content(message: Message, args: Tuple[str]):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_data["state"] = "new_content_text"
    user_data["content_order_id"] = args[0]
    await message.answer("А теперь напиши своё сообщение эксперту с любым текстом.", keyboard=DEFAULT_KEYBOARD)


@bot.on.message(text="Отправить контент")
async def send_content(message: Message):
    user_data = get_user_data(message.from_id)
    order_id = user_data["content_order_id"]
    new_text = user_data["content_text"]
    await add_new_content_to_order(order_id, new_text)
    await message.answer("Спасибо! Ваш новый контент отправлен вашему оператору!")
    await get_to_default_state(message)


@bot.on.message(text="Доступные Заказы")
async def available_orders(message: Message):
    orders = database_request(
        f"SELECT order_id, order_desiredprice, order_subjectarea, order_requirements FROM public.order WHERE contractor_id ISNULL")
    my_keyboard = Keyboard(one_time=True, inline=False)
    for element in orders:
        my_keyboard.row()
        my_keyboard.add(
            Text(f"!доступный_заказ {element[0]}"), color=KeyboardButtonColor.POSITIVE)
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    await message.answer("Список доступных заказов", keyboard=my_keyboard)


@bot.on.message(command=("доступный_заказ", 1))
async def my_order(message: Message, args: Tuple[str]):
    answer = await get_order_data(args[0])
    my_keyboard = Keyboard(one_time=True, inline=False)
    my_keyboard.add(
        Text(f"!принять_заказ {args[0]}"), color=KeyboardButtonColor.POSITIVE)
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    await message.answer(answer, keyboard=my_keyboard)


@bot.on.message(command=("принять_заказ", 1))
async def my_order(message: Message, args: Tuple[str]):
    await contractor_accept_order(message.from_id, args[0])
    await message.answer("Заказ принят, спасибо!")
    await get_to_default_state(message)


@bot.on.message(text="Принятые Заказы")
async def accepted_orders(message: Message):
    my_orders = database_request(
        f"SELECT order_id FROM public.order WHERE contractor_id IN (SELECT contractor_id FROM public.contractor WHERE contractor_vk_id LIKE '{message.from_id}')")
    my_keyboard = Keyboard(one_time=True, inline=False)
    for element in my_orders:
        my_keyboard.row()
        my_keyboard.add(Text(f"!мой_заказ {element[0]}"))
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()

    await message.answer("меню", keyboard=my_keyboard)


@bot.on.message(text="Сообщение Заказчику")
async def new_content(message: Message):
    my_orders = database_request(
        f"SELECT order_id FROM public.order WHERE contractor_id IN (SELECT contractor_id FROM public.contractor WHERE contractor_vk_id LIKE '{message.from_id}')")
    my_keyboard = Keyboard(one_time=True, inline=False)
    for element in my_orders:
        my_keyboard.row()
        my_keyboard.add(Text(f"!сообщение_заказчику_по_заказу№ {element[0]}"))
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()

    await message.answer("меню", keyboard=my_keyboard)


@bot.on.message(command=("сообщение_заказчику_по_заказу№", 1))
async def add_content(message: Message, args: Tuple[str]):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_data["state"] = "new_order_message_text"
    user_data["order_message_order_id"] = args[0]
    user_data["order_message_text"] = ""
    await message.answer("А теперь напиши своё сообщение и мы доставим его заказчику!", keyboard=DEFAULT_KEYBOARD)


@bot.on.message(text="Отправить Сообщение Заказчику")
async def send_content(message: Message):
    user_data = get_user_data(message.from_id)
    order_id = user_data["order_message_order_id"]
    new_text = user_data["order_message_text"]
    await message.answer("Спасибо!")
    await contractor_send_message(order_id, new_text)
    await get_to_default_state(message)


@bot.on.message(text="Добавить Исполнителя")
async def new_content(message: Message):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_data["state"] = "new_contractor_vk_id"
    await message.answer("Пожалуйста напиши оригинальный VK ID (тот, который цифрами) того, кого хочешь добавить", keyboard=DEFAULT_KEYBOARD)


@bot.on.message(text="Добавить Нового Исполнителя")
async def send_content(message: Message):
    user_data = get_user_data(message.from_id)
    vk_id = user_data["new_contractor_vk_id"]
    await message.answer("Спасибо!")
    await create_new_contractor(vk_id)
    await get_to_default_state(message)


@bot.on.message(text="Добавить Бухгалтера")
async def add_accountant(message: Message):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_data["state"] = "new_accountant_vk_id"
    await message.answer("Пожалуйста напиши оригинальный VK ID (тот, который цифрами) того, кого хочешь добавить", keyboard=DEFAULT_KEYBOARD)


@bot.on.message(text="Добавить Нового Бухгалтера")
async def really_add_accountant(message: Message):
    user_data = get_user_data(message.from_id)
    vk_id = user_data["new_accountant_vk_id"]
    await message.answer("Спасибо!")
    await create_new_accountant(vk_id)
    await get_to_default_state(message)


@bot.on.message(text="Обновить Аккаунт")
async def update_acc_start(message: Message):
    my_orders = database_request(
        f"SELECT order_id FROM public.order WHERE customer_id IN (SELECT customer_id FROM public.customer WHERE customer_vk_id='{message.from_id}')")
    my_keyboard = Keyboard(one_time=True, inline=False)
    for element in my_orders:
        my_keyboard.row()
        my_keyboard.add(Text(f"!обновить_аккаунт {element[0]}"))
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()

    await message.answer("меню", keyboard=my_keyboard)


@bot.on.message(command=("обновить_аккаунт", 1))
async def update_acc(message: Message, args: Tuple[str]):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_data["state"] = "update_account_text"
    user_data["update_account_order_id"] = args[0]
    await message.answer("А теперь напиши данные от своего аккаунта в формате:\nсоциальная_сеть\nЛогин\nПароль\n\nПример:\nВК\n89205101203\nmoi_parol", keyboard=DEFAULT_KEYBOARD)


@bot.on.message(text="Обновить Аккаунт!")
async def update_acc_confirm(message: Message):
    user_data = get_user_data(message.from_id)
    order_id = user_data["update_account_order_id"]
    new_text = user_data["update_account_text"]
    account_data = new_text.splitlines()
    if len(account_data) < 3:
        await message.answer("Неправильный формат данных. Перепроверьте.")
        await get_to_default_state(message)
        return

    await update_account_info(order_id, account_data[0], account_data[1], account_data[2])
    await message.answer("Спасибо! Данные вашего аккаунта обновлены!")
    await get_to_default_state(message)


@bot.on.message(text="Отправить Отчёт")
async def send_report(message: Message):
    my_orders = database_request(
        f"SELECT order_id FROM public.order WHERE contractor_id IN (SELECT contractor_id FROM public.contractor WHERE contractor_vk_id LIKE '{message.from_id}')")
    my_keyboard = Keyboard(one_time=True, inline=False)
    for element in my_orders:
        my_keyboard.row()
        my_keyboard.add(Text(f"!отправить_отчёт {element[0]}"))
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    await message.answer("Меню", keyboard=my_keyboard)


@bot.on.message(command=("отправить_отчёт", 1))
async def send_report_id(message: Message, args: Tuple[str]):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_data["state"] = "new_report_scope"
    user_data["new_report_order_id"] = args[0]
    await message.answer("Напиши охват аудитории", keyboard=DEFAULT_KEYBOARD)


@bot.on.message(text="Отправить Отчёт!")
async def send_report_for_real(message: Message):
    user_data = get_user_data(message.from_id)
    order_id = user_data["new_report_order_id"]
    scope = user_data["new_report_scope"]
    numberpublications = user_data["new_report_numberpublications"]

    if not (scope.isdigit() and numberpublications.isdigit()):
        await message.answer("Все значения должны быть числами. Перепроверьте.")
        await get_to_default_state(message)
        return

    await message.answer("Спасибо! Ваш отчёт отправлен!")
    await create_new_report(order_id, message.from_id, scope, numberpublications)
    await get_to_default_state(message)


@bot.on.message(text="Выписать счёт")
async def send_profit(message: Message):
    my_orders = database_request(
        f"SELECT order_id FROM public.order WHERE order_id NOT IN (SELECT order_id FROM public.profit)")
    my_keyboard = Keyboard(one_time=True, inline=False)
    for element in my_orders:
        my_keyboard.row()
        my_keyboard.add(Text(f"!выписать_счёт {element[0]}"))
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    await message.answer("Меню", keyboard=my_keyboard)


@bot.on.message(command=("выписать_счёт", 1))
async def send_profit_id(message: Message, args: Tuple[str]):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_data["state"] = "new_profit_initialcost"
    user_data["new_profit_order_id"] = args[0]
    user_data["new_profit_initialcost"] = ""
    user_data["new_profit_costmaintenance"] = ""
    user_data["new_profit_totalcost"] = ""
    await message.answer("Напишите начальную цену", keyboard=DEFAULT_KEYBOARD)


@bot.on.message(text="Выписать счёт!")
async def send_profit(message: Message):
    user_data = get_user_data(message.from_id)
    order_id = user_data["new_profit_order_id"]
    initialcost = user_data["new_profit_initialcost"]
    costmaintenance = user_data["new_profit_costmaintenance"]
    totalcost = user_data["new_profit_totalcost"]
    vk_id = message.from_id
    accountant_id = database_request(
        f"SELECT accountant_id FROM public.accountant WHERE accountant_vk_id='{vk_id}'")[0][0]

    await message.answer("Спасибо! Ваш счёт вскоре придёт к заказчику!")
    await create_new_profit(accountant_id, order_id, initialcost, costmaintenance, totalcost)
    await get_to_default_state(message)


@bot.on.message(text="Получить отчёт")
async def get_profits(message: Message):
    my_orders = database_request(f"SELECT order_id FROM public.order")
    my_keyboard = Keyboard(one_time=True, inline=False)
    for element in my_orders:
        my_keyboard.row()
        my_keyboard.add(Text(f"!получить_отчёт_по_заказу№ {element[0]}"))
    my_keyboard.row()
    my_keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    my_keyboard = my_keyboard.get_json()
    await message.answer("Меню", keyboard=my_keyboard)


@bot.on.message(command=("получить_отчёт_по_заказу№", 1))
async def get_profits_id(message: Message, args: Tuple[str]):
    order_id = args[0]
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.add_font('montserat', '', 'font.ttf', True)
    pdf.set_font("montserat", size=14)
    result = database_request(
        f"SELECT * FROM public.report WHERE order_id={order_id} ORDER BY report_startdate ASC")
    for element in result:
        text = f"Дата: {element[3]}\nОхват аудитории: {element[4]}\nКол-во публикаций: {element[5]}"
        text2 = text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(180, 10, txt=text, align='C', border=1)

    pdf.output("temp.pdf")

    uploader = DocMessagesUploader(bot.api)
    attachment = await uploader.upload("temp.pdf", "temp.pdf", peer_id=message.peer_id)
    await message.answer("Вот ваш отчёт!", attachment=attachment)
    await get_to_default_state(message)


@bot.on.message(text="Мои счета")
async def my_profits(message: Message):
    my_orders = database_request(
        f"SELECT order_id, order_subjectarea FROM public.order WHERE customer_id IN (SELECT customer_id FROM public.customer WHERE customer_vk_id='{message.from_id}')")
    my_orders_string = "("
    for element in my_orders:
        my_orders_string += str(element[0])
        my_orders_string += ","
    my_orders_string += "0)"

    result = database_request(
        f"SELECT order_id, profit_totalcost FROM public.profit WHERE order_id IN {my_orders_string}")
    final_answer = "Ваши счета:\n"
    for element in result:
        final_answer += f"[Номер Заказа: {element[0]}]\nСумма к оплате: {element[1]}\n\n"

    await message.answer(final_answer)
    await get_to_default_state(message)


@bot.on.message()
async def message_handler(message: Message):
    user_id = message.from_id
    user_data = get_user_data(user_id)
    user_state = user_data["state"]

    answer = globals()[user_state](user_data, message)
    await message.answer(answer["text"], keyboard=answer["keyboard"])


bot.run_forever()


'''
KEYBOARD_STANDARD = Keyboard(one_time=True, inline=False)
KEYBOARD_STANDARD.add(Text("Привет"), color=KeyboardButtonColor.POSITIVE)
KEYBOARD_STANDARD.add(Text("Button 2"))
KEYBOARD_STANDARD.row()
KEYBOARD_STANDARD.add(Text("Button 3"))
KEYBOARD_STANDARD = KEYBOARD_STANDARD.get_json()



@bot.on.message(text="Привет")
async def hi_handler(message: Message):
    users_info = await bot.api.users.get(message.from_id)
    await message.answer("Привет, {}".format(users_info[0].first_name))

keyboard = KEYBOARD_STANDARD

@bot.on.message()
async def send_keyboard(message):
    await message.answer("Here is your keyboard!", keyboard=keyboard)



'''
