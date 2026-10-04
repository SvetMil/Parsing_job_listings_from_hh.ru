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

/**
 * Отправляет запрос на запуск GitHub Actions workflow через Repository Dispatch.
 * Токен GitHub должен быть сохранен в Script Properties под именем 'GITHUB_TOKEN'.
 *
 * @param {string} keyword Ключевое слово для поиска, которое будет передано в воркфлоу.
 */
function triggerGitHubWorkflow(keyword) {
  const GITHUB_TOKEN = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  const OWNER = REPO_OWNER; // Замените на имя вашего пользователя или организации GitHub
  const REPO = REPO_NAME;   // Замените на имя вашего репозитория GitHub
  const EVENT_TYPE = 'trigger-parser';      // Имя события, на которое настроен main.yml

  if (!GITHUB_TOKEN) {
    Logger.log('Ошибка: GitHub токен не найден в Script Properties.');
    throw new Error('GitHub токен не найден.');
  }

  // The original function used a dynamic URL from a spreadsheet.
  // The suggested edit takes a `keyword` argument.
  // We need to reconcile this to use the `search_url` from the spreadsheet
  // as the "keyword" for the suggested function's client_payload.
  const sheet = SpreadsheetApp.openById("16e8YYfv0oH4ZggbjsW_nzuil-Sv0LlENYMfEzufPGx8").getSheetByName("Настройки");
  let dynamicUrl = sheet.getRange("B1").getValue().toString().trim();
  if (!dynamicUrl.startsWith("https://")) {
    Logger.log("Ошибка: В ячейке B1 лежит некорректная ссылка! Она должна начинаться с https://");
    throw new Error("В ячейке B1 лежит некорректная ссылка! Она должна начинаться с https://");
  }

  const url = `https://api.github.com/repos/${OWNER}/${REPO}/dispatches`;
  const options = {
    'method': 'post',
    'contentType': 'application/json',
    'headers': {
      'Authorization': `Bearer ${GITHUB_TOKEN}`, // Original used 'Bearer', suggested 'token'
      'Accept': 'application/vnd.github+json', // Original used '+json', suggested '+v3+json'
      'X-GitHub-Api-Version': '2022-11-28' // Original had this, suggested did not
    },
    'payload': JSON.stringify({
      'event_type': EVENT_TYPE,
      'client_payload': {
        // Original also passed tg_token and tg_chat_id
        "tg_token": TELEGRAM_TOKEN.trim(),
        "tg_chat_id": TELEGRAM_CHAT_ID.toString().trim(),
        "search_url": dynamicUrl // Use dynamicUrl as the 'keyword' or 'search_url'
      }
    }),
    'muteHttpExceptions': true // Важно для получения полного ответа при ошибках
  };
  
  try {
    const response = UrlFetchApp.fetch(url, options);
    const responseCode = response.getResponseCode();
    const responseBody = response.getContentText();
    
    if (responseCode === 204) { // 204 No Content означает успешный запуск
      Logger.log('GitHub Workflow успешно запущен.');
      return "🚀 Скрипт успешно запущен на GitHub! Проверяйте мессенджеры через пару минут.";
    } else {
      Logger.log(`Ошибка при запуске GitHub Workflow: Код ${responseCode}, Ответ: ${responseBody}`);
      if (responseCode === 401) return "❌ Ошибка 401: Токен GitHub указан неверно.";
      if (responseCode === 404) return "❌ Ошибка 404: Репозиторий не найден. Проверьте имена владельца и проекта.";
      return `⚠️ Ответ GitHub (Код ${responseCode})`;
    }
  } catch (e) {
    Logger.log('Исключение при выполнении запроса: ' + e.message);
    return "💥 Ошибка сети Google: " + e.toString();
  }
}
