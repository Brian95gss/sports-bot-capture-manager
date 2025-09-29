import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import aiohttp

app = FastAPI(title="Sports Capture Manager Bot")

# Variables de entorno
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')
AUTHORIZED_USER_ID = int(os.getenv('AUTHORIZED_USER_ID', '0'))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # https://tu-app.onrender.com

# Variables globales para estado
current_match = {}
current_batch = []

def is_authorized(update: dict) -> bool:
    """Verifica si el usuario está autorizado"""
    try:
        if 'message' in update:
            user_id = update['message']['from']['id']
        elif 'callback_query' in update:
            user_id = update['callback_query']['from']['id']
        else:
            return False
        return user_id == AUTHORIZED_USER_ID
    except:
        return False

@app.on_event("startup")
async def startup():
    """Configura el webhook al iniciar"""
    if BOT_TOKEN and WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
            payload = {"url": webhook_url}
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                print(f"Webhook configured: {result}")

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "running",
        "bot": "Sports Capture Manager",
        "webhook": f"{WEBHOOK_URL}/webhook" if WEBHOOK_URL else "not configured"
    }

@app.post("/webhook")
async def webhook(request: Request):
    """Recibe actualizaciones de Telegram"""
    try:
        update = await request.json()
        
        if not is_authorized(update):
            return {"ok": True}
        
        await process_update(update)
        return {"ok": True}
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=200)

async def process_update(update: dict):
    """Procesa las actualizaciones"""
    try:
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            
            if 'text' in message:
                text = message['text'].strip()
                
                if text.startswith('/start'):
                    await send_message(chat_id, "Bot de captura iniciado. Usa /help para ver comandos.")
                
                elif text.startswith('/new_match'):
                    match_text = text[11:].strip()
                    if ' vs ' in match_text.lower():
                        teams = match_text.lower().split(' vs ')
                        current_match['home'] = teams[0].strip()
                        current_match['away'] = teams[1].strip()
                        current_batch.clear()
                        await send_message(
                            chat_id,
                            f"✅ Partido iniciado:\n{current_match['home'].title()} vs {current_match['away'].title()}\n\nAhora envía las capturas."
                        )
                    else:
                        await send_message(chat_id, "Formato: /new_match Equipo1 vs Equipo2")
                
                elif text == '/status':
                    if current_match:
                        msg = f"📊 Partido actual:\n{current_match.get('home', 'N/A')} vs {current_match.get('away', 'N/A')}\n"
                        msg += f"Capturas: {len(current_batch)}"
                        await send_message(chat_id, msg)
                    else:
                        await send_message(chat_id, "No hay partido activo. Usa /new_match")
                
                elif text == '/clear':
                    current_match.clear()
                    current_batch.clear()
                    await send_message(chat_id, "✅ Lote eliminado")
                
                elif text == '/help':
                    help_text = """🤖 COMANDOS:

/new_match Equipo1 vs Equipo2 - Iniciar partido
/status - Ver estado actual
/clear - Limpiar todo
/help - Esta ayuda

Envía capturas de pantalla después de /new_match"""
                    await send_message(chat_id, help_text)
                
                else:
                    await send_message(chat_id, "Comando no reconocido. Usa /help")
            
            elif 'photo' in message:
                if current_match:
                    photo = message['photo'][-1]  # La imagen de mayor calidad
                    file_id = photo['file_id']
                    current_batch.append({
                        'file_id': file_id,
                        'timestamp': message['date']
                    })
                    await send_message(
                        chat_id,
                        f"✅ Captura {len(current_batch)} guardada\n\nEnvía más o usa /status"
                    )
                else:
                    await send_message(chat_id, "⚠️ Primero inicia un partido con /new_match")
                    
    except Exception as e:
        print(f"Error processing update: {e}")

async def send_message(chat_id: int, text: str):
    """Envía mensaje a Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    print(f"Error sending message: {response.status}")
                    
    except Exception as e:
        print(f"Error in send_message: {e}")

# Para Render
handler = app
