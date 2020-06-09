#  Бот для контролю ціни на криптовалюту
#
#  Alex k 14.05.2020
#
#
#


import telebot
import threading
import re
import random
import shelve
from time import sleep
from pycoingecko import CoinGeckoAPI

cg = CoinGeckoAPI()
bot = telebot.TeleBot('1222486864:AAHgNuUMiUir4s6UFSJc8bHQdat5HeDhPEs')


@bot.message_handler(commands=['start'])
def start(message):
    User.create_user(message.chat.id, message.chat.first_name)
    first_text = f"""
{message.chat.first_name}, Привіт! Тебе вітає криптобот. Я можу:

- Дізнатись про ціну на потрібну тобі криптовалюту
- Повідомлю тебе, коли її вартість буде змінюватись
- Можна вибрати кілька валют та вибрати поріг інформування

Ось кілька корисних команд:
/find обрана крипта - Пошук потрібної криптовалюти
/settings - Налаштування
/remind coin price - Нагадування
    """
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.row('Створити нагадування⏱', 'Налаштування')
    bot.send_message(message.chat.id, first_text, reply_markup=keyboard)


@bot.message_handler(commands=['find'])
def find_current_crypto(message):
    cname = message.text[6:]
    response = check_coin(cname, message)  # coin obj
    if response:
        coin = Coin(response)
        coin_name, currency, price = coin.get_property()
        text = f'Вибрано монету - {coin_name.upper()}\nАктуальна ціна - {price} {currency.upper()}'
        bot.send_message(message.chat.id, text)
    else:
        text = f'На жаль, мені не вдається знайти монету {cname} :(\nСпробуйте в інший раз.'
        bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['remind'])
def notification(message):
    user_input = message.text[8:]
    user_input.replace(' ', '')
    current_coin = ''
    current_price = ''
    for item in user_input:
        if item not in '1234567890':
            current_coin += item
        else:
            current_price += item
    if current_price:
        current_price = int(current_price)
        response = check_coin(current_coin, message)
        if response:
            user = User.get_user(message.chat.id)
            note = user.create_notify(response, current_price, message)
            sync_data(user)
            user.start_notify(note)
            sync_data(user)
        else:
            bot.send_message(message.chat.id, 'Неправильний ввід. Спробуйте ще.')
    else:
        bot.send_message(message.chat.id, 'Ви забули вказати ціну.')


@bot.message_handler(content_types=['text'])
def controller(message):
    if message.text == 'Створити нагадування⏱':
        text = 'Для створення нагадування пропиши:\n/remind "вибрана валюта" "ціна"'
        bot.send_message(message.chat.id, text)
    elif message.text == '/settings' or message.text == 'Налаштування':
        inline_kb = telebot.types.InlineKeyboardMarkup()
        user = User.get_user(message.chat.id, message)
        notifications = user.get_notifications()
        if user.currency == 'uah':
            flag = '🇺🇦'
        else:
            flag = '🇺🇸'
        text = f'Кількість активних нагадувань - {len(notifications)} \nВибрана валюта - {user.currency}{flag}\n' \
               '\nСписок нагадувань:\n'
        notification_list = user.get_notifications()
        if notification_list:
            for item in user.get_notifications():
                text += f'\n🛎Reminder {item.id} : {item.coin_name} - {item.current_price} {item.currency}\n' \
                        f'Актуальна ціна - {item.get_coin_price()} {item.get_coin_currency()}\n\n'
        else:
            text += '\n\n❎Пусто❎'
        inline_kb.row(
            telebot.types.InlineKeyboardButton(text='Видалити ❌', callback_data='Delete' + str(message.chat.id)),
            telebot.types.InlineKeyboardButton(text='Редагувати', callback_data='Edit' + str(message.chat.id))
        )
        bot.send_message(message.chat.id, text, reply_markup=inline_kb)


@bot.callback_query_handler(func=lambda call: True)
def callback(query):
    chat_id = ''.join(re.findall('(\d+)', query.data))
    user = User.get_user(chat_id)
    if 'Edit' in query.data:
        text = 'Вибери валюту'
        inline_kb = telebot.types.InlineKeyboardMarkup()
        inline_kb.row(
            telebot.types.InlineKeyboardButton(text='🇺🇦 UAH', callback_data='uah' + str(chat_id)),
            telebot.types.InlineKeyboardButton(text='🇺🇸 USD', callback_data='usd' + str(chat_id)),
        )
        bot.send_message(chat_id, text, reply_markup=inline_kb)

    elif 'Delete' in query.data:
        text = 'Вибери нагадування яке бажаєш видалити'
        inline_kb = telebot.types.InlineKeyboardMarkup()
        notification_list = user.get_notifications()
        if notification_list:
            for item in notification_list:
                kb_text = f'🛎Reminder {item.id} : {item.coin_name} - {item.current_price} {item.currency}\n'
                query_data = str(item.id) + '|' + str(chat_id) + '|' + 'deleteItem'
                inline_kb.row(
                    telebot.types.InlineKeyboardButton(text=kb_text, callback_data=query_data)
                )
        else:
            text = '<Список порожній>'
        bot.send_message(chat_id, text, reply_markup=inline_kb)

    elif 'deleteItem' in query.data:
        data = query.data.split('|')
        data.pop()
        number_notification = data[0]
        chat_id = data[1]
        user = User.get_user(chat_id)
        notification_list = user.get_notifications()
        if notification_list:
            for item in notification_list:
                if item.get_id() == number_notification:
                    user.remove_notification(item.get_id())
                    bot.send_message(chat_id, 'Done')

    elif 'uah' or 'usd' in query.data:
        new_currency = query.data[:3]
        user.currency = new_currency
        bot.send_message(chat_id, f'Валюту успішно змінено на {new_currency}.')
    sync_data(user)


def check_coin(coin_name, message, current_currency=None):
    """Перевірка наявності виброної крипти"""
    if not current_currency:
        current_currency = User.get_user(message.chat.id).currency
    response = cg.get_price(ids=coin_name, vs_currencies=current_currency)
    if response:
        return response
    else:
        return None


def sync_data(user_obj):
    with shelve.open('users.dat', 'c') as states:
        states[user_obj.user_id] = user_obj


class Coin(object):
    """"Клас для управління вибраною монетою"""

    def __init__(self, params):
        self.coin_name = ''
        self.currency = ''
        self.price = None
        self.update_params(params)

    def __str__(self):
        return self.coin_name + ' ' + self.currency + ' ' + str(self.price)

    def get_property(self):
        prop = (self.coin_name, self.currency, self.price)
        return prop

    def update_params(self, params):
        for key in params.keys():
            self.coin_name = key
            for currency in params[key]:
                self.currency = currency
                self.price = params[key][currency]


class Notification(Coin):
    """Клас для нотифікацій"""

    def __init__(self, params, message, current_price):
        super().__init__(params)
        self.__message = message
        self.id = str(random.randrange(100000))
        self.current_price = current_price
        self.current_currency = User.get_user(message.chat.id).currency
        text = f'Нотифікація N{self.id} створена успішно.'
        bot.send_message(message.chat.id, text)

    def check_price(self):
        self.update_params(check_coin(self.coin_name, self.__message.chat.id, self.current_currency))
        if self.price > self.current_price:
            bot.send_message(self.__message.chat.id, self.__text_notification())
            return True

    def __text_notification(self):
        text = f'\t\tWARNING!!!\n' \
               f'Вартість монети {self.coin_name} перевищила {self.current_price} {self.current_currency} ' \
               f'та становить зараз {self.price}{self.current_currency}'
        return text

    def get_id(self):
        return self.id

    def __str__(self):
        return str(self.id)

    def get_coin_price(self):
        return self.price

    def get_coin_currency(self):
        return self.currency


class User(object):
    """Об'єкт для кожного користувача."""

    def __init__(self, user_id, first_name):
        self.__user_id = user_id
        self.__first_name = first_name
        self.notification_list = dict()
        self.__currency = 'usd'

    def __str__(self):
        return str(self.__user_id)

    def create_notify(self, params, current_price, message):
        new_note = Notification(params, message, current_price)
        note_id = new_note.get_id()
        self.notification_list[note_id] = new_note
        return new_note

    def start_notify(self, note):
        note_id = note.get_id()
        t = MyThread(10, note_id, self.__user_id)
        t.start()

    def get_notifications(self, note_id=None):
        if note_id:
            return self.notification_list[note_id]
        else:
            note_array = []
            for key in self.notification_list.keys():
                note_array.append(self.notification_list[key])
            return note_array

    @property
    def currency(self):
        return self.__currency

    @currency.setter
    def currency(self, new_currency):
        if new_currency:
            self.__currency = new_currency

    @property
    def user_id(self):
        return str(self.__user_id)

    def remove_notification(self, note_id):
        del self.notification_list[note_id]

    @staticmethod
    def get_user(chat_id, message=None):
        with shelve.open('users.dat', 'c') as file:
            try:
                user = file[str(chat_id)]
            except KeyError:
                if message:
                    user_name = message.chat.first_name
                    file[str(chat_id)] = User(chat_id, user_name)
                    file.sync()
                    return file[str(chat_id)]
            else:
                return user

    @staticmethod
    def create_user(user_id, user_name):
        with shelve.open('users.dat', 'c') as file:
            if str(user_id) not in file:
                file[str(user_id)] = User(user_id, user_name)


class MyThread(threading.Thread):
    def __init__(self, interval, note_id, user_id):
        threading.Thread.__init__(self)
        self.interval = interval
        self.note_id = note_id
        self.user_id = user_id

    def run(self):
        while True:
            user = User.get_user(self.user_id)
            note = user.get_notifications(self.note_id)
            check = note.check_price()
            sync_data(user)
            if check:
                user.remove_notification(self.note_id)
                sync_data(user)
                break
            sleep(self.interval)


if __name__ == '__main__':
    print('Start')
    with shelve.open('users.dat') as users:
        for user_id in users:
            for reminder in users[user_id].get_notifications():
                if reminder:
                    users[user_id].start_notify(reminder)
    bot.infinity_polling(True)