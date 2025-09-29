# Cliente Supabase para Bot 1
import os
from datetime import datetime
from typing import Dict, List, Optional
from supabase import create_client, Client
import json
import uuid

class Database:
    def __init__(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_ANON_KEY')
        self.supabase: Client = create_client(url, key)
    
    async def start_new_batch(self, chat_id: int, match_info: Dict) -> str:
        """Inicia nuevo lote de capturas"""
        try:
            # Limpiar lote anterior si existe
            await self.clear_current_batch(chat_id)
            
            # Crear nuevo lote
            batch_record = {
                'id': str(uuid.uuid4()),
                'chat_id': chat_id,
                'match_info': match_info,
                'images': [],
                'extracted_data': {},
                'sent_to_bot2': False,
                'created_at': datetime.utcnow().isoformat()
            }
            
            result = self.supabase.table('capture_batches').insert(batch_record).execute()
            return result.data[0]['id']
            
        except Exception as e:
            print(f"Error starting new batch: {e}")
            raise e
    
    async def get_current_batch(self, chat_id: int) -> Optional[Dict]:
        """Obtiene lote actual del usuario"""
        try:
            result = self.supabase.table('capture_batches')\
                .select('*')\
                .eq('chat_id', chat_id)\
                .eq('sent_to_bot2', False)\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            print(f"Error getting current batch: {e}")
            return None
    
    async def add_image_to_batch(self, batch_id: str, image_data: bytes, file_id: str):
        """Agrega imagen al lote"""
        try:
            # Subir imagen a Supabase Storage
            image_filename = f"batch_{batch_id}_{file_id}_{datetime.utcnow().timestamp()}.jpg"
            
            storage_result = self.supabase.storage.from_('capture_images').upload(
                image_filename, 
                image_data,
                file_options={"content-type": "image/jpeg"}
            )
            
            if storage_result.get('error'):
                raise Exception(f"Storage error: {storage_result['error']}")
            
            # Obtener lote actual
            current_batch = self.supabase.table('capture_batches').select('*').eq('id', batch_id).single().execute()
            
            # Agregar imagen a la lista
            images = current_batch.data.get('images', [])
            images.append({
                'id': file_id,
                'filename': image_filename,
                'uploaded_at': datetime.utcnow().isoformat(),
                'processed': False
            })
            
            # Actualizar lote
            self.supabase.table('capture_batches').update({'images': images}).eq('id', batch_id).execute()
            
        except Exception as e:
            print(f"Error adding image to batch: {e}")
            raise e
    
    async def get_image_data(self, filename: str) -> bytes:
        """Obtiene datos de imagen desde Storage"""
        try:
            result = self.supabase.storage.from_('capture_images').download(filename)
            return result
        except Exception as e:
            print(f"Error getting image data: {e}")
            raise e
    
    async def save_extracted_data(self, batch_id: str, extracted_data: Dict):
        """Guarda datos extraídos por OCR"""
        try:
            self.supabase.table('capture_batches').update({
                'extracted_data': extracted_data,
                'processed_at': datetime.utcnow().isoformat()
            }).eq('id', batch_id).execute()
            
        except Exception as e:
            print(f"Error saving extracted data: {e}")
            raise e
    
    async def mark_batch_as_sent(self, batch_id: str):
        """Marca lote como enviado al Bot 2"""
        try:
            self.supabase.table('capture_batches').update({
                'sent_to_bot2': True,
                'sent_at': datetime.utcnow().isoformat()
            }).eq('id', batch_id).execute()
            
        except Exception as e:
            print(f"Error marking batch as sent: {e}")
            raise e
    
    async def clear_current_batch(self, chat_id: int):
        """Limpia lote actual"""
        try:
            # Obtener lote actual
            current_batch = await self.get_current_batch(chat_id)
            
            if current_batch:
                # Eliminar imágenes del storage
                for image in current_batch.get('images', []):
                    try:
                        self.supabase.storage.from_('capture_images').remove([image['filename']])
                    except:
                        pass  # Ignorar errores de eliminación
                
                # Eliminar registro del lote
                self.supabase.table('capture_batches').delete().eq('id', current_batch['id']).execute()
                
        except Exception as e:
            print(f"Error clearing current batch: {e}")
            raise e
