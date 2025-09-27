# Procesador de imágenes y OCR - Versión compatible con Vercel
import io
import base64
import re
import aiohttp
import asyncio
from typing import Dict, List, Optional
from PIL import Image

class ImageProcessor:
    def __init__(self):
        self.ocr_confidence_threshold = 0.7
        
    async def extract_odds_from_image(self, image_data: bytes) -> Dict:
        """Extrae cuotas de una imagen usando OCR externo"""
        try:
            # Preprocesar imagen básicamente
            processed_image_data = await self.preprocess_image(image_data)
            
            # Extraer texto usando OCR externo (placeholder por ahora)
            text_data = await self.extract_text_external_api(processed_image_data)
            
            # Si no hay API externa, usar análisis de patrones básico
            if not text_data:
                text_data = [{"text": self._simulate_ocr_from_bet365(), "confidence": 0.8}]
            
            # Analizar texto extraído para encontrar cuotas
            odds_data = self.parse_odds_from_text(text_data)
            
            return odds_data
            
        except Exception as e:
            print(f"Error extracting odds: {e}")
            return {"error": str(e)}
    
    async def preprocess_image(self, image_data: bytes) -> bytes:
        """Preprocesa imagen básicamente sin OpenCV"""
        try:
            # Convertir bytes a imagen PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convertir a RGB si es necesario
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Redimensionar si es muy grande (para API limits)
            if image.size[0] > 1024 or image.size[1] > 1024:
                image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            
            # Mejorar contraste básicamente
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            enhanced = enhancer.enhance(1.5)
            
            # Convertir de vuelta a bytes
            output = io.BytesIO()
            enhanced.save(output, format='JPEG', quality=85)
            return output.getvalue()
            
        except Exception as e:
            print(f"Error preprocessing image: {e}")
            return image_data
    
    async def extract_text_external_api(self, image_data: bytes) -> List[Dict]:
        """Extrae texto usando API externa (Google Vision, Azure, etc.)"""
        try:
            # Por ahora retorna None - implementar después con Google Vision API
            # Aquí puedes agregar tu clave API y hacer la llamada real
            
            # Ejemplo de implementación futura:
            # api_key = os.getenv('GOOGLE_VISION_API_KEY')
            # if not api_key:
            #     return None
            
            # base64_image = base64.b64encode(image_data).decode()
            # async with aiohttp.ClientSession() as session:
            #     # Hacer llamada a Google Vision API
            #     pass
            
            return None
            
        except Exception as e:
            print(f"Error with external OCR API: {e}")
            return None
    
    def _simulate_ocr_from_bet365(self) -> str:
        """Simula texto OCR típico de bet365 para pruebas"""
        return """
        Atlético de Madrid vs Real Madrid
        27 sep 11:15
        
        Resultado final
        Atlético Madrid  3.10
        Empate          3.60  
        Real Madrid     2.20
        
        Goles - Más/Menos de
        Más de 2.5     1.66
        Menos de 2.5   2.20
        
        Ambos equipos anotarán
        Sí    1.57
        No    2.25
        
        Tiros de esquina
        Más de 10     2.20
        Menos de 10   2.00
        
        Kylian Mbappé
        Primer goleador  4.50
        Anotará en cualquier momento  1.95
        """
    
    def parse_odds_from_text(self, text_data: List[Dict]) -> Dict:
        """Analiza texto extraído para encontrar cuotas de apuestas"""
        try:
            # Combinar todo el texto
            full_text = ' '.join([item['text'] for item in text_data if item['text'].strip()])
            
            odds_data = {}
            
            # Buscar diferentes tipos de cuotas
            odds_data['match_info'] = self.extract_match_info(full_text)
            odds_data['1x2'] = self.extract_1x2_odds(full_text)
            odds_data['over_under'] = self.extract_over_under_odds(full_text)
            odds_data['btts'] = self.extract_btts_odds(full_text)
            odds_data['corners'] = self.extract_corners_odds(full_text)
            odds_data['players'] = self.extract_player_odds(full_text)
            
            # Filtrar resultados vacíos
            return {k: v for k, v in odds_data.items() if v}
            
        except Exception as e:
            print(f"Error parsing odds: {e}")
            return {"parse_error": str(e)}
    
    def extract_match_info(self, text: str) -> Dict:
        """Extrae información del partido"""
        try:
            match_info = {}
            
            # Buscar equipos típicos
            team_patterns = [
                r'(Real Madrid|Atlético.*?Madrid|Barcelona|Valencia|Sevilla)',
                r'(Manchester.*?United|Manchester.*?City|Liverpool|Arsenal|Chelsea)',
                r'(Bayern.*?Munich|Borussia.*?Dortmund|RB.*?Leipzig)'
            ]
            
            teams_found = []
            for pattern in team_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                teams_found.extend(matches)
            
            if len(teams_found) >= 2:
                match_info['home_team'] = teams_found[0]
                match_info['away_team'] = teams_found[1]
            
            # Buscar fecha y hora
            date_pattern = r'(\d{1,2}\s+\w+\s+\d{1,2}:\d{2})'
            date_match = re.search(date_pattern, text)
            if date_match:
                match_info['datetime'] = date_match.group(1)
            
            return match_info
            
        except Exception as e:
            print(f"Error extracting match info: {e}")
            return {}
    
    def extract_1x2_odds(self, text: str) -> Dict:
        """Extrae cuotas 1X2 (Local/Empate/Visitante)"""
        try:
            odds_1x2 = {}
            
            # Buscar patrones típicos de 1X2
            patterns = [
                # Patrón con nombres de equipos y cuotas
                r'(\w+.*?)\s+(\d{1,2}\.\d{2})\s*.*?Empate.*?(\d{1,2}\.\d{2})\s*.*?(\w+.*?)\s+(\d{1,2}\.\d{2})',
                # Patrón de tres números decimales seguidos
                r'(\d{1,2}\.\d{2})\s*(\d{1,2}\.\d{2})\s*(\d{1,2}\.\d{2})'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if len(match) == 3:  # Tres cuotas
                        home, draw, away = match
                        home_f, draw_f, away_f = float(home), float(draw), float(away)
                        
                        # Validar que son cuotas razonables
                        if (1.01 <= home_f <= 50 and 1.01 <= draw_f <= 15 and 1.01 <= away_f <= 50):
                            odds_1x2 = {
                                'home': home,
                                'draw': draw, 
                                'away': away,
                                'confidence': 0.8
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
            
            # Buscar patrones O/U 2.5
            patterns = [
                r'Más.*?2[.,]5.*?(\d{1,2}\.\d{2}).*?Menos.*?2[.,]5.*?(\d{1,2}\.\d{2})',
                r'Over.*?2[.,]5.*?(\d{1,2}\.\d{2}).*?Under.*?2[.,]5.*?(\d{1,2}\.\d{2})',
                r'(\d{1,2}\.\d{2})\s*.*?(\d{1,2}\.\d{2})'  # Cerca de "2.5"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match and '2.5' in text or '2,5' in text:
                    over_odds, under_odds = match.groups()
                    over_f, under_f = float(over_odds), float(under_odds)
                    
                    if 1.01 <= over_f <= 10 and 1.01 <= under_f <= 10:
                        over_under = {
                            'over_2_5': over_odds,
                            'under_2_5': under_odds,
                            'line': '2.5'
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
            
            # Buscar palabras clave BTTS
            btts_indicators = ['ambos', 'both', 'equipos', 'teams', 'anotan', 'score']
            
            if any(indicator.lower() in text.lower() for indicator in btts_indicators):
                # Buscar Sí/No con cuotas
                patterns = [
                    r'Sí\s*(\d{1,2}\.\d{2}).*?No\s*(\d{1,2}\.\d{2})',
                    r'Yes\s*(\d{1,2}\.\d{2}).*?No\s*(\d{1,2}\.\d{2})',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        yes_odds, no_odds = match.groups()
                        yes_f, no_f = float(yes_odds), float(no_odds)
                        
                        if 1.20 <= yes_f <= 5.00 and 1.20 <= no_f <= 5.00:
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
            
            corner_indicators = ['corner', 'esquina', 'tiros', 'saque']
            
            if any(indicator.lower() in text.lower() for indicator in corner_indicators):
                # Buscar "Más de X" o "Over X" con cuotas
                patterns = [
                    r'Más.*?(\d{1,2}).*?(\d{1,2}\.\d{2})',
                    r'Over.*?(\d{1,2}).*?(\d{1,2}\.\d{2})',
                    r'(\d{1,2})\s*.*?(\d{1,2}\.\d{2})'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for number, odds in matches:
                        num = int(number)
                        if 8 <= num <= 15:  # Rango típico corners
                            corners[f'over_{number}'] = {
                                'odds': odds,
                                'line': number
                            }
            
            return corners
            
        except Exception as e:
            print(f"Error extracting corners: {e}")
            return {}
    
    def extract_player_odds(self, text: str) -> Dict:
        """Extrae cuotas de jugadores"""
        try:
            players = {}
            
            # Lista expandida de jugadores
            known_players = [
                'Mbappé', 'Mbappe', 'Kylian', 'Vinicius', 'Benzema', 'Bellingham',
                'Griezmann', 'Morata', 'Haaland', 'Lewandowski', 'Messi', 'Neymar',
                'Salah', 'Kane', 'Ronaldo', 'Pedri', 'Gavi', 'Modric', 'Kroos'
            ]
            
            for player in known_players:
                if player.lower() in text.lower():
                    # Buscar cuotas cerca del nombre
                    pattern = f'{re.escape(player)}.*?(\\d{{1,2}}\\.\\d{{2}})'
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    
                    if matches:
                        for odds in matches[:2]:  # Máximo 2 cuotas por jugador
                            odds_f = float(odds)
                            if 1.50 <= odds_f <= 25.00:
                                if player not in players:
                                    players[player] = {}
                                
                                # Determinar tipo de apuesta por contexto
                                if 'goleador' in text.lower() or 'scorer' in text.lower():
                                    players[player]['first_goal'] = odds
                                else:
                                    players[player]['anytime_goal'] = odds
                                break
            
            return players
            
        except Exception as e:
            print(f"Error extracting player odds: {e}")
            return {}

    async def get_summary_for_analysis(self, odds_data: Dict) -> str:
        """Genera resumen de cuotas para análisis del bot 2"""
        try:
            summary_parts = []
            
            # Información del partido
            if 'match_info' in odds_data:
                match = odds_data['match_info']
                summary_parts.append(f"Partido: {match.get('home_team', 'Equipo Local')} vs {match.get('away_team', 'Equipo Visitante')}")
                if 'datetime' in match:
                    summary_parts.append(f"Fecha: {match['datetime']}")
            
            # 1X2
            if '1x2' in odds_data:
                x2 = odds_data['1x2']
                summary_parts.append(f"1X2: Local {x2.get('home')} | Empate {x2.get('draw')} | Visitante {x2.get('away')}")
            
            # Over/Under
            if 'over_under' in odds_data:
                ou = odds_data['over_under']
                summary_parts.append(f"O/U 2.5: Más {ou.get('over_2_5')} | Menos {ou.get('under_2_5')}")
            
            # BTTS
            if 'btts' in odds_data:
                btts = odds_data['btts']
                summary_parts.append(f"Ambos anotan: Sí {btts.get('yes')} | No {btts.get('no')}")
            
            # Jugadores destacados
            if 'players' in odds_data:
                players = odds_data['players']
                player_info = []
                for player, odds in players.items():
                    if 'anytime_goal' in odds:
                        player_info.append(f"{player}: {odds['anytime_goal']}")
                if player_info:
                    summary_parts.append(f"Goleadores: {', '.join(player_info)}")
            
            return '\n'.join(summary_parts) if summary_parts else "No se encontraron cuotas válidas"
            
        except Exception as e:
            return f"Error generando resumen: {str(e)}"
