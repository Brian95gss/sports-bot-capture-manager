# Bot 1: Capture Manager - Webhook Principal Completo
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

async def handle_image_message(message: dict):
    """Maneja imágenes subidas"""
    chat_id = message['chat']['id']
    
    # Verificar que hay un lote activo
    current_batch = await db.get_current_batch(chat_id)
    if not current_batch:
        await telegram.send_message(
            chat_id,
            "Primero inicia un partido con /new_match Equipo1 vs Equipo2"
        )
        return
    
    # Obtener archivo de imagen
    if 'photo' in message:
        photo = message['photo'][-1]
        file_id = photo['file_id']
        await telegram.send_message(
            chat_id,
            "Imagen recibida (comprimida). Para mejor OCR, envía como 'archivo'."
        )
    elif 'document' in message:
        document = message['document']
        if document['mime_type'].startswith('image/'):
            file_id = document['file_id']
        else:
            await telegram.send_message(chat_id, "El archivo debe ser una imagen.")
            return
    
    try:
        image_data = await telegram.download_file(file_id)
        batch_id = current_batch['id']
        await db.add_image_to_batch(batch_id, image_data, file_id)
        
        updated_batch = await db.get_current_batch(chat_id)
        images_count = len(updated_batch['images'])
        
        status_msg = f"Imagen {images_count}/10 recibida\n"
        status_msg += f"{updated_batch['match_info']['home_team']} vs {updated_batch['match_info']['away_team']}\n\n"
        
        if images_count >= 5:
            status_msg += "Usa /process cuando tengas todas las capturas"
        else:
            status_msg += "Sigue subiendo capturas..."
        
        await telegram.send_message(chat_id, status_msg)
        
    except Exception as e:
        await telegram.send_message(
            chat_id,
            f"Error procesando imagen: {str(e)}"
        )

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

async def process_current_batch(chat_id: int):
    """Procesa todas las imágenes del lote actual con OCR"""
    try:
        current_batch = await db.get_current_batch(chat_id)
        if not current_batch:
            await telegram.send_message(chat_id, "No hay lote activo.")
            return
        
        if not current_batch['images']:
            await telegram.send_message(chat_id, "No hay imágenes para procesar.")
            return
        
        total_images = len(current_batch['images'])
        await telegram.send_message(
            chat_id,
            f"Procesando {total_images} imágenes con OCR...\nEsto puede tardar 1-2 minutos."
        )
        
        from lib.image_processor import ImageProcessor
        image_processor = ImageProcessor()
        
        extracted_data = {}
        
        for i, image_info in enumerate(current_batch['images'], 1):
            await telegram.send_message(
                chat_id,
                f"Procesando imagen {i}/{total_images}..."
            )
            
            image_data = await db.get_image_data(image_info['filename'])
            odds_data = await image_processor.extract_odds_from_image(image_data)
            
            if odds_data:
                extracted_data.update(odds_data)
        
        await db.save_extracted_data(current_batch['id'], extracted_data)
        
        summary = format_extraction_summary(extracted_data)
        
        result_msg = "PROCESAMIENTO COMPLETADO\n\n"
        result_msg += summary + "\n\n"
        result_msg += "Usa /verify para ver detalles completos\n"
        result_msg += "Usa /send para enviar al bot de predicciones"
        
        await telegram.send_message(chat_id, result_msg)
        
    except Exception as e:
        await telegram.send_message(
            chat_id,
            f"Error procesando lote: {str(e)}"
        )

def format_extraction_summary(data: dict) -> str:
    """Formatea resumen de datos extraídos"""
    summary_lines = []
    
    if '1x2' in data:
        odds_1x2 = data['1x2']
        summary_lines.append(
            f"1X2: Local ({odds_1x2.get('home', '?')}), "
            f"Empate ({odds_1x2.get('draw', '?')}), "
            f"Visitante ({odds_1x2.get('away', '?')})"
        )
    
    if 'over_under' in data:
        ou = data['over_under']
        summary_lines.append(
            f"O/U 2.5: Más ({ou.get('over_2_5', '?')}), "
            f"Menos ({ou.get('under_2_5', '?')})"
        )
    
    if 'btts' in data:
        btts = data['btts']
        summary_lines.append(
            f"BTTS: Sí ({btts.get('yes', '?')}), "
            f"No ({btts.get('no', '?')})"
        )
    
    if 'corners' in data:
        corners = data['corners']
        summary_lines.append(
            f"Corners: +10 ({corners.get('over_10', '?')})"
        )
    
    if 'players' in data:
        players = data['players']
        player_count = len(players)
        summary_lines.append(f"Jugadores: {player_count} detectados")
    
    return '\n'.join(summary_lines) if summary_lines else "No se pudieron extraer datos"

async def show_extracted_data(chat_id: int):
    """Muestra datos extraídos detalladamente"""
    current_batch = await db.get_current_batch(chat_id)
    if not current_batch or not current_batch.get('extracted_data'):
        await telegram.send_message(
            chat_id,
            "No hay datos extraídos. Usa /process primero."
        )
        return
    
    data = current_batch['extracted_data']
    match_info = current_batch['match_info']
    
    detailed_message = f"""
DATOS EXTRAÍDOS - {match_info['home_team']} vs {match_info['away_team']}

RESULTADO FINAL (1X2):
• {match_info['home_team']}: {data.get('1x2', {}).get('home', 'No detectado')}
• Empate: {data.get('1x2', {}).get('draw', 'No detectado')}
• {match_info['away_team']}: {data.get('1x2', {}).get('away', 'No detectado')}

TOTAL DE GOLES:
• Más de 2.5: {data.get('over_under', {}).get('over_2_5', 'No detectado')}
• Menos de 2.5: {data.get('over_under', {}).get('under_2_5', 'No detectado')}

AMBOS EQUIPOS ANOTAN:
• Sí: {data.get('btts', {}).get('yes', 'No detectado')}
• No: {data.get('btts', {}).get('no', 'No detectado')}

CORNERS:
• Más de 10: {data.get('corners', {}).get('over_10', 'No detectado')}
    """.strip()
    
    if 'players' in data and data['players']:
        detailed_message += "\n\nJUGADORES PRINCIPALES:"
        for player_name, player_data in data['players'].items():
            detailed_message += f"\n• {player_name}:"
            if 'goal' in player_data:
                detailed_message += f" Gol ({player_data['goal']})"
    
    detailed_message += "\n\n¿Todo correcto? Usa /send para enviar al bot de predicciones"
    
    await telegram.send_message(chat_id, detailed_message)

async def send_to_bot2(chat_id: int):
    """Envía datos procesados al Bot 2"""
    try:
        current_batch = await db.get_current_batch(chat_id)
        if not current_batch or not current_batch.get('extracted_data'):
            await telegram.send_message(
                chat_id,
                "No hay datos para enviar. Usa /process primero."
            )
            return
        
        from api.data_sender import DataSender
        data_sender = DataSender()
        
        payload = {
            'match_info': current_batch['match_info'],
            'odds_data': current_batch['extracted_data'],
            'timestamp': current_batch['created_at'],
            'source': 'capture_manager_bot'
        }
        
        success = await data_sender.send_to_predictions_bot(payload)
        
        if success:
            await db.mark_batch_as_sent(current_batch['id'])
            
            success_msg = "DATOS ENVIADOS EXITOSAMENTE AL BOT DE PREDICCIONES\n\n"
            success_msg += f"{current_batch['match_info']['home_team']} vs {current_batch['match_info']['away_team']}\n"
            success_msg += "Datos procesados y transferidos\n\n"
            success_msg += "El bot de predicciones comenzará el análisis automáticamente.\n"
            success_msg += "Los tips se enviarán a los suscriptores cuando estén listos."
            
            await telegram.send_message(chat_id, success_msg)
        else:
            await telegram.send_message(
                chat_id,
                "Error enviando datos al bot de predicciones. Intenta nuevamente."
            )
            
    except Exception as e:
        await telegram.send_message(
            chat_id,
            f"Error enviando datos: {str(e)}"
        )

async def clear_current_batch(chat_id: int):
    """Limpia el lote actual"""
    try:
        await db.clear_current_batch(chat_id)
        await telegram.send_message(
            chat_id,
            "Lote actual eliminado.\nUsa /new_match para empezar uno nuevo."
        )
    except Exception as e:
        await telegram.send_message(
            chat_id,
            f"Error limpiando lote: {str(e)}"
        )

async def show_batch_status(chat_id: int):
    """Muestra estado del lote actual"""
    current_batch = await db.get_current_batch(chat_id)
    
    if not current_batch:
        await telegram.send_message(
            chat_id,
            "ESTADO ACTUAL\n\nNo hay lote activo\nUsa /new_match Equipo1 vs Equipo2 para empezar"
        )
        return
    
    match_info = current_batch['match_info']
    images_count = len(current_batch['images'])
    has_extracted = bool(current_batch.get('extracted_data'))
    is_sent = current_batch.get('sent_to_bot2', False)
    
    status_message = f"""
ESTADO ACTUAL

PARTIDO: {match_info['home_team']} vs {match_info['away_team']}
Fecha: {match_info['match_date']}
Liga: {match_info['league']}

CAPTURAS: {images_count}/10 recibidas
PROCESADAS: {'Sí' if has_extracted else 'No'}
ENVIADAS: {'Sí' if is_sent else 'No'}

PRÓXIMO PASO:
{get_next_step_message(images_count, has_extracted, is_sent)}
    """.strip()
    
    await telegram.send_message(chat_id, status_message)

def get_next_step_message(images_count: int, has_extracted: bool, is_sent: bool) -> str:
    """Determina el siguiente paso"""
    if is_sent:
        return "Proceso completado. Usa /new_match para otro partido."
    elif has_extracted:
        return "Usa /send para enviar al bot de predicciones"
    elif images_count >= 5:
        return "Usa /process para extraer cuotas con OCR"
    else:
        return "Sigue subiendo capturas de cuotas"

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
