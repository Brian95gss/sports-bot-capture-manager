import os
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import aiohttp
import sys
sys.path.append('lib')

# Importar tus módulos
from lib.database import Database
from lib.image_processor import ImageProcessor
from lib.telegram_client import TelegramClient
from lib.data_sender import DataSender

app = FastAPI(title="Sports Capture Manager Bot")

# Instanciar servicios
db = Database()
processor = ImageProcessor()
telegram = TelegramClient()
sender = DataSender()

# Variables de configuración
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

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
                print(f"✅ Webhook configured: {result}")
    else:
        print("⚠️ Missing WEBHOOK_URL or BOT_TOKEN")

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "running",
        "bot": "Sports Capture Manager",
        "webhook": f"{WEBHOOK_URL}/webhook" if WEBHOOK_URL else "not configured",
        "version": "2.0"
    }

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """Recibe actualizaciones de Telegram"""
    try:
        update = await request.json()
        
        # Verificar autorización
        if not telegram.is_authorized_user(update):
            return {"ok": True}
        
        # Procesar en background para responder rápido a Telegram
        background_tasks.add_task(process_update, update)
        return {"ok": True}
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=200)

async def process_update(update: dict):
    """Procesa las actualizaciones"""
    try:
        if 'message' not in update:
            return
        
        message = update['message']
        chat_id = message['chat']['id']
        
        # Comandos de texto
        if 'text' in message:
            await process_command(chat_id, message['text'])
        
        # Imágenes
        elif 'photo' in message:
            await process_photo(chat_id, message)
                    
    except Exception as e:
        print(f"❌ Error processing update: {e}")
        await telegram.send_message(chat_id, f"Error: {str(e)}")

async def process_command(chat_id: int, text: str):
    """Procesa comandos de texto"""
    try:
        text = text.strip()
        
        if text.startswith('/start'):
            await telegram.send_message(
                chat_id,
                "🤖 <b>Bot de Captura iniciado</b>\n\n"
                "Usa /help para ver comandos disponibles."
            )
        
        elif text.startswith('/new_match'):
            match_text = text[11:].strip()
            
            if not match_text or ' vs ' not in match_text.lower():
                await telegram.send_message(
                    chat_id,
                    "❌ Formato incorrecto\n\n"
                    "Uso: <code>/new_match Equipo1 vs Equipo2</code>"
                )
                return
            
            # Parsear equipos
            teams = match_text.lower().split(' vs ')
            match_info = {
                'home_team': teams[0].strip().title(),
                'away_team': teams[1].strip().title(),
                'started_at': None
            }
            
            # Crear nuevo lote en DB
            batch_id = await db.start_new_batch(chat_id, match_info)
            
            await telegram.send_message(
                chat_id,
                f"✅ <b>Partido iniciado</b>\n\n"
                f"🏟 {match_info['home_team']} vs {match_info['away_team']}\n"
                f"📸 Ahora envía las capturas de pantalla"
            )
        
        elif text == '/status':
            batch = await db.get_current_batch(chat_id)
            
            if not batch:
                await telegram.send_message(
                    chat_id,
                    "ℹ️ No hay partido activo\n\n"
                    "Usa /new_match para iniciar uno"
                )
                return
            
            match_info = batch.get('match_info', {})
            images_count = len(batch.get('images', []))
            
            msg = (
                f"📊 <b>Estado actual</b>\n\n"
                f"🏟 {match_info.get('home_team', 'N/A')} vs {match_info.get('away_team', 'N/A')}\n"
                f"📸 Capturas: {images_count}\n"
                f"🆔 Batch ID: <code>{batch['id'][:8]}...</code>"
            )
            
            await telegram.send_message(chat_id, msg)
        
        elif text == '/clear':
            await db.clear_current_batch(chat_id)
            await telegram.send_message(chat_id, "✅ Lote eliminado correctamente")
        
        elif text == '/process':
            # Procesar lote actual
            await process_current_batch(chat_id)
        
        elif text == '/help':
            help_text = """🤖 <b>COMANDOS DISPONIBLES</b>

<b>/new_match</b> Equipo1 vs Equipo2
Inicia un nuevo partido

<b>/status</b>
Ver estado del partido actual

<b>/process</b>
Procesar capturas y enviar al Bot 2

<b>/clear</b>
Eliminar lote actual

<b>/help</b>
Mostrar esta ayuda

📸 Después de /new_match, envía las capturas de pantalla de bet365"""
            
            await telegram.send_message(chat_id, help_text)
        
        else:
            await telegram.send_message(
                chat_id,
                f"❌ Comando no reconocido: <code>{text}</code>\n\n"
                "Usa /help para ver comandos disponibles"
            )
                
    except Exception as e:
        print(f"❌ Error processing command: {e}")
        await telegram.send_message(chat_id, f"Error: {str(e)}")

async def process_photo(chat_id: int, message: dict):
    """Procesa imágenes recibidas"""
    try:
        # Verificar que hay un batch activo
        batch = await db.get_current_batch(chat_id)
        
        if not batch:
            await telegram.send_message(
                chat_id,
                "⚠️ <b>No hay partido activo</b>\n\n"
                "Primero inicia un partido con /new_match"
            )
            return
        
        # Obtener la imagen de mayor calidad
        photo = message['photo'][-1]
        file_id = photo['file_id']
        
        await telegram.send_message(chat_id, "⏳ Descargando imagen...")
        
        # Descargar imagen
        image_data = await telegram.download_file(file_id)
        
        # Guardar en Supabase
        await db.add_image_to_batch(batch['id'], image_data, file_id)
        
        # Contar imágenes
        updated_batch = await db.get_current_batch(chat_id)
        images_count = len(updated_batch.get('images', []))
        
        await telegram.send_message(
            chat_id,
            f"✅ <b>Captura {images_count} guardada</b>\n\n"
            f"Envía más capturas o usa /process para analizar"
        )
        
    except Exception as e:
        print(f"❌ Error processing photo: {e}")
        await telegram.send_message(chat_id, f"Error procesando imagen: {str(e)}")

async def process_current_batch(chat_id: int):
    """Procesa el lote actual con OCR y envía al Bot 2"""
    try:
        batch = await db.get_current_batch(chat_id)
        
        if not batch:
            await telegram.send_message(chat_id, "❌ No hay lote activo")
            return
        
        images = batch.get('images', [])
        
        if not images:
            await telegram.send_message(chat_id, "❌ No hay imágenes en el lote")
            return
        
        await telegram.send_message(
            chat_id,
            f"🔄 <b>Procesando {len(images)} imágenes...</b>\n\n"
            "Esto puede tardar unos momentos"
        )
        
        # Procesar cada imagen con OCR
        all_odds_data = {}
        
        for i, image in enumerate(images):
            try:
                # Descargar imagen
                image_data = await db.get_image_data(image['filename'])
                
                # Extraer cuotas
                odds = await processor.extract_odds_from_image(image_data)
                
                # Agregar a datos consolidados
                for key, value in odds.items():
                    if key not in all_odds_data:
                        all_odds_data[key] = value
                    elif isinstance(value, dict):
                        all_odds_data[key].update(value)
                
                await telegram.send_message(
                    chat_id,
                    f"✓ Imagen {i+1}/{len(images)} procesada"
                )
                
            except Exception as e:
                print(f"Error processing image {i}: {e}")
                continue
        
        # Guardar datos extraídos
        await db.save_extracted_data(batch['id'], all_odds_data)
        
        # Generar resumen
        summary = await processor.get_summary_for_analysis(all_odds_data)
        
        await telegram.send_message(
            chat_id,
            f"📊 <b>Datos extraídos:</b>\n\n{summary}"
        )
        
        # Enviar al Bot 2
        await telegram.send_message(chat_id, "📤 Enviando al Bot de Predicciones...")
        
        payload = {
            'batch_id': batch['id'],
            'match_info': batch['match_info'],
            'odds_data': all_odds_data,
            'summary': summary,
            'timestamp': batch['created_at']
        }
        
        success = await sender.send_to_predictions_bot(payload)
        
        if success:
            await db.mark_batch_as_sent(batch['id'])
            await telegram.send_message(
                chat_id,
                "✅ <b>Datos enviados al Bot 2</b>\n\n"
                "Usa /new_match para iniciar otro partido"
            )
        else:
            await telegram.send_message(
                chat_id,
                "⚠️ Error enviando al Bot 2\n\n"
                "Los datos se guardaron localmente"
            )
        
    except Exception as e:
        print(f"❌ Error processing batch: {e}")
        await telegram.send_message(chat_id, f"Error: {str(e)}")

# Para Render
handler = app
