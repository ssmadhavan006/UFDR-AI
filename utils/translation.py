# utils/translation.py
import re
import os
from typing import Dict, Tuple, Optional
import logging
from utils.gemini_client import GeminiClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultilingualProcessor:
    """Handles language detection and translation while preserving entities using Gemini API"""
    
    def __init__(self):
        # Initialize Gemini client
        self.gemini_client = GeminiClient()
        
        # Regex patterns for entities to preserve
        self.crypto_pattern = r'\b(bc[0-9a-zA-Z]{25,40}|0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b'
        self.phone_pattern = r'\+?[\d\s\-\(\)]{7,}'
        self.number_pattern = r'\b\d+(?:\.\d+)?\b'
        self.entity_patterns = [
            ('CRYPTO', self.crypto_pattern),
            ('PHONE', self.phone_pattern),
            ('NUMBER', self.number_pattern)
        ]
    
    def detect_language(self, text: str) -> str:
        """Detect language of text using Gemini API"""
        try:
            if not text or not text.strip():
                return 'en'
            
            # Clean text for better detection
            clean_text = re.sub(r'[^\w\s]', ' ', text)
            if len(clean_text.strip()) < 3:
                return 'en'
            
            # Use Gemini API for language detection
            result = self.gemini_client.detect_language(clean_text)
            detected = result.get('language_code', 'en')
            
            logger.debug(f"Detected language: {detected} for text: {text[:50]}...")
            return detected
        except Exception as e:
            logger.warning(f"Language detection failed for text '{text[:50]}...': {e}")
            return 'en'  # Default to English
    
    def _extract_entities(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Extract entities and replace with placeholders"""
        entity_map = {}
        processed_text = text
        
        for entity_type, pattern in self.entity_patterns:
            matches = re.findall(pattern, processed_text)
            for i, match in enumerate(matches):
                placeholder = f"__{entity_type}_{i}__"
                entity_map[placeholder] = match
                processed_text = processed_text.replace(match, placeholder, 1)
        
        return processed_text, entity_map
    
    def _restore_entities(self, text: str, entity_map: Dict[str, str]) -> str:
        """Restore entities from placeholders"""
        for placeholder, entity in entity_map.items():
            text = text.replace(placeholder, entity)
        return text
    
    def translate_text(self, text: str, src_lang: str = 'auto', dest_lang: str = 'en') -> Dict:
        """
        Translate text while preserving entities using Gemini API
        
        Returns:
            dict with keys: original_text, translated_text, src_language, confidence
        """
        try:
            if not text or not text.strip():
                return {
                    'original_text': text,
                    'translated_text': text,
                    'src_language': 'en',
                    'confidence': 1.0
                }
            
            # Detect language if not provided
            if src_lang == 'auto':
                src_lang = self.detect_language(text)
            
            # No translation needed if already English
            if src_lang == 'en' or src_lang == dest_lang:
                return {
                    'original_text': text,
                    'translated_text': text,
                    'src_language': src_lang,
                    'confidence': 1.0
                }
            
            # Extract entities before translation
            clean_text, entity_map = self._extract_entities(text)
            
            # Translate using Gemini API
            result = self.gemini_client.translate_text(clean_text, source_language=src_lang, target_language=dest_lang)
            
            # Restore entities in translated text
            translated_text = self._restore_entities(result.get('translated_text', clean_text), entity_map)
            
            logger.info(f"Translated '{text[:50]}...' from {src_lang} to {dest_lang}")
            
            return {
                'original_text': text,
                'translated_text': translated_text,
                'src_language': src_lang,
                'confidence': result.get('confidence', 0.9)
            }
            
        except Exception as e:
            logger.error(f"Translation failed for text '{text[:50]}...': {e}")
            return {
                'original_text': text,
                'translated_text': text,
                'src_language': src_lang if src_lang != 'auto' else 'en',
                'confidence': 0.0
            }
    
    def process_message(self, message_text: str) -> Dict:
        """
        Process a single message: detect language and translate if needed
        
        Returns:
            dict with original text, translated text, detected language, etc.
        """
        result = {
            'original_text': message_text,
            'detected_language': self.detect_language(message_text),
            'translated_text': message_text,
            'translation_confidence': 1.0,
            'needs_translation': False
        }
        
        # Translate if not English
        if result['detected_language'] != 'en':
            result['needs_translation'] = True
            translation_result = self.translate_text(
                message_text, 
                src_lang=result['detected_language'], 
                dest_lang='en'
            )
            result.update({
                'translated_text': translation_result['translated_text'],
                'translation_confidence': translation_result['confidence']
            })
        
        return result

class TranslationManager:
    """Translation manager that provides a simplified interface for the frontend app"""
    
    def __init__(self):
        self.processor = MultilingualProcessor()
    
    def detect_language(self, text: str) -> str:
        """Detect language of text"""
        return self.processor.detect_language(text)
    
    def translate_text(self, text: str, src_lang: str = 'auto', dest_lang: str = 'en') -> Tuple[str, str, float]:
        """
        Translate text and return (translated_text, original_text, confidence)
        
        Returns:
            tuple: (translated_text, original_text, confidence_score)
        """
        try:
            result = self.processor.translate_text(text, src_lang, dest_lang)
            return (
                result['translated_text'],
                result['original_text'],
                result['confidence']
            )
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return (text, text, 0.0)
    
    def process_message(self, message_text: str) -> Dict:
        """Process a message with language detection and translation"""
        return self.processor.process_message(message_text)

# Global instance for easy access
multilingual_processor = MultilingualProcessor()
translation_manager = TranslationManager()

def detect_language(text: str) -> str:
    """Quick function for language detection"""
    return multilingual_processor.detect_language(text)

def translate_message(text: str) -> Dict:
    """Quick function for message translation"""
    return multilingual_processor.process_message(text)

# Example usage and test
if __name__ == "__main__":
    processor = MultilingualProcessor()
    
    # Test messages
    test_messages = [
        "Hello, how are you?",  # English
        "வணக்கம், எப்படி இருக்கிறீர்கள்?",  # Tamil
        "Send money to bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",  # English with crypto
        "என் பணத்தை +91 9876543210 க்கு அனுப்பு",  # Tamil with phone
        "Envía dinero a 0x742d35Cc6634C0532925a3b844Bc454e4438f44e",  # Spanish with crypto
    ]
    
    for msg in test_messages:
        result = processor.process_message(msg)
        print(f"Original: {result['original_text']}")
        print(f"Language: {result['detected_language']}")
        print(f"Translated: {result['translated_text']}")
        print(f"Needs Translation: {result['needs_translation']}")
        print("-" * 50)