import os
import sys
import json
import time
import requests
from playwright.sync_api import sync_playwright

# Фильтры поиска вакансий (Красноярск, Бухгалтер, Удаленка)
SEARCH_URL = ""

# === НАДЕЖНЫЙ СБОР ТОКЕНОВ ИЗ ВСЕХ ИСТОЧНИКОВ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VK_TOKEN = os.getenv("VK_TOKEN")
VK_USER_ID = os.getenv("VK_USER_ID")

# Извлекаем данные, которые прислала наша синяя Google-кнопка
event_path = os.getenv("GITHUB_EVENT_PATH")
if event_path and os.path.exists(event_path):
    try:
        with open(event_path, "r", encoding="utf-8") as f:
            event_data = json.load(f)
        
        payload = event_data.get("client_payload", {})
        if payload.get("tg_token"):
            TELEGRAM_TOKEN = payload.get("tg_token")
            TELEGRAM_CHAT_ID = payload.get("tg_chat_id")
            
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Перезаписываем SEARCH_URL строго той ссылкой, которая пришла из ячейки B1
        if payload.get("search_url"):
            SEARCH_URL = payload.get("search_url")
            print(f"🔥 Успех! Робот переключился на динамическую ссылку из Google Таблицы.")
            
    except Exception as e:
        print(f"Запуск по расписанию (используются Secrets): {e}")

# Защитная проверка: если и из таблицы ничего не пришло, и в Secrets пусто — ставим базовую заглушку на Бухгалтеров
if not SEARCH_URL:
    SEARCH_URL = "https://hh.ru"

# Финальная проверка авторизации мессенджеров
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("⛔️ Критическая ошибка: Авторизация Telegram отсутствует. Скрипт остановлен.")
    sys.exit(0)

DB_FILE = "seen_vacancies.txt"

def load_seen_vacancies():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_vacancy(v_id):
    with open(DB_FILE, "a", encoding="utf-8") as f:
        f.write(f"{v_id}\n")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Ошибка Telegram: {e}")

def send_vk(text):
    if not VK_TOKEN or not VK_USER_ID:
        print("Внимание: Токены VK отсутствуют в Secrets репозитория. Сообщение в VK пропущено.")
        return
    clean_text = text.replace("*", "")
    url = "https://api.vk.com/method/messages.send"
    payload = {
        "user_id": VK_USER_ID,
        "message": clean_text,
        "random_id": int(time.time() * 1000),
        "access_token": VK_TOKEN,
        "v": "5.131"
    }
    try:
        res = requests.post(url, data=payload, timeout=10).json()
        if "error" in res:
            print(f"Ошибка VK API: {res['error']['error_msg']}")
    except Exception as e:
        print(f"Ошибка отправки в VK: {e}")

def parse_hh():
    print("Запуск анти-детект браузера...")
    seen_vacancies = load_seen_vacancies()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 YaBrowser/24.4.0.0",
            viewport={"width": 1440, "height": 900},
            locale="ru-RU",
            timezone_id="Asia/Krasnoyarsk"
        )
        page = context.new_page()
        page.add_init_script("delete navigator.__proto__.webdriver;")
        
        print("Подключение к HeadHunter...")
        page.goto(SEARCH_URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(5000)
        
        # ИСПРАВЛЕНО: Возвращаем самый надежный сбор ссылок по тегу /vacancy/
        links_elements = page.locator('a[href*="/vacancy/"]').all()
        new_count = 0
        valid_vacancies = {}
        
        for el in links_elements:
            try:
                href = el.get_attribute("href")
                title = el.inner_text().strip()
                
                if href and title and len(title) > 5:
                    # ИСПРАВЛЕНО: Четкое и безопасное извлечение ID вакансии без мусора из URL
                    clean_href = href.split("?")[0]
                    v_id = clean_href.split("/vacancy/")[-1].replace("/", "").strip()
                    
                    if v_id.isdigit(): 
                        valid_vacancies[v_id] = {"title": title, "url": clean_href}
            except:
                continue

        print(f"Успешно распознано вакансий на странице: {len(valid_vacancies)}")

        # Создаем уникальный текстовый ключ на основе текущей ссылки, чтобы разделять разные поиски
        import hashlib
        search_key = hashlib.md5(SEARCH_URL.encode('utf-8')).hexdigest()[:8]
        
        for v_id, info in valid_vacancies.items():
            # Теперь проверяем уникальную связку "ID вакансии + Ключ поиска"
            memory_key = f"{v_id}_{search_key}"
            
            if memory_key not in seen_vacancies:
                new_count += 1
                message = f"🌟 *Новая вакансия!*\n\n📌 {info['title']}\n🔗 Ссылка: {info['url']}"
                
                print(f"Отправка уведомлений: {info['title']}")
                send_telegram(message)
                send_vk(message)
                
                # Сохраняем в файл уникальную связку, а не просто голый ID
                save_vacancy(memory_key)
                seen_vacancies.add(memory_key) 
                time.sleep(2.0)
                
        if new_count == 0:
            print("По этой ссылке новых вакансий не обнаружено. Все они уже есть в памяти.")
        browser.close()

if __name__ == "__main__":
    parse_hh()
