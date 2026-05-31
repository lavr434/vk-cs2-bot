import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.exceptions import ApiError
import time
import re
import json
import os
import csv
import random
import threading
from datetime import datetime

# ========== ТВОЙ ТОКЕН ==========
ACCESS_TOKEN = "vk1.a.OQkKuGG9gC_uWLMxBKB5COrERd4RYfkSN2k8DMETR4NtD2urbTzRvCsAwoVAgNjDRwrzoLqovaq4pOTxtp-p3UZKVmpESwbffQXC1pLI9IKaHKIMGMODIugvNk83C68eQj8CYVZE7AsgBDv4suC3arUSpBT3zCAaDShSgA-TuMKT7-8Q574nSgsncWESlFrv4oqGLzA6NtR442WumV4Nhg"

# ========== НАСТРОЙКИ ПОИСКА ГРУПП ==========
SEARCH_KEYWORDS = ["халява cs2", "скины cs2", "cs2 халява", "бесплатные скины cs2"]  # слова для поиска
GROUPS_FILE = "groups_auto.json"   # файл для хранения найденных групп
SEARCH_EVERY_HOURS = 24            # раз в сутки обновлять список групп

# ========== ОСТАЛЬНЫЕ НАСТРОЙКИ (комментарии, ответы, задержки) ==========
KEYWORDS = ["халява cs2", "скины cs2", "бесплатные кейсы", "раздача скинов"]
REPLY_TRIGGERS = ["где халява", "как получить скины", "скинь ссылку", "150 рублей"]
COMMENTS_LIST = [
    "Ребята, кто хочет получить 150 рублей на скины без депозита, напишите мне. Я сам проверил, вывел 1000.",
    "Сайт дает 150 рублей просто за регистрацию. Без вложений, я выводил. Кому интересно, пишите в личку.",
    "Реально рабочий способ получить 150 рублей на кейсы. Я уже вывел 1000. Напишите мне, поделюсь ссылкой."
]
REPLY_COMMENTS_LIST = [
    "Напиши мне в личку, я расскажу, где получить 150 рублей на скины без депозита.",
    "Я нашел способ получить 150 рублей на скины. Напиши в ЛС, поделюсь подробностями.",
    "Лови инструкцию в личных сообщениях. Там реально дают 150 рублей просто так."
]
SECOND_MSG_LIST = [
    "Отлично! Вот ссылка: https://long-voyage.com/?i=925084 Заходишь в раздел бонусы и выполняешь условия для получения 150 рублей без депозита.",
    "Конечно, держи ссылку: https://long-voyage.com/?i=925084 После регистрации получишь 150 бонусов. Без вложений."
]

DELAY_BEFORE_SECOND = 5 * 60
MIN_COMMENT_DELAY = 300       # 5 минут между успешными комментариями
MAX_COMMENT_DELAY = 600
MIN_REPLY_DELAY = 120
MAX_REPLY_DELAY = 300

# ========== ФАЙЛЫ ДЛЯ ЛОГИРОВАНИЯ ==========
POSTS_LOG = "posted_comments.json"
REPLIES_LOG = "comment_replies.json"
SECOND_SENT_LOG = "second_sent.json"
REPORT_FILE = "activity_report.csv"

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def init_report():
    if not os.path.exists(REPORT_FILE):
        with open(REPORT_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(['user_id', 'action', 'target', 'time', 'status'])

def log_action(user_id, action, target, status):
    with open(REPORT_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, action, target, datetime.now().isoformat(), status])

def is_positive(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    negative_words = ['нет', 'не', 'не надо', 'не интересно', 'не буду', 'не приду']
    for word in negative_words:
        if word in text:
            return False
    positive_words = ['да', 'ага', 'конечно', 'скинь', 'давай', 'гоу', 'хорошо', 'ок', 'жду', 'ссылку']
    for word in positive_words:
        if word in text:
            return True
    return False

def send_message(vk_session, user_id, message):
    vk = vk_session.get_api()
    while True:
        try:
            vk.messages.send(user_id=int(user_id), message=message, random_id=random.randint(1, 2**31))
            return True
        except ApiError as e:
            if 'Captcha needed' in str(e):
                print(f"\n!!! КАПЧА для {user_id}. Открой {e.captcha_img}")
                captcha_key = input("Введите код: ")
                try:
                    vk.messages.send(user_id=int(user_id), message=message, random_id=random.randint(1, 2**31),
                                    captcha_sid=e.captcha_sid, captcha_key=captcha_key)
                    return True
                except:
                    print("Неверный код, повтор через 30 сек")
                    time.sleep(30)
            elif 'Permission denied' in str(e):
                print(f"Нет прав к {user_id}. Пропускаем.")
                return False
            else:
                print(f"Ошибка: {e}. Повтор через 60 сек.")
                time.sleep(60)
        except Exception as other:
            print(f"Ошибка: {other}. Повтор через 30 сек.")
            time.sleep(30)

def post_comment(vk_session, owner_id, post_id, text):
    vk = vk_session.get_api()
    try:
        vk.wall.createComment(owner_id=owner_id, post_id=post_id, message=text)
        return True
    except ApiError as e:
        if 'Captcha needed' in str(e):
            print(f"Капча при комментировании {post_id}: {e.captcha_img}")
            captcha_key = input("Код: ")
            try:
                vk.wall.createComment(owner_id=owner_id, post_id=post_id, message=text,
                                     captcha_sid=e.captcha_sid, captcha_key=captcha_key)
                return True
            except:
                return False
        else:
            print(f"Ошибка комментирования: {e}")
            return False

def reply_to_comment(vk_session, owner_id, post_id, comment_id, text):
    vk = vk_session.get_api()
    try:
        vk.wall.createComment(owner_id=owner_id, post_id=post_id, message=text, reply_to_comment=comment_id)
        return True
    except ApiError as e:
        if 'Captcha needed' in str(e):
            print(f"Капча при ответе {comment_id}")
            captcha_key = input("Код: ")
            try:
                vk.wall.createComment(owner_id=owner_id, post_id=post_id, message=text,
                                     reply_to_comment=comment_id, captcha_sid=e.captcha_sid, captcha_key=captcha_key)
                return True
            except:
                return False
        else:
            print(f"Ошибка ответа: {e}")
            return False

# ========== АВТОМАТИЧЕСКИЙ ПОИСК ГРУПП ==========
def find_groups(vk_session):
    """Ищет группы по ключевым словам, сохраняет в JSON, обновляет раз в сутки."""
    if os.path.exists(GROUPS_FILE):
        # Проверяем, когда последний раз обновляли
        mod_time = os.path.getmtime(GROUPS_FILE)
        if time.time() - mod_time < SEARCH_EVERY_HOURS * 3600:
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
                groups = json.load(f)
            print(f"Загружено {len(groups)} групп из кэша (последнее обновление < {SEARCH_EVERY_HOURS} ч.)")
            return groups
    vk = vk_session.get_api()
    found_ids = set()
    for kw in SEARCH_KEYWORDS:
        try:
            response = vk.groups.search(q=kw, type='group', count=200, sort=0)  # sort=0 по популярности
            for item in response['items']:
                group_id = -item['id']   # для API нужен минус
                found_ids.add(group_id)
            print(f"По запросу '{kw}' найдено {len(response['items'])} групп")
            time.sleep(0.5)
        except Exception as e:
            print(f"Ошибка поиска групп по '{kw}': {e}")
    groups = list(found_ids)
    with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(groups, f, indent=2)
    print(f"Всего уникальных групп найдено: {len(groups)}")
    return groups

# ========== ПОТОК 1: КОММЕНТИРОВАНИЕ ПОСТОВ (без паузы после ошибок) ==========
def comment_posts_worker(vk_session, publics, stop_event):
    vk = vk_session.get_api()
    posted = load_json(POSTS_LOG)
    while not stop_event.is_set():
        any_success = False
        for pub in publics:
            if stop_event.is_set():
                break
            try:
                posts = vk.wall.get(owner_id=pub, count=5, filter='owner')
                for post in posts['items']:
                    post_id = post['id']
                    key = f"{pub}_{post_id}"
                    if key in posted:
                        continue
                    post_text = post.get('text', '').lower()
                    if any(kw in post_text for kw in KEYWORDS):
                        print(f"Пост для комментария: {pub}/{post_id}")
                        comment_text = random.choice(COMMENTS_LIST)
                        if post_comment(vk_session, pub, post_id, comment_text):
                            posted[key] = datetime.now().isoformat()
                            save_json(POSTS_LOG, posted)
                            log_action(pub, 'comment_on_post', str(post_id), 'success')
                            any_success = True
                            # Пауза ТОЛЬКО после успешного комментария
                            delay = random.uniform(MIN_COMMENT_DELAY, MAX_COMMENT_DELAY)
                            print(f"Пауза {delay:.0f} сек")
                            time.sleep(delay)
                            break  # выходим из цикла постов, чтобы не комментировать подряд
                time.sleep(15)  # короткая пауза между группами (не блокирует, если не было успеха)
            except Exception as e:
                error_str = str(e)
                if 'Access denied' in error_str or 'group is blocked' in error_str:
                    print(f"Группа {pub} недоступна – пропуск без паузы")
                else:
                    print(f"Ошибка: {e}")
                    time.sleep(30)
        if not any_success:
            time.sleep(60)  # если ни одной успешной операции, делаем паузу перед следующим кругом

# ========== ПОТОК 2: ОТВЕТЫ НА КОММЕНТАРИИ (аналогично – без паузы после ошибок) ==========
def reply_comments_worker(vk_session, publics, my_id, stop_event):
    vk = vk_session.get_api()
    replied = load_json(REPLIES_LOG)
    while not stop_event.is_set():
        any_success = False
        for pub in publics:
            if stop_event.is_set():
                break
            try:
                posts = vk.wall.get(owner_id=pub, count=5, filter='owner')
                for post in posts['items']:
                    post_id = post['id']
                    comments = vk.wall.getComments(owner_id=pub, post_id=post_id, count=30)
                    for comment in comments['items']:
                        from_id = comment['from_id']
                        if from_id == my_id:
                            continue
                        comment_id = comment['id']
                        key = f"{pub}_{post_id}_{comment_id}"
                        if key in replied:
                            continue
                        text = comment.get('text', '').lower()
                        if any(trigger in text for trigger in REPLY_TRIGGERS):
                            print(f"Найден комментарий для ответа: {pub}/{post_id} от {from_id}")
                            reply_text = random.choice(REPLY_COMMENTS_LIST)
                            if reply_to_comment(vk_session, pub, post_id, comment_id, reply_text):
                                replied[key] = datetime.now().isoformat()
                                save_json(REPLIES_LOG, replied)
                                log_action(from_id, 'reply_to_comment', f"{pub}_{post_id}_{comment_id}", 'success')
                                any_success = True
                                delay = random.uniform(MIN_REPLY_DELAY, MAX_REPLY_DELAY)
                                print(f"Пауза {delay:.0f} сек")
                                time.sleep(delay)
                                break  # выходим после успешного ответа, чтобы не флудить
                time.sleep(15)
            except Exception as e:
                if 'Access denied' in str(e) or 'group is blocked' in str(e):
                    print(f"Группа {pub} недоступна – пропуск")
                else:
                    print(f"Ошибка: {e}")
                    time.sleep(30)
        if not any_success:
            time.sleep(60)

# ========== ПОТОК 3: ПРОСЛУШИВАНИЕ ЛИЧНЫХ СООБЩЕНИЙ ==========
def listen_messages(vk_session, my_id, stop_event):
    second_sent = load_json(SECOND_SENT_LOG)
    longpoll = VkLongPoll(vk_session)
    pending_timers = {}
    try:
        for event in longpoll.listen():
            if stop_event.is_set():
                break
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                user_id = str(event.user_id)
                if user_id == my_id:
                    continue
                if user_id in second_sent:
                    continue
                if user_id in pending_timers and pending_timers[user_id].is_alive():
                    continue
                text = event.text
                if is_positive(text):
                    now = datetime.now().isoformat()
                    print(f"[{now}] {user_id} ответил положительно: {text}")
                    log_action(user_id, 'first_reply_positive', '', 'received')
                    def send_second(uid):
                        msg = random.choice(SECOND_MSG_LIST)
                        if send_message(vk_session, int(uid), msg):
                            now2 = datetime.now().isoformat()
                            print(f"[{now2}] Второе сообщение отправлено {uid}")
                            second_sent[uid] = now2
                            save_json(SECOND_SENT_LOG, second_sent)
                            log_action(uid, 'second_message_sent', msg[:50], 'success')
                        if uid in pending_timers:
                            del pending_timers[uid]
                    timer = threading.Timer(DELAY_BEFORE_SECOND, send_second, args=[user_id])
                    timer.daemon = True
                    timer.start()
                    pending_timers[user_id] = timer
                else:
                    print(f"{user_id} ответил отрицательно/нейтрально: {text}")
    except Exception as e:
        print(f"Ошибка ЛС: {e}")

# ========== ЗАПУСК ==========
def main():
    if not ACCESS_TOKEN or ACCESS_TOKEN == "ВАШ_ТОКЕН_СЮДА":
        print("Ошибка: токен не задан!")
        return
    vk_session = vk_api.VkApi(token=ACCESS_TOKEN)
    try:
        my_id = str(vk_session.get_api().users.get()[0]['id'])
        print(f"ID вашего аккаунта: {my_id}")
    except:
        print("Не удалось получить свой ID")
        return

    init_report()
    # Автоматически ищем группы
    publics = find_groups(vk_session)
    if not publics:
        print("Не найдено ни одной группы. Проверьте ключевые слова или токен.")
        return

    stop_event = threading.Event()
    threads = [
        threading.Thread(target=comment_posts_worker, args=(vk_session, publics, stop_event), daemon=True),
        threading.Thread(target=reply_comments_worker, args=(vk_session, publics, my_id, stop_event), daemon=True),
        threading.Thread(target=listen_messages, args=(vk_session, my_id, stop_event), daemon=True)
    ]
    for t in threads:
        t.start()

    print(f"Бот запущен. Обрабатывается {len(publics)} групп (автоматически найдены).")
    print("1. Комментирование постов (без паузы при ошибках)")
    print("2. Ответы на комментарии")
    print("3. Обработка ЛС (свои игнорируются)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nОстановка бота...")
        stop_event.set()
        for t in threads:
            t.join(timeout=2)
        print("Бот остановлен.")

if __name__ == "__main__":
    main()