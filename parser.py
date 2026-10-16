# SEARCH_URL = "https://hh.ru"
# url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
# url = "https://api.vk.com/method/messages.send"

import os
import requests
import xml.etree.ElementTree as ET
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
    
    if photo_url:
        try:
            vk_proto = "https://"
            vk_api_domain = "api.vk.com"
            vk_method_path = "/method/"
            
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
                if response_list and isinstance(response_list, list):
                    photo_info = response_list[0]
                    owner_id = photo_info.get("owner_id")
                    media_id = photo_info.get("id")
                    if owner_id and media_id:
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
    """Основной рабочий цикл парсера."""
    hh_proto = "https://"
    hh_domain = "krasnoyarsk.hh.ru"
    hh_rss_path = "/search/vacancy/rss"
    rss_url = hh_proto + hh_domain + hh_rss_path
    
    params = {"text": "Курьер", "area": 54, "order_by": "publication_time"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    seen_file = "seen_vacancies.txt"
    seen_ids = set()
    if os.path.exists(seen_file):
        with open(seen_file, "r") as f:
            seen_ids = set(line.strip() for line in f if line.strip())

    print("📡 Подключение к живой ленте hh.ru...")
    try:
        response = requests.get(rss_url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"❌ hh.ru недоступен. Статус: {response.status_code}")
            return
            
        root = ET.fromstring(response.content)
        new_count = 0
        
        for item in root.findall(".//item"):
            title = item.find("title").text or ""
            link = item.find("link").text or ""
            desc = item.find("description").text or ""
            
            v_id = link.split("/vacancy/")[-1].split("?")[0].replace("/", "") if "/vacancy/" in link else None
            
            if not v_id or v_id in seen_ids:
                continue  
                
            company = "Прямой работодатель"
            salary = "Зарплата не указана"

            # 🎯 ТОЧЕЧНО ИСПРАВЛЕНО: Теперь replace вызывается у текстовой строки, а не у всего списка!
            if "Вакансия компании:" in desc:
                raw_company = desc.split("Вакансия компании:")[-1].split("</p>")[0]
                company = raw_company.replace("</div>", "").replace("<td>", "").strip()

            if "Предполагаемый уровень месячного дохода:" in desc:
                raw_salary = desc.split("Предполагаемый уровень месячного дохода:")[-1].split("</p>")[0]
                salary = raw_salary.replace("</div>", "").replace("<td>", "").strip()
             
            clean_link = link.split('?')[0]
            post_text = (
                f"💼 *Новая вакансия: {title.strip()}*\n\n"
                f"🏢 Компания: {company}\n"
                f"💰 Зарплата: {salary}\n"
                f"📍 Город: Красноярск\n\n"
                f"🔗 Откликнуться на hh.ru: {clean_link}"
            )
            
            default_photo = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500"
            
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
