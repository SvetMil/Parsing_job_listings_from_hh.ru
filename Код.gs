// Конфигурация вашего репозитория
const TELEGRAM_TOKEN = PropertiesService.getScriptProperties().getProperty('TELEGRAM_TOKEN');
const TELEGRAM_CHAT_ID = PropertiesService.getScriptProperties().getProperty('TELEGRAM_CHAT_ID');
const GITHUB_TOKEN = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');

const REPO_OWNER = "SvetMil"; 
const REPO_NAME = "Parsing_job_listings_from_hh.ru"; 
// ======================================

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
      .setTitle('Запуск Парсера Вакансий')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      // ИСПРАВЛЕНО: Принудительно заставляем Google выдать мобильный масштаб
      .addMetaTag('viewport', 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no');
}

function triggerGitHubWorkflow() {
  const sheet = SpreadsheetApp.openById("16e8YYfv0oH4ZggbjsW_nzuil-Sv0LlENYMfEzufPGx8").getSheetByName("Настройки");
  let dynamicUrl = sheet.getRange("B1").getValue().toString().trim();
  // dynamicUrl = "";
  try {
  } catch(e) {
    return "❌ Техническая ошибка Google: " + e.toString();
  }

  if (!dynamicUrl.startsWith("https://")) {
    return "❌ Ошибка: В ячейке B1 лежит некорректная ссылка! Она должна начинаться с https://";
  }

  const url = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/dispatches`;
  
  const payload = {
    "event_type": "trigger-parser", 
    "client_payload": {
      "tg_token": TELEGRAM_TOKEN.trim(),
      "tg_chat_id": TELEGRAM_CHAT_ID.toString().trim(),
      // ПЕРЕДАЕМ ССЫЛКУ ИЗ ТАБЛИЦЫ НА ГИТХАБ
      "search_url": dynamicUrl
    }
  };
  
  const options = {
    "method": "post",
    "contentType": "application/json",
    "headers": {
      "Authorization": "Bearer " + GITHUB_TOKEN.trim(),
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28"
    },
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true 
  };
  
  try {
    const response = UrlFetchApp.fetch(url, options);
    const code = response.getResponseCode();
    
    if (code === 204) {
      return "🚀 Скрипт успешно запущен на GitHub! Проверяйте мессенджеры через пару минут.";
    } 
    if (code === 401) return "❌ Ошибка 401: Токен GitHub указан неверно.";
    if (code === 404) return "❌ Ошибка 404: Репозиторий не найден. Проверьте имена владельца и проекта.";
    
    return `⚠️ Ответ GitHub (Код ${code})`;
  } catch(e) {
    return "💥 Ошибка сети Google: " + e.toString();
  }
}