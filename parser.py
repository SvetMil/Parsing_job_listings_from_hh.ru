import time
import requests
from playwright.sync_api import sync_playwright

# === НАСТРОЙКИ ===
# Ссылка на результаты поиска (настройте фильтры на сайте hh.ru и скопируйте URL сюда)
SEARCH_URL = "https://krasnoyarsk.hh.ru/search/vacancy?hhtmFromLabel=header&hhtmFrom=resume_profile_front&text=%22%D0%91%D1%83%D1%85%D0%B3%D0%B0%D0%BB%D1%82%D0%B5%D1%80+%D0%BD%D0%B0+%D1%83%D0%B4%D0%B0%D0%BB%D0%B5%D0%BD%D0%BD%D1%8B%D0%B9+%D0%B4%D0%BE%D1%81%D1%82%D1%83%D0%BF%22+OR+%22%D0%9E%D0%BF%D0%B5%D1%80%D0%B0%D1%82%D0%BE%D1%80+%D0%9F%D0%9A+%281%D0%A1%2C+%D0%AD%D0%94%D0%9E%29%22+OR+%22%D0%A1%D0%BF%D0%B5%D1%86%D0%B8%D0%B0%D0%BB%D0%B8%D1%81%D1%82+%D0%BF%D0%BE+%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%B5+%D1%81+%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%B0%D0%BC%D0%B8+%D0%AD%D0%94%D0%9E+%D0%B8+%D0%9C%D0%B5%D1%80%D0%BA%D1%83%D1%80%D0%B8%D0%B9%22+OR+%22%D0%A1%D0%BF%D0%B5%D1%86%D0%B8%D0%B0%D0%BB%D0%B8%D1%81%D1%82+1%D0%A1%22&area=113&search_field=name&search_field=company_name&search_field=description&work_format=REMOTE&enable_snippets=true" 

TELEGRAM_TOKEN = "8935437490:AAH50t92BuZ-EGTBiU8EI6C3f7-Sp9gy3kU"  # Замените на токен от BotFather
TELEGRAM_CHAT_ID = "7083993290"   # Замените на ваш ID от userinfobot
# =================

# Файл, где будут храниться ID вакансий, чтобы не присылать их повторно
DB_FILE = "seen_vacancies.txt"

def load_seen_vacancies():
    try:
        with open(DB_FILE, "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_vacancy(v_id):
    with open(DB_FILE, "a") as f:
        f.write(f"{v_id}\n")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")

def parse_hh():
    print("Запуск браузера...")
    seen_vacancies = load_seen_vacancies()
    
    with sync_playwright() as p:
        # headless=True уберет всплывающее окно браузера, скрипт будет работать незаметно в консоли
        browser = p.chromium.launch(headless=True) 
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="ru-RU"
        )
        page = context.new_page()
        
        print(f"Переход по ссылке...")
        page.goto(SEARCH_URL, wait_until="networkidle")
        
        links_elements = page.locator('a[href*="/vacancy/"]').all()
        
        new_count = 0
        valid_vacancies = {}
        
        for el in links_elements:
            try:
                href = el.get_attribute("href")
                title = el.inner_text().strip()
                
                if href and title and len(title) > 5:
                    # Корректно извлекаем ID вакансии, отсекая все параметры после знака ?
                    clean_href = href.split("?")[0]
                    # Извлекаем только цифры ID из структуры ссылки
                    v_id = clean_href.split("/vacancy/")[-1].replace("/", "").strip()
                    
                    if v_id.isdigit(): 
                        valid_vacancies[v_id] = {"title": title}
            except:
                continue

        print(f"Найдено уникальных вакансий на странице: {len(valid_vacancies)}")
        
        for v_id, info in valid_vacancies.items():
            if v_id not in seen_vacancies:
                new_count += 1
                # ИСПРАВЛЕНО: Добавлен обязательный слэш (/) между доменом и ID вакансии
                clean_url = f"https://krasnoyarsk.hh.ru/vacancy/{v_id}"
                
                message = f"🌟 *Новая вакансия!*\n\n📌 *{info['title']}*\n🔗 [Открыть на HH]({clean_url})"
                
                print(f"Отправка в ТГ: {info['title']}")
                send_telegram(message)
                
                # Сохраняем строго очищенный ID в базу данных
                save_vacancy(v_id)
                # Добавляем в локальное множество текущей сессии, чтобы не дублировать
                seen_vacancies.add(v_id) 
                
                time.sleep(1.5)
                
        if new_count == 0:
            print("Новых вакансий нет или все они уже были обработаны.")
            
        browser.close()

if __name__ == "__main__":
    parse_hh()
