# Envío de datos al Bot 2
import os
import aiohttp
import asyncio
from typing import Dict

class DataSender:
    def __init__(self):
        self.bot2_webhook_url = os.getenv('BOT2_WEBHOOK_URL')
        self.session = None
    
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def send_to_predictions_bot(self, payload: Dict) -> bool:
        """Envía datos procesados al Bot 2"""
        try:
            if not self.bot2_webhook_url:
                print("Bot 2 webhook URL not configured")
                return False
            
            session = await self.get_session()
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer shared_secret_token'
            }
            
            async with session.post(
                self.bot2_webhook_url, 
                json=payload, 
                headers=headers,
                timeout=30
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    print(f"Successfully sent data to Bot 2: {result}")
                    return True
                else:
                    print(f"Error sending to Bot 2: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"Error sending data to predictions bot: {e}")
            return False
Commit message: Add data sender to Bot 2
