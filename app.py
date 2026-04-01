import os
import re
import uuid
import logging
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import yt_dlp
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['DOWNLOAD_FOLDER'] = Path('/tmp') / 'downloads' if os.environ.get('RENDER') else Path(__file__).parent / 'downloads'
app.config['CLEANUP_DELAY'] = 900

# Create downloads folder
app.config['DOWNLOAD_FOLDER'].mkdir(exist_ok=True)

# Store active downloads
active_downloads = {}

class YouTubeConverter:
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': str(app.config['DOWNLOAD_FOLDER'] / '%(title)s_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': True,
            'no_color': True,
            'noprogress': True,
            'noplaylist': True,
        }
    
    def sanitize_filename(self, filename):
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'\s+', ' ', filename).strip()
        if len(filename) > 200:
            filename = filename[:200]
        return filename
    
    def extract_video_info(self, url):
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': False, 'noplaylist': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'id': info.get('id', '')
                }
        except Exception as e:
            raise ValueError(f"Invalid YouTube URL: {str(e)}")
    
    def convert_to_mp3(self, url):
        try:
            conversion_id = str(uuid.uuid4())[:8]
            
            ydl_opts = self.ydl_opts.copy()
            ydl_opts['outtmpl'] = str(app.config['DOWNLOAD_FOLDER'] / f'%(title)s_{conversion_id}_%(id)s.%(ext)s')
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', 'Unknown')
                video_id = info.get('id', 'unknown')
                
                logger.info(f"Converting: {video_title}")
                ydl.download([url])
                
                pattern = f"*{conversion_id}*{video_id}*.mp3"
                files = list(app.config['DOWNLOAD_FOLDER'].glob(pattern))
                
                if not files:
                    pattern = f"*{video_id}*.mp3"
                    files = list(app.config['DOWNLOAD_FOLDER'].glob(pattern))
                
                if not files:
                    raise Exception("Could not locate converted file")
                
                mp3_file = files[0]
                safe_filename = f"{self.sanitize_filename(video_title)}_{video_id}.mp3"
                final_path = app.config['DOWNLOAD_FOLDER'] / safe_filename
                
                if mp3_file != final_path:
                    if final_path.exists():
                        final_path.unlink()
                    mp3_file.rename(final_path)
                    mp3_file = final_path
                
                return {
                    'filename': safe_filename,
                    'path': str(mp3_file),
                    'title': video_title,
                    'duration': info.get('duration', 0),
                    'size': mp3_file.stat().st_size,
                }
        except Exception as e:
            raise Exception(f"Conversion failed: {str(e)}")

converter = YouTubeConverter()

def cleanup_old_files():
    while True:
        try:
            time.sleep(300)
            now = time.time()
            to_remove = []
            for path, timestamp in list(active_downloads.items()):
                if now - timestamp > 900:
                    if Path(path).exists():
                        Path(path).unlink()
                    to_remove.append(path)
            for path in to_remove:
                del active_downloads[path]
        except:
            pass

threading.Thread(target=cleanup_old_files, daemon=True).start()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/style.css')
def serve_css():
    return send_from_directory('.', 'style.css', mimetype='text/css')

@app.route('/script.js')
def serve_js():
    return send_from_directory('.', 'script.js', mimetype='application/javascript')

@app.route('/api/convert', methods=['POST'])
def convert_video():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'success': False, 'error': 'No URL provided'}), 400
        
        url = data['url'].strip()
        
        youtube_pattern = r'(https?://)?(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com)/.+'
        if not re.match(youtube_pattern, url):
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400
        
        try:
            video_info = converter.extract_video_info(url)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        
        result = converter.convert_to_mp3(url)
        
        active_downloads[result['path']] = time.time()
        
        return jsonify({
            'success': True,
            'filename': result['filename'],
            'download_url': f'/api/download/{result["filename"]}',
            'info': {
                'title': result['title'],
                'duration': result['duration'],
                'size_mb': round(result['size'] / (1024 * 1024), 2)
            }
        })
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        filename = os.path.basename(filename)
        filepath = app.config['DOWNLOAD_FOLDER'] / filename
        
        if not filepath.exists():
            return jsonify({'error': 'File not found'}), 404
        
        active_downloads[str(filepath)] = time.time()
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/info', methods=['POST'])
def get_info():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL'}), 400
        
        info = converter.extract_video_info(data['url'].strip())
        mins = info['duration'] // 60
        secs = info['duration'] % 60
        info['duration_formatted'] = f"{mins}:{secs:02d}"
        
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)