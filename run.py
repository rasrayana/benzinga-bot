
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from config import TOKEN
from benzinga import news_data

bot = Bot(token=TOKEN)
dp = Dispatcher()  

KEYWORDS = ["stock", "market", "crypto", "tesla", "trump", "trump's", "elon"]
API_KEY = '570cd36541c84aec95e4017cd6ca6a0e'
news = news_data.News(API_KEY)
processed_news = set()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    chat_id = message.chat.id
    await message.answer("🚀Бот запущен! Смотрим новости...Проверка идет каждую минуту")
    asyncio.create_task(news_monitoring_task(chat_id))


def transform_data(raw_data):
    try:
        transformed_data = []
        
        for story in raw_data:
            transformed_story = {
                'title': story.get('title'),
                'url': story.get('url'),
                'news_id': story.get('url'),
            }
            transformed_data.append(transformed_story)
        
        return transformed_data
    except Exception as e:
        logging.error("Ошибка при преобразовании данных: %s", e)
        return None


async def check_news(chat_id):
    try:
        stories = news.news()
        # logging.info("API Response: %s", stories)

        if isinstance(stories, list):
            transformed_data = transform_data(stories)
            if transformed_data:
                for story in transformed_data:
                    title = story.get("title")
                    url = story.get("url")
                    news_id = story.get('news_id')  

        
                    if news_id not in processed_news:
                        if any(keyword.lower() in title.lower() for keyword in KEYWORDS):
                            text = f"🚀 Новая новость: {title}\nСсылка: {url}"
                            await bot.send_message(chat_id=chat_id, text=text)
                            processed_news.add(news_id)  
        else:
            logging.error("Полученные данные не соответствуют ожидаемому формату.")          
    except Exception as e:
        logging.error("Ошибка при получении новостей: %s", e)



async def news_monitoring_task(chat_id):
    while True:
        await check_news(chat_id)
        await asyncio.sleep(60)  



async def main():
  await dp.start_polling(bot)


if __name__ == '__main__':
  logging.basicConfig(level=logging.CRITICAL) 
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print('Exit')   