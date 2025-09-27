# Cliente de Telegram para Bot 1
import os
import aiohttp
import asyncio
from typing import Dict, List, Optional

class TelegramClient:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.authorized_user_id = int(os.getenv('AUTHORIZED_USER_ID', 0))
        self.session = None
    
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def is_authorized_user(self, update: Dict) -> bool:
        """Verifica si el usuario está autorizado"""
        try:
            if 'message' in update:
                user_id = update['message']['from']['id']
            elif 'callback_query' in update:
                user_id = update['callback_query']['from']['id']
            else:
                return False
            
            return user_id == self.authorized_user_id
        except:
            return False
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        """Envía mensaje a Telegram"""
        session = await self.get_session()
        
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            async with session.post(f"{self.base_url}/sendMessage", json=payload) as response:
                return await response.json()
        except Exception as e:
            print(f"Error sending message: {e}")
            return None
    
    async def download_file(self, file_id: str) -> bytes:
        """Descarga archivo de Telegram"""
        session = await self.get_session()
        
        try:
            # Obtener file_path
            async with session.get(f"{self.base_url}/getFile?file_id={file_id}") as response:
                file_info = await response.json()
                
                if not file_info.get('ok'):
                    raise Exception(f"Error getting file info: {file_info}")
                
                file_path = file_info['result']['file_path']
            
            # Descargar archivo
            download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            async with session.get(download_url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    raise Exception(f"Error downloading file: {response.status}")
                    
        except Exception as e:
            print(f"Error downloading file: {e}")
            raise e
Commit message: Add Telegram client
