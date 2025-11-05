"""
Gemini API Client for AIE application
"""
import os
import json
import requests
from typing import List, Dict, Any, Optional
import base64
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class GeminiClient:
    """Client for interacting with Google's Gemini API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini API client
        
        Args:
            api_key: Gemini API key (if None, will try to get from environment)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key not provided and not found in environment variables")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.text_model = "gemini-1.5-pro"
        self.vision_model = "gemini-1.5-pro-vision"
    
    def generate_text(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1024) -> str:
        """
        Generate text using Gemini API
        
        Args:
            prompt: Text prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated text response
        """
        url = f"{self.base_url}/{self.text_model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
                "topK": 40
            }
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Gemini API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # Extract the generated text from the response
        try:
            generated_text = result["candidates"][0]["content"]["parts"][0]["text"]
            return generated_text
        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse Gemini API response: {e}")
    
    def analyze_image(self, image_path: str, prompt: str, temperature: float = 0.7) -> str:
        """
        Analyze an image using Gemini Vision API
        
        Args:
            image_path: Path to the image file
            prompt: Text prompt describing what to analyze in the image
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            Analysis text response
        """
        url = f"{self.base_url}/{self.vision_model}:generateContent?key={self.api_key}"
        
        # Read and encode the image
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            image_b64 = base64.b64encode(image_data).decode("utf-8")
        
        # Determine MIME type based on file extension
        mime_type = "image/jpeg"  # Default
        if image_path.lower().endswith(".png"):
            mime_type = "image/png"
        elif image_path.lower().endswith(".gif"):
            mime_type = "image/gif"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 1024,
                "topP": 0.95,
                "topK": 40
            }
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Gemini API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # Extract the generated text from the response
        try:
            generated_text = result["candidates"][0]["content"]["parts"][0]["text"]
            return generated_text
        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse Gemini API response: {e}")
    
    def translate_text(self, text: str, target_language: str = "English") -> Dict[str, Any]:
        """
        Translate text using Gemini API
        
        Args:
            text: Text to translate
            target_language: Target language for translation
            
        Returns:
            Dictionary with translated text and confidence score
        """
        prompt = f"""
        Translate the following text to {target_language}. 
        Return a JSON object with the translated text and a confidence score between 0 and 1.
        
        Text to translate: "{text}"
        
        Format your response as a valid JSON object with these keys:
        - translated_text: The translated text
        - confidence: A number between 0 and 1 indicating translation confidence
        """
        
        response = self.generate_text(prompt)
        
        # Extract JSON from response
        try:
            # Find JSON in the response (it might be surrounded by markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            return {
                "translated_text": result.get("translated_text", ""),
                "confidence": float(result.get("confidence", 0.7))
            }
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback if JSON parsing fails
            return {
                "translated_text": response.strip(),
                "confidence": 0.5
            }
    
    def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Detect the language of a text using Gemini API
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with detected language and confidence score
        """
        prompt = f"""
        Detect the language of the following text. 
        Return a JSON object with the detected language name and a confidence score between 0 and 1.
        
        Text: "{text}"
        
        Format your response as a valid JSON object with these keys:
        - language: The detected language name (in English)
        - language_code: The ISO 639-1 two-letter language code
        - confidence: A number between 0 and 1 indicating detection confidence
        """
        
        response = self.generate_text(prompt)
        
        # Extract JSON from response
        try:
            # Find JSON in the response (it might be surrounded by markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            return {
                "language": result.get("language", "Unknown"),
                "language_code": result.get("language_code", "un"),
                "confidence": float(result.get("confidence", 0.7))
            }
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback if JSON parsing fails
            return {
                "language": "Unknown",
                "language_code": "un",
                "confidence": 0.5
            }
    
    def generate_ai_suggestions(self, messages) -> List[str]:
        """
        Generate AI investigative suggestions based on message data
        
        Args:
            messages: List of message dictionaries or Document objects
            
        Returns:
            List of AI suggestions as strings
        """
        # Format messages for the prompt - handle both dict and Document objects
        messages_text = "\n".join([
            self._format_message_for_ai(msg)
            for msg in messages[:20]  # Limit to 20 messages to avoid token limits
        ])
        
        prompt = f"""
        You are a digital forensics AI assistant. Based on the following chat messages, 
        provide 3-5 investigative suggestions that might help an investigator uncover 
        important information or patterns. Focus on potential leads, suspicious patterns, 
        or areas that warrant further investigation.
        
        CHAT MESSAGES:
        {messages_text}
        
        Provide your suggestions as a list, with each suggestion on a new line starting with "- ".
        Be specific, insightful, and focus on actionable investigative steps.
        """
        
        response = self.generate_text(prompt, temperature=0.3)
        
        # Parse the response into a list of suggestions
        suggestions = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                suggestions.append(line[2:])
            elif line.startswith("1. ") or line.startswith("2. ") or line.startswith("3. ") or line.startswith("4. ") or line.startswith("5. "):
                suggestions.append(line[3:])
        
        return suggestions
    
    def _format_message_for_ai(self, msg) -> str:
        """
        Helper method to format a message for AI processing
        Handles both dict and Document objects
        """
        try:
            # Check if it's a Document object (has page_content and metadata attributes)
            if hasattr(msg, 'page_content') and hasattr(msg, 'metadata'):
                # It's a Document object
                sender = msg.metadata.get('sender', 'Unknown')
                timestamp = msg.metadata.get('timestamp', 'Unknown')
                content = msg.page_content or 'No content'
                return f"Sender: {sender}, Time: {timestamp}, Content: {content}"
            else:
                # It's a dictionary
                sender = msg.get('sender', 'Unknown')
                timestamp = msg.get('timestamp', 'Unknown')
                content = msg.get('content', msg.get('text', 'No content'))
                return f"Sender: {sender}, Time: {timestamp}, Content: {content}"
        except Exception as e:
            # Fallback for any unexpected format
            return f"Message format error: {str(e)}"
    
    def tag_image(self, image_path: str, num_tags: int = 5) -> List[Dict[str, Any]]:
        """
        Generate tags for an image using Gemini Vision API
        
        Args:
            image_path: Path to the image file
            num_tags: Number of tags to generate
            
        Returns:
            List of dictionaries with tag label and confidence score
        """
        prompt = f"""
        Analyze this image and provide {num_tags} descriptive tags that best represent its content.
        Return your response as a valid JSON array of objects, where each object has:
        - "label": the tag text
        - "confidence": a number between 0 and 1 indicating your confidence in this tag
        
        Format example:
        [
            {{"label": "example tag", "confidence": 0.95}},
            {{"label": "another tag", "confidence": 0.8}}
        ]
        
        Only return the JSON array, nothing else.
        """
        
        response = self.analyze_image(image_path, prompt, temperature=0.2)
        
        # Extract JSON from response
        try:
            # Find JSON in the response (it might be surrounded by markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            
            tags = json.loads(json_str)
            return tags
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback if JSON parsing fails
            return [{"label": "image", "confidence": 0.5}]