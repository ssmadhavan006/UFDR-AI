"""
Media Forensics module for AIE - AI Forensic Explorer
Provides functionality for analyzing media files, detecting QR codes, and tagging images
"""

import os
import cv2
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from PIL import Image

# Import Gemini client for image tagging
from utils.gemini_client import GeminiClient

def detect_qr_codes(image_path):
    """
    Detect QR codes in an image
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of dictionaries with QR code data and positions
    """
    # Read the image
    img = cv2.imread(str(image_path))
    if img is None:
        return []
    
    # Initialize QR Code detector
    qr_detector = cv2.QRCodeDetector()
    
    # Detect and decode
    data, bbox, _ = qr_detector.detectAndDecode(img)
    
    results = []
    
    # If a QR code is found
    if bbox is not None:
        if data:  # If data was successfully decoded
            # Convert bbox to a more usable format
            bbox = bbox.astype(int)
            
            results.append({
                "image_path": str(image_path),
                "qr_data": data,
                "position": bbox.tolist() if isinstance(bbox, np.ndarray) else bbox,
                "timestamp": datetime.now().isoformat()
            })
    
    return results

def tag_image_with_gemini(image_path, num_tags=5):
    """
    Tag an image using Gemini Vision API
    
    Args:
        image_path: Path to the image file
        num_tags: Number of tags to generate
        
    Returns:
        Dictionary with image tags and confidence scores
    """
    try:
        # Initialize Gemini client
        gemini_client = GeminiClient()
        
        # Get tags from Gemini
        tags = gemini_client.tag_image(image_path, num_tags=num_tags)
        
        # Prepare results
        results = {
            "image_path": str(image_path),
            "tags": tags,
            "timestamp": datetime.now().isoformat()
        }
        
        return results
    
    except Exception as e:
        return {"error": str(e), "image_path": str(image_path)}

def scan_directory_for_media(directory_path):
    """
    Scan a directory for media files and analyze them
    
    Args:
        directory_path: Path to the directory to scan
        
    Returns:
        Dictionary with analysis results
    """
    media_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    results = {
        "qr_codes": [],
        "tagged_images": [],
        "media_files": []
    }
    
    # Walk through the directory
    for root, _, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in media_extensions:
                # Add to media files list
                results["media_files"].append(file_path)
                
                # Detect QR codes
                qr_results = detect_qr_codes(file_path)
                if qr_results:
                    results["qr_codes"].extend(qr_results)
                
                # Tag image with Gemini
                tag_results = tag_image_with_gemini(file_path)
                if "error" not in tag_results:
                    results["tagged_images"].append(tag_results)
    
    return results

def link_media_to_chats(media_results, chat_data):
    """
    Link media files to relevant chat messages
    
    Args:
        media_results: Results from scan_directory_for_media
        chat_data: List of chat messages
        
    Returns:
        Dictionary with linked media and chats
    """
    linked_results = {
        "media_with_chats": []
    }
    
    # Extract media file paths
    media_files = set(media_results["media_files"])
    
    # Scan chat data for media references
    for message in chat_data:
        content = message.get("content", "")
        
        # Check if any media file is mentioned in the message
        for media_file in media_files:
            file_name = os.path.basename(media_file)
            
            if file_name in content:
                # Create a link
                linked_results["media_with_chats"].append({
                    "media_path": media_file,
                    "chat_message": message,
                    "timestamp": datetime.now().isoformat()
                })
    
    return linked_results

def find_images_with_qr_codes(directory_path):
    """
    Find all images with QR codes in a directory
    
    Args:
        directory_path: Path to the directory to scan
        
    Returns:
        List of dictionaries with QR code data and image paths
    """
    media_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    results = []
    
    # Walk through the directory
    for root, _, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in media_extensions:
                # Detect QR codes
                qr_results = detect_qr_codes(file_path)
                if qr_results:
                    results.extend(qr_results)
    
    return results