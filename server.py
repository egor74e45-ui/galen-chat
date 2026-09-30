import asyncio
import json
import random
from websockets import serve

TWITCH_SERVER = "irc.chat.twitch.tv"
TWITCH_PORT = 6667
CONNECTED_CLIENTS = set()

# Дефолтные настройки для ОБС
current_settings = {
    "size": "17px",
    "font": "'Segoe UI', sans-serif",
    "margin": "6px",
    "align": "left",
    "color": "#ffffff"
}

# База фраз для симуляции, если Твич недоступен или выдает ошибку
SIM_USERS = ["Alex_Gamer", "Cyber_Katya", "Buster_Fan", "Danil_10", "Sofia_Spb"]
SIM_TEXTS = ["Всем привет!", "Стрим лагает?", " Galen Chat круто выглядит!", "Какая игра сегодня?", "Модеры, чекните лс"]

async def read_twitch_chat(channel_name):
    """Подключается к Twitch через встроенные потоки asyncio без регулярных выражений"""
    try:
        print(f"📡 Подключаемся к Twitch для канала: {channel_name}...")
        reader, writer = await asyncio.open_connection(TWITCH_SERVER, TWITCH_PORT)
        
        writer.write(b"PASS justinfan12345\r\n")
        writer.write(b"NICK justinfan12345\r\n")
        writer.write(f"JOIN #{channel_name.lower()}\r\n".encode('utf-8'))
        await writer.drain()
        
        print(f"✅ Успешно вошли в чат канала: #{channel_name}")
        
        while CONNECTED_CLIENTS:
            line_bytes = await reader.readline()
            if not line_bytes:
                break
                
            line = line_bytes.decode('utf-8', errors='ignore').strip()
            
            if line.startswith("PING"):
                writer.write(b"PONG :tmi.twitch.tv\r\n")
                await writer.drain()
                continue
            
            # Простой и надежный парсинг строки через split вместо регулярных выражений
            if "PRIVMSG" in line and "!" in line:
                try:
                    # Извлекаем ник пользователя (все что между : и !)
                    username = line.split("!")[0].replace(":", "")
                    # Извлекаем текст сообщения (все что после PRIVMSG #канал :)
                    text = line.split("PRIVMSG")[1].split(":", 1)[1]
                    
                    print(f"📨 Сообщение -> [{username}]: {text}")
                    
                    message_data = {"type": "chat", "username": username, "text": text}
                    js_string = json.dumps(message_data)
                    
                    for client in CONNECTED_CLIENTS.copy():
                        try: await client.send(js_string)
                        except: CONNECTED_CLIENTS.remove(client)
                except Exception:
                    continue # Пропускаем битые системные строки Твича
                        
    except Exception as e:
        print(f"⚠️ Твич недоступен ({e}). Включаем локальный симулятор чата...")
        # Если роутер или сеть блокируют Твич, сервер сам начнет генерировать сообщения
        while CONNECTED_CLIENTS:
            await asyncio.sleep(random.uniform(1.0, 2.5))
            message_data = {
                "type": "chat",
                "username": random.choice(SIM_USERS),
                "text": random.choice(SIM_TEXTS)
            }
            js_string = json.dumps(message_data)
            for client in CONNECTED_CLIENTS.copy():
                try: await client.send(js_string)
                except: CONNECTED_CLIENTS.remove(client)
    finally:
        print("🔌 Соединение закрыто.")

async def handler(websocket):
    global current_settings
    print("🌐 Подключилась новая вкладка!")
    CONNECTED_CLIENTS.add(websocket)
    
    await websocket.send(json.dumps({"type": "settings", "settings": current_settings}))
    
    twitch_task = None
    try:
        async for message in websocket:
            data = json.loads(message)
            
            if data.get("action") == "connect":
                channel = data.get("channel")
                if twitch_task:
                    twitch_task.cancel()
                twitch_task = asyncio.create_task(read_twitch_chat(channel))
                
            elif data.get("action") == "update_styles":
                current_settings = data.get("settings")
                broadcast_data = json.dumps({"type": "settings", "settings": current_settings})
                for client in CONNECTED_CLIENTS.copy():
                    if client != websocket:
                        try: await client.send(broadcast_data)
                        except: CONNECTED_CLIENTS.remove(client)
                            
        await websocket.wait_closed()
    finally:
        if twitch_task:
            twitch_task.cancel()
        CONNECTED_CLIENTS.remove(websocket)
        print("🔌 Вкладка отключилась.")

async def main():
    async with serve(handler, "0.0.0.0", 8765):
        print("🤖 Бэкенд Galen Chat запущен на ws://localhost:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
