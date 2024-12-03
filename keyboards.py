from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

keyb = ReplyKeyboardMarkup(keyboard=[
  [KeyboardButton(text="/add_keywords"),KeyboardButton(text="/remove_keyword")],
  [KeyboardButton(text="/view_keywords"),KeyboardButton(text="/done")],
  [KeyboardButton(text="/search_news"),KeyboardButton(text="/stop_searching_news")],
],
        
                            input_field_placeholder="Выберите пункт меню")

