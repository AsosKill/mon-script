from flask import Flask, request, jsonify, send_file
import requests
import json
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

# Configuration
RUNWAY_API_URL = "https://api.runwayml.com/v1/query"
RUNWAY_API_KEY = "key_3d31ffb21f881f8c91c345d7906b5bdb194d8b0aa422e2bcdaea12bb090cb504135dccd0c535a0b6bc140d8df3abcf5a04d29c50062b282f63b9823507c910f8"
STATS_FILE = "thumbnail_stats.json"

def load_stats():
    """Charge les statistiques des miniatures tendances"""
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r") as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Erreur lors du chargement des statistiques: {e}")
        return None

def generate_image_with_runway(title, stats=None):
    """Génère une image avec Runway ML basée sur les statistiques tendances"""
    try:
        prompt_base = f"Create a YouTube thumbnail with the title '{title}'"
        
        if stats:
            brightness_desc = "bright" if stats["brightness_avg"] > 127 else "dark"
            contrast_desc = "high contrast" if stats["contrast_avg"] > 50 else "soft contrast"
            
            prompt = f"{prompt_base}. Make it {brightness_desc} with {contrast_desc}. "
            prompt += "Include text overlay. " if stats["text_usage"] == "Yes" else "Minimize text. "
            prompt += "Use vibrant, attention-grabbing design similar to trending YouTube thumbnails."
        else:
            prompt = f"{prompt_base}. Make it vibrant and attention-grabbing."
        
        print(f"Génération d'image avec prompt: {prompt}")
        
        headers = {
            "Authorization": f"Bearer {RUNWAY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "prompt": prompt,
            "model": "stable-diffusion-xl-1024-v1-0",
            "params": {
                "width": 1280,
                "height": 720,
                "num_outputs": 1
            }
        }
        
        response = requests.post(RUNWAY_API_URL, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        
        result = response.json()
        
        if "error" in result:
            print(f"Erreur Runway ML: {result['error']}")
            return None
        
        if "output" in result and "images" in result["output"]:
            image_url = result["output"]["images"][0]
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            
            img = Image.open(BytesIO(img_response.content))
            
            if stats:
                draw = ImageDraw.Draw(img)
                r, g, b = stats["dominant_color"]
                text_color = (255-r, 255-g, 255-b)  # Couleur inverse
                
                try:
                    font = ImageFont.truetype("arial.ttf", 60)
                except:
                    font = ImageFont.load_default()
                
                text_position = (50, 600)
                for offset in [(2,2), (-2,2), (2,-2), (-2,-2)]:
                    draw.text((text_position[0]+offset[0], text_position[1]+offset[1]), 
                             title, fill=(0,0,0), font=font)
                
                draw.text(text_position, title, fill=text_color, font=font)
            
            output_filename = f"thumbnail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            img.save(output_filename)
            
            return output_filename
        else:
            print("Format de réponse Runway ML inattendu")
            return None
    
    except Exception as e:
        print(f"Erreur lors de la génération d'image: {e}")
        return None

@app.route('/')
def home():
    """Endpoint pour vérifier que l'API fonctionne"""
    return jsonify({"message": "Thumbnail API is running!"}), 200

@app.route('/stats', methods=['GET'])
def get_stats():
    """Endpoint pour récupérer les statistiques des tendances"""
    stats = load_stats()
    if stats:
        return jsonify(stats)
    return jsonify({"error": "Aucune statistique disponible"}), 404

@app.route('/generate', methods=['GET', 'POST'])
def generate_thumbnail():
    """Endpoint pour générer une miniature"""
    if request.method == 'GET':
        title = request.args.get('title')
    else:  # POST
        data = request.json
        if not data or "title" not in data:
            return jsonify({"error": "Le titre est requis"}), 400
        title = data["title"]
    
    if not title:
        return jsonify({"error": "Le titre est requis"}), 400
    
    stats = load_stats()
    output_file = generate_image_with_runway(title, stats)
    
    if output_file and os.path.exists(output_file):
        return jsonify({
            "success": True,
            "message": "Miniature générée avec succès",
            "filename": output_file,
            "url": f"/thumbnails/{output_file}"
        })
    
    return jsonify({
        "success": False,
        "message": "Échec de la génération de la miniature"
    }), 500

@app.route('/thumbnails/<filename>', methods=['GET'])
def get_thumbnail(filename):
    """Endpoint pour récupérer une miniature générée"""
    if os.path.exists(filename):
        return send_file(filename)
    return jsonify({"error": "Fichier non trouvé"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # 10000 par défaut si PORT n'est pas défini
    app.run(host="0.0.0.0", port=port)

