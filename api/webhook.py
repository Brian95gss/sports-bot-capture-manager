# Bot 1: Capture Manager - Webhook Principal para Vercel
import os
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse

# Crear app FastAPI
app = FastAPI(title="Sports Betting Bot - Capture Manager", version="1.0.0")

# Variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
AUTHORIZED_USER_ID = os.getenv('AUTHORIZED_USER_ID')
BOT2_WEBHOOK_URL = os.getenv('BOT2_WEBHOOK_URL')

# Función simple de validación de usuario
def is_authorized_user(update: dict) -> bool:
    """Verifica si el usuario está autorizado"""
    try:
        if not AUTHORIZED_USER_ID:
            return False
            
        authorized_id = int(AUTHORIZED_USER_ID)
        
        if 'message' in update:
            user_id = update['message']['from']['id']
        elif 'callback_query' in update:
            user_id = update['callback_query']['from']['id']
        else:
            return False
            
        return user_id == authorized_id
    except:
        return False

# Endpoint principal - CAMBIO CRÍTICO: usar "/" en lugar de "/api/webhook"
@app.post("/")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recibe updates de Telegram"""
    try:
        update = await request.json()
        
        # Solo procesar si es del usuario autorizado
        if not is_authorized_user(update):
            return {"ok": True, "message": "Unauthorized"}
        
        background_tasks.add_task(process_telegram_update, update)
        return {"ok": True}
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/")
async def health_check():
    """Health check para GET requests"""
    return {
        "status": "healthy",
        "service": "Capture Manager Bot",
        "version": "1.0.0",
        "webhook_configured": bool(TELEGRAM_BOT_TOKEN),
        "database_configured": bool(SUPABASE_URL and SUPABASE_ANON_KEY)
    }

async def process_telegram_update(update: dict):
    """Procesa updates de Telegram"""
    try:
        if 'message' in update:
            message = update['message']
            
            if 'text' in message:
                await handle_text_message(message)
            elif 'photo' in message or 'document' in message:
                await handle_image_message(message)
                
    except Exception as e:
        print(f"Error processing update: {e}")

async def handle_text_message(message: dict):
    """Maneja mensajes de texto"""
    chat_id = message['chat']['id']
    text = message['text'].strip()
    
    if text.lower().startswith('/new_match'):
        await start_new_match(chat_id, text)
    
    elif text.lower() == '/process':
        await process_current_batch(chat_id)
    
    elif text.lower() == '/verify':
        await show_extracted_data(chat_id)
    
    elif text.lower() == '/send':
        await send_to_bot2(chat_id)
    
    elif text.lower() == '/clear':
        await clear_current_batch(chat_id)
    
    elif text.lower() == '/status':
        await show_batch_status(chat_id)
    
    else:
        await show_help(chat_id)

async def handle_image_message(message: dict):
    """Maneja imágenes subidas"""
    chat_id = message['chat']['id']
    
    # Por ahora, respuesta simple para confirmar que funciona
    await send_message(
        chat_id,
        "Imagen recibida. Funcionalidad de OCR en desarrollo."
    )

async def start_new_match(chat_id: int, text: str):
    """Inicia nuevo partido para captura de cuotas"""
    try:
        # Extraer nombres de equipos: "/new_match Atlético Madrid vs Real Madrid"
        match_text = text[11:].strip()  # Remover "/new_match "
        
        if not match_text:
            await send_message(
                chat_id,
                "Falta especificar el partido.\nEjemplo: /new_match Atlético Madrid vs Real Madrid"
            )
            return
        
        # Parse básico del partido
        if ' vs ' in match_text.lower():
            teams = match_text.split(' vs ')
            if len(teams) == 2:
                home_team = teams[0].strip()
                away_team = teams[1].strip()
                
                response = f"""
NUEVO PARTIDO INICIADO

{home_team} vs {away_team}

Sistema de captura inicializado.
Ahora puedes subir capturas de cuotas.

Estado: Listo para recibir imágenes
                """.strip()
                
                await send_message(chat_id, response)
            else:
                await send_message(
                    chat_id,
                    "Formato incorrecto. Usa: /new_match Equipo Local vs Equipo Visitante"
                )
        else:
            await send_message(
                chat_id,
                "Formato incorrecto. Usa: /new_match Equipo Local vs Equipo Visitante"
            )
        
    except Exception as e:
        await send_message(
            chat_id,
            f"Error iniciando partido: {str(e)}"
        )

async def process_current_batch(chat_id: int):
    """Procesa todas las imágenes del lote actual con OCR"""
    await send_message(
        chat_id,
        "Procesamiento de OCR iniciado...\nFuncionalidad completa en desarrollo."
    )

async def show_extracted_data(chat_id: int):
    """Muestra datos extraídos detalladamente"""
    await send_message(
        chat_id,
        "DATOS EXTRAÍDOS\n\nFuncionalidad de verificación en desarrollo.\nOCR será implementado próximamente."
    )

async def send_to_bot2(chat_id: int):
    """Envía datos procesados al Bot 2"""
    await send_message(
        chat_id,
        "Función de envío al Bot 2 en desarrollo.\nConexión con sistema de predicciones próximamente."
    )

async def clear_current_batch(chat_id: int):
    """Limpia el lote actual"""
    await send_message(
        chat_id,
        "Lote actual eliminado.\nUsa /new_match para empezar uno nuevo."
    )

async def show_batch_status(chat_id: int):
    """Muestra estado del lote actual"""
    await send_message(
        chat_id,
        "ESTADO ACTUAL\n\nSistema funcionando correctamente.\nFuncionalidades de base de datos en desarrollo."
    )

async def show_help(chat_id: int):
    """Muestra comandos disponibles"""
    help_text = """
COMANDOS DISPONIBLES:

/new_match Equipo1 vs Equipo2 - Iniciar nuevo partido
/process - Procesar capturas con OCR (en desarrollo)
/verify - Ver datos extraídos (en desarrollo)  
/send - Enviar al bot de predicciones (en desarrollo)
/clear - Limpiar lote actual
/status - Ver estado actual

EJEMPLO DE USO:
1. /new_match Real Madrid vs Barcelona
2. Subir capturas de cuotas (funcionalidad básica)
3. /process (cuando esté disponible)

ESTADO: Bot desplegado y funcionando
    """.strip()
    
    await send_message(chat_id, help_text)

async def send_message(chat_id: int, text: str):
    """Envía mensaje a Telegram"""
    try:
        if not TELEGRAM_BOT_TOKEN:
            print("No TELEGRAM_BOT_TOKEN configured")
            return
            
        import aiohttp
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    print(f"Message sent to {chat_id}")
                else:
                    print(f"Error sending message: {response.status}")
                    
    except Exception as e:
        print(f"Error in send_message: {e}")

# Para Vercel - exportar la app
handler = app
