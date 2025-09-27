# Procesador de imágenes y OCR
import io
import os
from PIL import Image
import cv2
import numpy as np
from typing import Dict, List, Optional
import re

# Importar bibliotecas OCR
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from google.cloud import vision
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False

class ImageProcessor:
    def __init__(self):
        self.ocr_confidence_threshold = 0.7
        
        # Configurar Google Vision si está disponible
        if GOOGLE_VISION_AVAILABLE:
            try:
                self.vision_client = vision.ImageAnnotatorClient()
            except:
                self.vision_client = None
        else:
            self.vision_client = None
    
    async def extract_odds_from_image(self, image_data: bytes) -> Dict:
        """Extrae cuotas de una imagen usando OCR"""
        try:
            # Preprocesar imagen
            processed_image = self.preprocess_image(image_data)
            
            # Extraer texto usando el mejor OCR disponible
            if self.vision_client:
                text_data = await self.extract_text_google_vision(processed_image)
            elif TESSERACT_AVAILABLE:
                text_data = self.extract_text_tesseract(processed_image)
            else:
                # Fallback: análisis básico de imagen
                text_data = [{"text": "OCR no disponible", "confidence": 0.1}]
            
            # Analizar texto extraído para encontrar cuotas
            odds_data = self.parse_odds_from_text(text_data)
            
            return odds_data
            
        except Exception as e:
            print(f"Error extracting odds: {e}")
            return {}
    
    def preprocess_image(self, image_data: bytes) -> np.ndarray:
        """Preprocesa imagen para mejor OCR"""
        try:
            # Convertir bytes a imagen PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convertir a numpy array
            img_array = np.array(image)
            
            # Convertir a escala de grises
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # Aplicar filtros para mejorar OCR
            # 1. Aumentar contraste
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # 2. Reducir ruido
            denoised = cv2.medianBlur(enhanced, 3)
            
            # 3. Aplicar threshold adaptativo
            threshold = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            return threshold
            
        except Exception as e:
            print(f"Error preprocessing image: {e}")
            # Retornar imagen original como fallback
            image = Image.open(io.BytesIO(image_data))
            return np.array(image)
    
    def extract_text_tesseract(self, image: np.ndarray) -> List[Dict]:
        """Extrae texto usando Tesseract OCR"""
        try:
            # Configurar Tesseract para números y texto
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
            
            # Extraer texto con datos detallados
            data = pytesseract.image_to_data(
                image, 
                config=custom_config, 
                output_type=pytesseract.Output.DICT
            )
            
            # Procesar resultados
            text_data = []
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 30:  # Filtrar por confianza mínima
                    text_data.append({
                        'text': data['text'][i],
                        'confidence': int(data['conf'][i]) / 100
                    })
            
            return text_data
            
        except Exception as e:
            print(f"Tesseract OCR error: {e}")
            return []
    
    def parse_odds_from_text(self, text_data: List[Dict]) -> Dict:
        """Analiza texto extraído para encontrar cuotas de apuestas"""
        try:
            # Combinar todo el texto
            full_text = ' '.join([item['text'] for item in text_data if item['text'].strip()])
            
            odds_data = {}
            
            # Buscar diferentes tipos de cuotas
            odds_data['1x2'] = self.extract_1x2_odds(full_text)
            odds_data['over_under'] = self.extract_over_under_odds(full_text)
            odds_data['btts'] = self.extract_btts_odds(full_text)
            odds_data['corners'] = self.extract_corners_odds(full_text)
            odds_data['players'] = self.extract_player_odds(full_text)
            
            # Filtrar resultados vacíos
            return {k: v for k, v in odds_data.items() if v}
            
        except Exception as e:
            print(f"Error parsing odds: {e}")
            return {}
    
    def extract_1x2_odds(self, text: str) -> Dict:
        """Extrae cuotas 1X2 (Local/Empate/Visitante)"""
        try:
            odds_1x2 = {}
            
            # Buscar patrones típicos de 1X2 - tres números decimales seguidos
            pattern = r'(\d{1,2}\.\d{2})\s*(\d{1,2}\.\d{2})\s*(\d{1,2}\.\d{2})'
            matches = re.findall(pattern, text)
            
            for match in matches:
                home, draw, away = match
                home_f, draw_f, away_f = float(home), float(draw), float(away)
                
                # Validar que son cuotas razonables para 1X2
                if (1.01 <= home_f <= 50 and 1.01 <= draw_f <= 10 and 1.01 <= away_f <= 50):
                    # Verificar que las probabilidades suman aproximadamente 100%
                    implied_prob = (1/home_f + 1/draw_f + 1/away_f)
                    if 0.95 <= implied_prob <= 1.20:  # Margen típico de bookmaker
                        odds_1x2 = {
                            'home': home,
                            'draw': draw,
                            'away': away
                        }
                        break
            
            return odds_1x2
            
        except Exception as e:
            print(f"Error extracting 1X2: {e}")
            return {}
    
    def extract_over_under_odds(self, text: str) -> Dict:
        """Extrae cuotas Over/Under goles"""
        try:
            over_under = {}
            
            # Buscar patrones con "2.5" y cuotas cercanas
            patterns = [
                r'(\d{1,2}\.\d{2})\s*.*?2[.,]5.*?(\d{1,2}\.\d{2})',  # Patrón general
                r'Más.*?2[.,]5.*?(\d{1,2}\.\d{2}).*?Menos.*?(\d{1,2}\.\d{2})',  # Español
                r'Over.*?2[.,]5.*?(\d{1,2}\.\d{2}).*?Under.*?(\d{1,2}\.\d{2})'   # Inglés
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    over_2_5, under_2_5 = match.groups()
                    over_f, under_f = float(over_2_5), float(under_2_5)
                    
                    # Validar cuotas típicas de O/U
                    if 1.01 <= over_f <= 10 and 1.01 <= under_f <= 10:
                        over_under = {
                            'over_2_5': over_2_5,
                            'under_2_5': under_2_5
                        }
                        break
            
            return over_under
            
        except Exception as e:
            print(f"Error extracting Over/Under: {e}")
            return {}
    
    def extract_btts_odds(self, text: str) -> Dict:
        """Extrae cuotas Both Teams To Score"""
        try:
            btts = {}
            
            # Palabras clave para BTTS
            btts_keywords = ['ambos', 'both', 'equipos', 'teams', 'anotan', 'score']
            
            if any(keyword.lower() in text.lower() for keyword in btts_keywords):
                # Buscar patrón Sí/No cerca de las palabras clave
                patterns = [
                    r'Sí\s*(\d{1,2}\.\d{2}).*?No\s*(\d{1,2}\.\d{2})',
                    r'Yes\s*(\d{1,2}\.\d{2}).*?No\s*(\d{1,2}\.\d{2})',
                    r'(\d{1,2}\.\d{2})\s*.*?(\d{1,2}\.\d{2})'  # Patrón general
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        yes_odds, no_odds = match.groups()
                        yes_f, no_f = float(yes_odds), float(no_odds)
                        
                        # BTTS típicamente tiene cuotas entre 1.30 y 4.00
                        if 1.30 <= yes_f <= 4.00 and 1.30 <= no_f <= 4.00:
                            btts = {
                                'yes': yes_odds,
                                'no': no_odds
                            }
                            break
            
            return btts
            
        except Exception as e:
            print(f"Error extracting BTTS: {e}")
            return {}
    
    def extract_corners_odds(self, text: str) -> Dict:
        """Extrae cuotas de corners"""
        try:
            corners = {}
            
            # Palabras clave para corners
            corner_keywords = ['corner', 'esquina', 'tiros', 'saque']
            
            if any(keyword.lower() in text.lower() for keyword in corner_keywords):
                # Buscar patrones específicos para corners
                patterns = [
                    r'(\d{1,2})\s*.*?(\d{1,2}\.\d{2})',  # Número + cuota
                    r'Más.*?(\d{1,2}).*?(\d{1,2}\.\d{2})',  # "Más de X"
                    r'Over.*?(\d{1,2}).*?(\d{1,2}\.\d{2})'   # "Over X"
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for number, odds in matches:
                        num = int(number)
                        if 8 <= num <= 15:  # Rango típico de corners
                            corners[f'over_{number}'] = odds
            
            return corners
            
        except Exception as e:
            print(f"Error extracting corners: {e}")
            return {}
    
    def extract_player_odds(self, text: str) -> Dict:
        """Extrae cuotas de jugadores"""
        try:
            players = {}
            
            # Lista de jugadores conocidos
            known_players = [
                'Mbappé', 'Mbappe', 'Kylian', 'Vinicius', 'Benzema', 'Bellingham',
                'Griezmann', 'Morata', 'Haaland', 'Lewandowski', 'Messi', 'Neymar'
            ]
            
            for player in known_players:
                if player.lower() in text.lower():
                    # Buscar cuotas cerca del nombre del jugador
                    pattern = f'{player}.*?(\\d{{1,2}}\\.\\d{{2}})'
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    
                    if matches:
                        odds = matches[0]
                        odds_f = float(odds)
                        
                        # Rango razonable para cuotas de jugador
                        if 1.20 <= odds_f <= 20.00:
                            players[player] = {
                                'goal': odds
                            }
                            break
            
            return players
            
        except Exception as e:
            print(f"Error extracting player odds: {e}")
            return {}
Commit message: Add image processor with OCR
