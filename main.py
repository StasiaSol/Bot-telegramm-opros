import telebot
from telebot import formatting
from telebot.types import Message as m, ReplyKeyboardMarkup, ReplyKeyboardRemove
from loguru import logger
from setting import token
from bd import *

logger.remove()
logger.add("log_opros.log", level="DEBUG", compression='zip', rotation='1 hour', retention='1 week')
logger.add("warn.log", level="WARNING", delay=True, rotation='1 hour')
bot = telebot.TeleBot(token)
logger.success("Экземпляр бота создан")
temp = {}


@bot.message_handler(['start'])
def start(msg: m):
    clear = ReplyKeyboardRemove()
    logger.info(f"Пользователь {msg.chat.id} нажал /start")
    old = db.s.get(Users, msg.chat.id)
    if not old:        
        user = Users(id=msg.chat.id, name=msg.from_user.full_name, answers=None, is_admin=False)
        db.merge(user)
        db.commit()
    bot.send_message(msg.chat.id, "Пройти опрос — /lets_go", reply_markup=clear)

@bot.message_handler(['lets_go'])
def quest(msg: m):
    
    # data = db.s.get(Manage, 1)
    # if data: 
    #     logger.debug(f"Прочитали вопросы из manage: {data.questions}")
    #     data = ", ".join(data.questions)
    #     bot.send_message(msg.chat.id, "Вопросы: + " + data, reply_markup=clear) 
    # else:
    #     logger.warning(f"Юзер {msg.chat.id} вызвал вопросы, но вопросов в таблице нет")
    #     bot.send_message(msg.chat.id, "Сейчас вопросов нет.", reply_markup=clear)  
    questions = check_questions()
    ids = []
    keyboard = ReplyKeyboardMarkup(True, True)
    for q in questions:
        ids.append(q[0])
        keyboard.row(str(q[0]))
    text = "Выберите опрос: \n"
    for q in questions:
        text += formatting.hbold(f"Номер {q[0]}. {q[1]} \n")
    bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=keyboard)
    bot.register_next_step_handler(msg, first_question, ids)
    
def first_question(msg: m, ids: list):
    clear = ReplyKeyboardRemove()
    if not msg.text.isnumeric():
        logger.warning(f"Юзер {msg.chat.id} ввёл неверный номер списка")
        bot.send_message(msg.chat.id, "Введён неправильный номер списка")
        start(msg)
        return
    if int(msg.text) not in ids:
        logger.warning(f"Юзер {msg.chat.id} ввёл неверный номер списка")
        bot.send_message(msg.chat.id, "Введён неправильный номер списка")
        start(msg)
        return
    temp[msg.chat.id] = {'list': int(msg.text),
                        'queue': 0,
                        'answers': []}
    logger.info(f"Клиент {msg.chat.id} инициализировал переменную - {temp[msg.chat.id] }")
    questions = db.s.get(Manage, int(msg.text)).questions
    bot.send_message(msg.chat.id, questions[0],reply_markup=clear)
    bot.register_next_step_handler(msg, next_question, questions)
    
@logger.catch
def next_question(msg: m, questions):
    global temp
    clear = ReplyKeyboardRemove()
    temp[msg.chat.id]['answers'].append(msg.text)
    logger.info(f"Юзер {msg.chat.id} ответил на вопрос №{temp[msg.chat.id]['queue']+1} "
                f"списка №{temp[msg.chat.id]['list']}")
    if temp[msg.chat.id]['queue'] == len(questions) - 1:
        bot.send_message(msg.chat.id, "Спасибо за ответы!", reply_markup=clear)
        logger.success(f"Юзер {msg.chat.id} завершил опрос!")
        save_client(msg)
        return
    temp[msg.chat.id]['queue'] += 1
    question = questions[temp[msg.chat.id]['queue']]
    bot.send_message(msg.chat.id, question, reply_markup=clear)
    bot.register_next_step_handler(msg, next_question, questions)
    
def save_client(msg: m):
    global temp 
    
    user = db.s.get(Users, msg.chat.id)
    if user.answers is None:
        answers = [temp[msg.chat.id]['answers']]
    else:
        answers = user.answers
        answers.append(temp[msg.chat.id]['answers'])
    db.s.query(Users).filter_by(id=msg.chat.id).update({"answers": answers})
    db.commit()
    temp = {}
        
# @bot.message_handler(['write'])
# def write(msg: m):    
#     data = Manage(id=1,short_name= 'Что-то', questions=["Ты кто?", "Кто я?"])
#     db.merge(data)
#     data = Manage(id=2, short_name="Крутые вопросы", questions=["Ты крут?", "Докажи?"])
#     db.merge(data)
#     db.commit()
#     logger.success(f"Админ {msg.chat.id} записал список вопросов с id={data.id}")
    
@bot.message_handler(['admin'])
def admin_panel(msg: m):
    user = db.s.get(Users, msg.chat.id)
    if user.is_admin:
        logger.info(f"Админ {msg.chat.id} зашёл в меню администратора")
        admin_panel(msg)
    else:
        logger.warning(f"Юзер {msg.chat.id} стучится в меню администратора")
        start(msg)
        
def admin_panel(msg: m):
    keyboard = ReplyKeyboardMarkup(True)
    keyboard.row("Посмотреть списки вопросов", "Удалить список вопросов")
    keyboard.row("Добавить список вопросов", 'Посмотреть ответы пользователей')
    bot.send_message(msg.chat.id, "Выбери действие:", reply_markup=keyboard)
    bot.register_next_step_handler(msg, admin_panel_handler)
    
def admin_panel_handler(msg: m):
    if msg.text.startswith("Посмотреть списки"):
        questions = check_questions()
        bot.send_message(msg.chat.id, questions_format(questions), parse_mode="HTML")
        admin_panel(msg)
    elif msg.text.startswith("Удалить"):
        delete_questions(msg)
    elif msg.text.startswith("Добавить"):
        ask_question(msg)
    elif msg.text.startswith("Посмотреть ответы"):
        answers(msg)
    else:
        admin_panel(msg)

@logger.catch        
def check_questions():
    questions = []
    data = db.s.query(Manage)
    for d in data:
        questions.append([d.id,d.short_name, d.questions])
    logger.success("Посмотрели вопросы из БД")
    return questions

@logger.catch()
def questions_format(questions: list):
    text = "Списки вопросов: \n\n"
    for q_list in questions:
        text += f"Список №{q_list[0]}\n"
        text += formatting.hbold(q_list[1]) + "\n"
        text += f"Вопросы: \n"
        for n, q in enumerate(q_list[2]):
            text += f"Вопрос №{n+1}. {q}\n"
            text += "\n"
    logger.info("Строка отформатирована успешно")
    return text

@logger.catch
def delete_questions(msg: m):
    questions = check_questions()
    ids = []
    keyboard = ReplyKeyboardMarkup(True, True)
    for q in questions:
        ids.append(q[0])
        keyboard.row(str(q[0]))
    text = "Выберите список для удаления: \n"
    for q in questions:
        text += formatting.hbold(f"Номер {q[0]}. {q[1]} \n") 
    bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=keyboard)
    bot.register_next_step_handler(msg, delete_questions_handler, ids) 
    
@logger.catch
def delete_questions_handler(msg: m, ids: list):      
    if not msg.text.isnumeric():
        logger.warning(f"Админ {msg.chat.id} ввёл неверный номер списка")
        bot.send_message(msg.chat.id, "Введён неправильный номер списка")
        admin_panel(msg)
        return
    keyboard = ReplyKeyboardMarkup(True, True)
    keyboard.row("я передумал")
    keyboard.row("УДАЛИТЬ")
    bot.send_message(msg.chat.id, f"Вы точно хотите удалить список №{msg.text}?", reply_markup=keyboard)
    bot.register_next_step_handler(msg, delete, int(msg.text))
    
@logger.catch
def delete(msg: m, num: int):
    if msg.text == "УДАЛИТЬ":
        db.s.query(Manage).filter(Manage.id == num).delete()
        db.commit()
        bot.send_message(msg.chat.id, f"Список №{num} успешно удалён!")
        logger.success(f"Список №{num} успешно удалён!")
    else:
        bot.send_message(msg.chat.id, "Удаление отменено.")
    admin_panel(msg)
    
@logger.catch
def ask_question(msg: m):
    global temp
    clear = ReplyKeyboardRemove
    temp[msg.chat.id] = []
    bot.send_message(msg.chat.id, "Введи первый вопрос:", reply_markup=clear)
    bot.register_next_step_handler(msg, ask_next_question)

@logger.catch
def ask_next_question(msg: m):
    global temp
    if msg.text != "всё":
        temp[msg.chat.id].append(msg.text)
        bot.send_message(msg.chat.id, "Введи следующий вопрос:")
        bot.register_next_step_handler(msg, ask_next_question)
    else:
        logger.info(f"Админ {msg.chat.id} создал новый список")
        bot.send_message(msg.chat.id, "Введи короткое имя:")
        bot.register_next_step_handler(msg, add_new_list)
    
    
@logger.catch
def add_new_list(msg: m):
    questions = check_questions()
    ids = []
    for q in questions:
        ids.append(q[0])
    num = max(ids) + 1
    new = Manage(id=num, short_name=msg.text,questions=temp[msg.chat.id])
    db.merge(new)
    db.commit()
    logger.success(f"Админ {msg.chat.id} записал новый список №{num}")
    bot.send_message(msg.chat.id, "Список успешно записан")
    admin_panel(msg)
    
@logger.catch()
def answers(msg):
    # Извлекаем всех пользователей и их ответы
    users = db.s.query(Users).all()
    
    # Проверка, есть ли вообще ответы у пользователей
    if not users:
        bot.send_message(msg.chat.id, "Пока нет ответов от пользователей.")
        return
    
    # Формируем текст для отправки в бот
    text = "Ответы пользователей:\n\n"
    for user in users:
        text += f"Пользователь {user.name} (ID: {user.id}):\n"
        
        if not user.answers:
            text += "  - Нет ответов\n\n"
            continue
        
        for i, answers_set in enumerate(user.answers, start=1):
            text += f"  Ответы на опрос №{i}:\n"
            for n, answer in enumerate(answers_set, start=1):
                text += f"    Вопрос {n}: {answer}\n"
            text += "\n"
    
    # Отправляем ответы в чат
    bot.send_message(msg.chat.id, text, parse_mode="HTML")
    logger.info(f'Администратор {msg.chat.id} вывел себе на экран все ответы на вопросы из БД')
    admin_panel(msg)
    

    
bot.infinity_polling()