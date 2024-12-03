
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from config import TOKEN, API_KEY
from benzinga import news_data
from keyboards import keyb

bot = Bot(token=TOKEN)
dp = Dispatcher()

news = news_data.News(API_KEY)
DB_FILE = "news_bot.db"
logging.basicConfig(level=logging.DEBUG)


def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_news (
                chat_id INTEGER,
                news_id TEXT,
                PRIMARY KEY (chat_id, news_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_keywords (
                chat_id INTEGER,
                keyword TEXT,
                PRIMARY KEY (chat_id, keyword)
            )
        """)
        conn.commit()
        conn.close()
        logging.info("База данных и таблицы инициализированы успешно.")
    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {e}")






async def is_news_processed(chat_id, news_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""SELECT 1 FROM processed_news WHERE chat_id = ? AND news_id = ?""", (chat_id, news_id))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logging.error(f"Ошибка при проверке новостей: {e}")
        return False


async def save_news_to_db(chat_id, news_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""INSERT OR IGNORE INTO processed_news (chat_id, news_id) VALUES (?, ?)""", (chat_id, news_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Ошибка при сохранении новости в БД: {e}")

async def save_user_keywords(chat_id, keywords):
    if not keywords:
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for keyword in keywords:
            if keyword.strip():  
                cursor.execute("""
                    INSERT OR IGNORE INTO user_keywords (chat_id, keyword)
                    VALUES (?, ?)
                """, (chat_id, keyword.strip().lower())) 
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Ошибка при сохранении ключевых слов в БД: {e}")




async def get_user_keywords(chat_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT keyword FROM user_keywords WHERE chat_id = ?
        """, (chat_id,))
        keywords = [row[0] for row in cursor.fetchall()]
        conn.close()
        return [keyword.lower() for keyword in keywords]  # Приводим к нижнему регистру
    except Exception as e:
        logging.error(f"Ошибка при получении ключевых слов пользователя: {e}")
        return []

def transform_data(raw_data):
    try:
        return [
            {
                'title': story.get('title'),
                'url': story.get('url'),
                'news_id': story.get('url'),
            }
            for story in raw_data
        ]
    except Exception as e:
        logging.error(f"Ошибка при преобразовании данных: {e}")
        return []

async def check_news(chat_id):
    try:
        stories = news.news()
        if isinstance(stories, list):
            transformed_data = transform_data(stories)
            user_keywords = await get_user_keywords(chat_id)

            for story in transformed_data:
                title = story.get("title")
                url = story.get("url")
                news_id = story.get("news_id")

                if not await is_news_processed(chat_id, news_id):
                    # Проверка на ключевые слова пользователя
                    if any(keyword.lower() in title.lower() for keyword in user_keywords):
                        text = f"🚀 Новая новость: {title}\nСсылка: {url}"
                        await bot.send_message(chat_id=chat_id, text=text)
                        await save_news_to_db(chat_id, news_id)
        else:
            logging.error("Полученные данные не соответствуют ожидаемому формату.")
    except Exception as e:
        logging.error(f"Ошибка при получении новостей: {e}")


async def news_monitoring_task(chat_id):
    while True:
        await check_news(chat_id)
        await asyncio.sleep(60)  





# Создание состояния
class KeywordState(StatesGroup):
    waiting_for_keyword = State()
    waiting_for_keyword_removal = State()
    searching_news = State()  
    managing_keywords = State() 
    viewing_keywords = State()  # Просмотр ключевых слов
    waiting_for_confirmation = State()





@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    chat_id = message.chat.id

    # Приветственное сообщение
    await message.answer(
        """
🚀Добро пожаловать!  
Я помогу вам отслеживать новости по ключевым словам. Выберите команду, чтобы начать:

🔹 /start - Показать это приветственное сообщение.✨  
🔹 /add_keywords - Начать добавление новых ключевых слов.➕  
🔹 /view_keywords - Просмотреть все добавленные ключевые слова.👀  
🔹 /remove_keyword - Удалить ключевое слово.❌  
🔹 /done - Завершить любой процесс работы с ключевыми словами.✅  
🔹 /search_news - Начать поиск новостей с текущими ключевыми словами.🔍  
🔹 /stop_searching_news - Завершить процесс поиска новостей.⛔  
        """, reply_markup=keyb
    )
    await state.clear() 






@dp.message(Command("view_keywords"))
async def view_keywords(message: Message, state: FSMContext):
    chat_id = message.chat.id

    # Получаем текущее состояние
    current_state = await state.get_state()

    if current_state in [KeywordState.waiting_for_keyword.state, KeywordState.waiting_for_keyword_removal.state, KeywordState.searching_news.state]:
        await message.answer("⚠️ Вы не можете просматривать ключевые слова, пока находитесь в процессе, добавления, удаления ключевых слов или поиска новостей.")
        return

    await state.set_state(KeywordState.viewing_keywords)

    user_keywords = await get_user_keywords(chat_id)
    
    if user_keywords:
        await message.answer(f"🔑 Ваши ключевые слова: {', '.join(user_keywords)}")
    else:
        await message.answer("❗ У вас нет добавленных ключевых слов. Используйте команду **/add_keywords** для их добавления.")

    await state.clear()






@dp.message(Command("add_keywords"))
async def add_keywords(message: Message, state: FSMContext):
    chat_id = message.chat.id
    
    # Получаем текущее состояние
    current_state = await state.get_state()
    logging.info(f"Текущее состояние: {current_state}")

    if current_state == KeywordState.searching_news.state:
        await message.answer("⚠️ Вы не можете добавлять ключевые слова, пока ищете новости.")
        return
    
    if current_state == KeywordState.viewing_keywords.state:
        await message.answer("⚠️ Вы не можете добавлять ключевые слова, пока просматриваете их.")
        return

    # Проверяем, что не находимся в процессе добавления/удаления ключевых слов
    if current_state in [KeywordState.waiting_for_keyword, KeywordState.waiting_for_keyword_removal]:
        await message.answer("⚠️ Вы уже находитесь в процессе добавления или удаления ключевых слов.")
        return

    # Переход в состояние добавления ключевых слов
    await message.answer("✏️ Введите новые ключевые слова для добавления. Каждое слово пишите отдельно как новое сообщение.")
    await state.set_state(KeywordState.waiting_for_keyword)


@dp.message(StateFilter(KeywordState.waiting_for_keyword))
async def handle_keywords_addition(message: Message, state: FSMContext):
    chat_id = message.chat.id

    # Игнорируем команды, не относящиеся к добавлению ключевых слов
    if message.text.startswith("/"):
        # Обрабатываем команду завершения процесса добавления
        if message.text == "/done":
            await state.clear()
            await message.answer("✅ Процесс добавления ключевых слов завершён. Вы можете использовать другие команды.")
            return
        
        # Игнорируем команду /view_keywords во время добавления
        elif message.text == "/view_keywords":
            await message.answer("❌ Вы не можете просматривать ключевые слова во время добавления. Завершите процесс добавления командой /done.")
            return
        
        # Игнорируем все остальные команды
        await message.answer("⚠️ В процессе добавления ключевых слов другие команды не доступны. Чтобы завершить, используйте команду /done.")
        return

    # Добавляем ключевые слова в список (основная логика добавления)
    keyword = message.text.strip().lower()
    if keyword:
        await save_user_keywords(chat_id, [keyword])
        await message.answer(f"✅ Ключевое слово '{keyword}' успешно добавлено.")
    else:
        await message.answer("❌ Пожалуйста, введите действительное ключевое слово для добавления.")






@dp.message(Command("remove_keyword"))
async def remove_keyword(message: Message, state: FSMContext):
    chat_id = message.chat.id
    current_state = await state.get_state()
    logging.info(f"Текущее состояние: {current_state}")
    if current_state == KeywordState.searching_news.state:
        await message.answer("❌ Вы не можете удалять ключевые слова во время поиска новостей.")
        return
    if current_state == KeywordState.viewing_keywords.state:
        await message.answer("❌ Вы не можете удалять ключевые слова, пока просматриваете их.")
        return
    
    if current_state == KeywordState.waiting_for_keyword.state:
        await message.answer("❌ Вы не можете удалять ключевые слова, пока добавляете их.")
        return
    user_keywords = await get_user_keywords(chat_id)
    if not user_keywords:
        await message.answer("❌ У вас нет добавленных ключевых слов.")
        return
    await message.answer(f"🔑 Ваши ключевые слова: {', '.join(user_keywords)}.\nВведите ключевое слово для удаления.")
    await state.set_state(KeywordState.waiting_for_keyword_removal)


@dp.message(StateFilter(KeywordState.waiting_for_keyword_removal))
async def handle_keyword_removal(message: Message, state: FSMContext):
    chat_id = message.chat.id
    if message.text.startswith("/"):
        # Обрабатываем команды завершения процесса удаления
        if message.text == "/done":
            await state.clear()
            await message.answer("✅ Процесс удаления ключевых слов завершён. Вы можете использовать другие команды.")
            return
        else:
            await message.answer("⚠️ В процессе удаления ключевых слов другие команды не доступны. Чтобы завершить, используйте команду /done.")
            return
    keyword_to_remove = message.text.strip().lower()
    user_keywords = await get_user_keywords(chat_id)
    if keyword_to_remove in user_keywords:
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM user_keywords WHERE chat_id = ? AND keyword = ?",
                    (chat_id, keyword_to_remove)
                )
                conn.commit()
            user_keywords = await get_user_keywords(chat_id)
            await message.answer(f"✅ Ключевое слово '{keyword_to_remove}' успешно удалено.")
            await message.answer(f"🔑 Ваши ключевые слова: {', '.join(user_keywords)}.\nВведите ключевое слово для удаления.")
            await message.answer(f"Для завершения процесса удаления ключевых слов введите команду /done")
            
        except sqlite3.Error as e:
            logging.error(f"Ошибка при удалении ключевого слова: {e}")
            await message.answer("❌ Произошла ошибка при удалении ключевого слова.")
    else:
        await message.answer(f"❌ Ключевое слово '{keyword_to_remove}' не найдено в вашем списке. Попробуйте снова.")
        await message.answer(f"🔑 Ваши ключевые слова: {', '.join(user_keywords)}.\nВведите ключевое слово для удаления.")
        await message.answer(f"Для завершения процесса удаления ключевых слов введите команду /done")





@dp.message(Command("done"))
async def done_keywords(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info(f"Текущее состояние: {current_state}")

    if current_state == KeywordState.searching_news.state:
        await message.answer("⚠️ Вы не можете завершить процесс, так как находитесь в процессе поиска новостей.")
        return
    
    # Проверяем текущее состояние и завершаем процесс
    if current_state in [
        KeywordState.waiting_for_keyword,
        KeywordState.waiting_for_keyword_removal,
        KeywordState.managing_keywords,
    ]:
        await message.answer("✅ Вы завершили работу с ключевыми словами.")
        await state.clear()
        await message.answer("Теперь вы можете воспользоваться другими командами для управления ключевыми словами.")

    else:
        await message.answer("❗ Вы не находитесь в процессе добавления или удаления ключевых слов.")






@dp.message(Command("search_news"))
async def search_news(message: Message, state: FSMContext):
    chat_id = message.chat.id

    # Получаем ключевые слова пользователя
    user_keywords = await get_user_keywords(chat_id)

    if not user_keywords:
        await message.answer("У вас нет добавленных ключевых слов. Используйте команду /start для их добавления.")
        return

    # Проверяем текущее состояние FSM
    current_state = await state.get_state()
    logging.info(f"Текущее состояние: {current_state}")

    if current_state == KeywordState.searching_news.state:
        await message.answer("Вы уже в процессе поиска новостей.")
        return

    if current_state in (KeywordState.waiting_for_keyword.state, KeywordState.waiting_for_keyword_removal.state):
        await state.clear()
        await message.answer("Предыдущее состояние завершено. Начинаем поиск новостей.")

    # Сообщаем пользователю, что начался поиск новостей
    await message.answer(f"Поиск новостей с ключевыми словами: {', '.join(user_keywords)}")
    await state.set_state(KeywordState.searching_news)

    # Запускаем проверку новостей
    await check_news(chat_id)  # Здесь вызывается ваша функция для проверки новостей
    await news_monitoring_task(chat_id)  # Начинаем мониторинг новостей


@dp.message(Command("stop_searching_news"))
async def stop_searching_news(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    current_state = await state.get_state()
    logging.info(f"Текущее состояние: {current_state}")

    # Проверяем, что пользователь в процессе поиска новостей
    if current_state == KeywordState.searching_news.state:
        await message.answer("Вы уверены, что хотите приостановить поиск новостей? Ответьте 'да' или 'нет'.")
        # Устанавливаем временное состояние для ожидания ответа
        await state.set_state(KeywordState.waiting_for_confirmation)
    else:
        await message.answer("Вы не находитесь в процессе поиска новостей.")


@dp.message(StateFilter(KeywordState.waiting_for_confirmation))
async def handle_confirmation(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    confirmation = message.text.lower()

    if confirmation == "да":
        # Приостанавливаем поиск новостей
        await state.set_state(KeywordState.managing_keywords)
        await message.answer("Поиск новостей приостановлен. Теперь вы можете редактировать ключевые слова.")
        # Здесь можно добавить код для остановки асинхронных задач мониторинга новостей, если они есть
    elif confirmation == "нет":
        # Возвращаемся к поиску новостей
        await message.answer("Поиск новостей продолжается.")
    else:
        # Обрабатываем неправильный ввод
        await message.answer("Пожалуйста, ответьте 'да' или 'нет'.")

    # Сбрасываем состояние ожидания
    await state.clear()


@dp.message(StateFilter(KeywordState.searching_news))
async def handle_commands_in_searching_news(message: types.Message, state: FSMContext):
    # Проверяем, что команда не является 'stop_searching_news'
    if message.text.lower() != "/stop_searching_news":
        await message.answer(
            "Вы находитесь в процессе поиска новостей. Пока не завершите поиск, доступны только команды /stop_searching_news."
        )
        return
    else:
        # Если команда правильная (stop_searching_news), обрабатываем её
        await message.answer("Поиск новостей будет приостановлен.")
        await state.set_state(KeywordState.managing_keywords)  # Переходим в состояние редактирования ключевых слов
        await message.answer("Теперь вы можете редактировать ключевые слова.")







@dp.message(Command("help"))
async def help_command(message: Message):
    help_text = """
💡Команды бота:

🔹 /start - Показать это приветственное сообщение.✨  
🔹 /add_keywords - Начать добавление новых ключевых слов.➕  
🔹 /view_keywords - Просмотреть все добавленные ключевые слова.👀  
🔹 /remove_keyword - Удалить ключевое слово.❌  
🔹 /done - Завершить любой процесс работы с ключевыми словами.✅  
🔹 /search_news - Начать поиск новостей с текущими ключевыми словами.🔍  
🔹 /stop_searching_news - Завершить процесс поиска новостей.⛔  
    """
    await message.answer(help_text)






# Основная функция
async def main():
    init_db()  # Инициализация базы данных
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Программа завершена.")

