# SEARCH_URL = "https://hh.ru"
# url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
# url = "https://api.vk.com/method/messages.send"

import os
import requests
import time

# === НАДЕЖНЫЙ СБОР ТОКЕНОВ ИЗ ВСЕХ ИСТОЧНИКОВ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VK_TOKEN = os.getenv("VK_TOKEN")
VK_USER_ID = os.getenv("VK_USER_ID")  # ID вашей страницы или группы (с минусом для групп)

def send_telegram_post(vacancy_text, photo_url=None):
    """Отправляет пост в Telegram-канал/чат (с фото или без)."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram-токены отсутствуют. Пропуск.")
        return False
        
    if photo_url:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": photo_url, "caption": vacancy_text, "parse_mode": "Markdown"}
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": vacancy_text, "parse_mode": "Markdown"}
        
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"🚨 Ошибка отправки в TG: {e}")
        return False

def send_vk_post(vacancy_text, photo_url=None):
    """Отправляет пост на стену VK (с картинкой или без)."""
    if not VK_TOKEN or not VK_USER_ID:
        print("⚠️ VK-токены отсутствуют. Пропуск.")
        return False
        
    attachments = ""
    vk_proto = "https://"
    vk_api_domain = "api.vk.com"
    vk_method_path = "/method/"
    
    if photo_url:
        try:
            server_url = vk_proto + vk_api_domain + vk_method_path + "photos.getWallUploadServer"
            server_res = requests.get(
                server_url,
                params={"access_token": VK_TOKEN, "v": "5.131", "group_id": abs(int(VK_USER_ID)) if int(VK_USER_ID) < 0 else None},
                timeout=10
            ).json()
            
            upload_url = server_res.get("response", {}).get("upload_url")
            
            if upload_url:
                img_data = requests.get(photo_url, timeout=10).content
                upload_res = requests.post(upload_url, files={"photo": ("img.jpg", img_data)}, timeout=10).json()
                
                save_url = vk_proto + vk_api_domain + vk_method_path + "photos.saveWallPhoto"
                save_params = {
                    "access_token": VK_TOKEN,
                    "v": "5.131",
                    "photo": upload_res.get("photo"),
                    "server": upload_res.get("server"),
                    "hash": upload_res.get("hash")
                }
                if int(VK_USER_ID) < 0:
                    save_params["group_id"] = abs(int(VK_USER_ID))
                else:
                    save_params["user_id"] = VK_USER_ID

                save_res = requests.get(save_url, params=save_params, timeout=10).json()
                
                response_list = save_res.get("response", [])
                if response_list and isinstance(response_list, list) and len(response_list) > 0:
                    photo_info = response_list[0]
                    owner_id = photo_info.get("owner_id")
                    media_id = photo_info.get("id")
                    if owner_id is not None and media_id is not None:
                        attachments = f"photo{owner_id}_{media_id}"
        except Exception as e:
            print(f"🚨 Не удалось прикрепить фото к VK-посту: {e}")

    post_url = vk_proto + vk_api_domain + vk_method_path + "wall.post"
    vk_params = {
        "access_token": VK_TOKEN,
        "v": "5.131",
        "owner_id": VK_USER_ID,
        "message": vacancy_text.replace("*", ""),  # В VK нет маркдауна со звездочками
        "attachments": attachments
    }
    
    try:
        res = requests.post(post_url, data=vk_params, timeout=10).json()
        return "response" in res
    except Exception as e:
        print(f"🚨 Ошибка отправки в VK: {e}")
        return False

def parse_and_post():
    """Основной рабочий цикл парсера через официальное API hh.ru."""
    # ИСПРАВЛЕНО: Указан верный базовый эндпоинт для работы с вакансиями API
    api_url = "https://api.hh.ru/vacancies"
    
    # Параметры поиска: Курьер, Регион: Красноярск (54), Сортировка по дате
    params = {
        "text": "Курьер", 
        "area": 54, 
        "order_by": "publication_time",
        "per_page": 10  # Берем топ-10 свежих вакансий за запуск
    }
    # Техническое требование hh.ru: обязательно передавать уникальный User-Agent
    headers = {"User-Agent": "JobListingParserApp/1.0 (SvetMil@github.com)"}
    
    seen_file = "seen_vacancies.txt"
    seen_ids = set()
    if os.path.exists(seen_file):
        with open(seen_file, "r") as f:
            seen_ids = set(line.strip() for line in f if line.strip())

    print("📡 Подключение к официальному API hh.ru...")
    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"❌ hh.ru API недоступно. Статус: {response.status_code}, Ответ: {response.text}")
            return
            
        data = response.json()
        items = data.get("items", [])
        new_count = 0
        
        for item in items:
            v_id = str(item.get("id"))
            
            if not v_id or v_id in seen_ids:
                continue  
                
            title = item.get("name", "Без названия")
            link = item.get("alternate_url", f"https://hh.ru/vacancy/{v_id}")
            
            # Извлекаем компанию
            employer = item.get("employer", {})
            company = employer.get("name", "Прямой работодатель") if employer else "Прямой работодатель"
            
            # Форматируем зарплату
            salary_data = item.get("salary")
            salary = "Зарплата не указана"
            if salary_data:
                s_from = salary_data.get("from")
                s_to = salary_data.get("to")
                curr = salary_data.get("currency", "руб.")
                if curr == "RUR": 
                    curr = "руб."
                
                if s_from and s_to:
                    salary = f"от {s_from} до {s_to} {curr}"
                elif s_from:
                    salary = f"от {s_from} {curr}"
                elif s_to:
                    salary = f"до {s_to} {curr}"

            post_text = (
                f"💼 *Новая вакансия: {title.strip()}*\n\n"
                f"🏢 Компания: {company}\n"
                f"💰 Зарплата: {salary}\n"
                f"📍 Город: Красноярск\n\n"
                f"🔗 Откликнуться на hh.ru: {link}"
            )
            
            # ИСПРАВЛЕНО: Корректный CDN-домен картинок Unsplash и добавлены слэши
            p_id = "photo-1618005182384-a83a8bd57fbe"
            p_mod = "?w=500"
            default_photo = f"https://images.unsplash.com/{p_id}{p_mod}"
            
            print(f"🚀 Публикация новой вакансии ID: {v_id}...")
            tg_ok = send_telegram_post(post_text, default_photo)
            vk_ok = send_vk_post(post_text, default_photo)
            
            if tg_ok or vk_ok:
                seen_ids.add(v_id)
                new_count += 1
                time.sleep(2)  
                
        with open(seen_file, "w") as f:
            for uid in seen_ids:
                f.write(f"{uid}\n")
                
        print(f"✅ Работа завершена. Опубликовано новых вакансий: {new_count}")
        
    except Exception as e:
        print(f"🚨 Критическая ошибка в главном цикле: {e}")

if __name__ == "__main__":
    parse_and_post()
