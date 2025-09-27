# Bot 1: Capture Manager - Webhook Principal
import os
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from lib.telegram_client import TelegramClient
from lib.database import Database
from lib.match_identifier import MatchIdentifier

app = FastAPI(title="Sports Betting Bot - Capture Manager", version="1.0.0")

# Inicializar servicios
telegram = TelegramClient()
db = Database()
match_identifier = MatchIdentifier()

@app.post("/api/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recibe updates de Telegram"""
    try:
        update = await request.json()
        
        # Solo procesar si es del usuario autorizado
        if not telegram.is_authorized_user(update):
            return {"ok": True, "message": "Unauthorized"}
        
        background_tasks.add_task(process_telegram_update, update)
        return {"ok": True}
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

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

async def start_new_match(chat_id: int, text: str):
    """Inicia nuevo partido para captura de cuotas"""
    try:
        # Extraer nombres de equipos: "/new_match Atlético Madrid vs Real Madrid"
        match_text = text[11:].strip()  # Remover "/new_match "
        
        if not match_text:
            await telegram.send_message(
                chat_id,
                "Falta especificar el partido.\nEjemplo: /new_match Atlético Madrid vs Real Madrid"
            )
            return
        
        # Identificar partido
        match_info = await match_identifier.identify_match(match_text)
        
        if not match_info:
            await telegram.send_message(
                chat_id, 
                f"No pude identificar el partido: '{match_text}'\nFormato correcto: /new_match Equipo Local vs Equipo Visitante"
            )
            return
        
        # Inicializar nuevo lote de capturas
        batch_id = await db.start_new_batch(chat_id, match_info)
        
        response = f"""
NUEVO PARTIDO INICIADO

{match_info['home_team']} vs {match_info['away_team']}
{match_info['match_date']}
{match_info['league']}

Ahora puedes subir hasta 10 capturas de cuotas.
Envía como 'archivo' para mejor calidad OCR.

Estado: 0/10 capturas recibidas
        """.strip()
        
        await telegram.send_message(chat_id, response)
        
    except Exception as e:
        await telegram.send_message(
            chat_id,
            f"Error iniciando partido: {str(e)}"
        )

async def show_help(chat_id: int):
    """Muestra comandos disponibles"""
    help_text = """
COMANDOS DISPONIBLES:

/new_match Equipo1 vs Equipo2 - Iniciar nuevo partido
/process - Procesar capturas actuales con OCR
/verify - Ver datos extraídos
/send - Enviar al bot de predicciones
/clear - Limpiar lote actual
/status - Ver estado actual

EJEMPLO DE USO:
1. /new_match Real Madrid vs Barcelona
2. Subir 10 capturas de cuotas
3. /process (para extraer cuotas con OCR)
4. /verify (para revisar datos)
5. /send (para enviar al bot de predicciones)
    """.strip()
    
    await telegram.send_message(chat_id, help_text)

@app.get("/api/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "Capture Manager Bot",
        "version": "1.0.0"
    }
Commit message: Add main webhook handler
