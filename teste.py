import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)

sheet = client.open_by_key("1UuQGybYpctVCOq5xhR_26THJOEk9jfdytLW1Be2HfRs")
aba = sheet.worksheet("Ordem_Producao_V2")
print(aba.get_all_records())
