from telethon import TelegramClient, events, sync
api_id = 14155598
api_hash = '0a4c62b754438db563008a67f2197ec7'
client = TelegramClient('session_name', api_id, api_hash)
client.start()

for dialog in client.iter_dialogs():
  print(f"{dialog.id}:{dialog.name}")
