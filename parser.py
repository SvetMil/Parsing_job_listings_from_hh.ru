import os
import sys
import json
import time
import requests
from playwright.sync_api import sync_playwright

# Фильтры поиска вакансий (Красноярск, Бухгалтер, Удаленка)
SEARCH_URL = "https://krasnoyarsk.hh.ru/search/vacancy?hhtmFromLabel=header&hhtmFrom=resume_profile_front&text=%22%D0%91%D1%83%D1%85%D0%B3%D0%B0%D0%BB%D1%82%D0%B5%D1%80+%D0%BD%D0%B0+%D1%83%D0%B4%D0%B0%D0%BB%D0%B5%D0%BD%D0%BD%D1%8B%D0%B9+%D0%B4%D0%BE%D1%81%D1%82%D1%83%D0%BF%22+OR+%22%D0%9E%D0%BF%D0%B5%D1%80%D0%B0%D1%82%D0%BE%D1%80+%D0%9F%D0%9A+%281%D0%A1%2C+%D0%AD%D0%94%D0%9E%29%22+OR+%22%D0%A1%D0%BF%D0%B5%D1%86%D0%B8%D0%B0%D0%BB%D0%B8%D1%81%D1%82+%D0%BF%D0%BE+%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%B5+%D1%81+%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%B0%D0%BC%D0%B8+%D0%AD%D0%94%D0%9E+%D0%B8+%D0%9C%D0%B5%D1%80%D0%BA%D1%83%D1%80%D0%B8%D0%B9%22+OR+%22%D0%A1%D0%BF%D0%B5%D1%86%D0%B8%D0%B0%D0%BB%D0%B8%D1%81%D1%82+1%D0%A1%22&area=113&search_field=name&search_field=company_name&search_field=description&work_format=REMOTE&enable_snippets=true" 

# === НАДЕЖНЫЙ СБОР ТОКЕНОВ ИЗ ВСЕХ ИСТОЧНИКОВ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VK_TOKEN = os.getenv("VK_TOKEN")
VK_USER_ID = os.getenv("VK_USER_ID")

# Если запуск ручной через Google-кнопку, извлекаем данные из payload
event_path = os.getenv("GITHUB_EVENT_PATH")
if event_path and os.path.exists(event_path):
    try:
        with open(event_path, "r", encoding="utf-8") as f:
            event_data = json.load(f)
        
        # Исправлено на основе лога диагностики: берем client_payload прямо с верхнего уровня
        payload = event_data.get("client_payload", {})
        if payload.get("tg_token"):
            TELEGRAM_TOKEN = payload.get("tg_token")
            TELEGRAM_CHAT_ID = payload.get("tg_chat_id")
    except Exception as e:
        print(f"Запуск без payload (используются Secrets): {e}")

# Финальная проверка авторизации
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
        
        vacancy_cards = page.locator('[data-qa="vacancy-serp__vacancy-title"]').all()
        new_count = 0
        valid_vacancies = {}
        
        for card in vacancy_cards:
            try:
                href = card.get_attribute("href")
                title = card.inner_text().strip()
                if href and title:
                    clean_href = href.split("?")[0]
                    v_id = ''.join(filter(str.isdigit, clean_href))
                    if v_id:
                        valid_vacancies[v_id] = {"title": title, "url": clean_href}
            except:
                continue

        print(f"Успешно распознано вакансий на странице: {len(valid_vacancies)}")
        
        for v_id, info in valid_vacancies.items():
            if v_id not in seen_vacancies:
                new_count += 1
                message = f"🌟 *Новая вакансия!*\n\n📌 {info['title']}\n🔗 Ссылка: {info['url']}"
                
                print(f"Отправка уведомлений: {info['title']}")
                send_telegram(message)
                send_vk(message)
                
                save_vacancy(v_id)
                seen_vacancies.add(v_id)
                time.sleep(2.0)
                
        if new_count == 0:
            print("Новых вакансий нет. Все вакансии уже сохранены в seen_vacancies.txt.")
        browser.close()

if __name__ == "__main__":
    parse_hh()
