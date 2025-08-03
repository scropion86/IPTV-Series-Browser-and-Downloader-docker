from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
import time
import logging
from tqdm import tqdm
import asyncio
import aiohttp
import threading
from queue import Queue, Empty
import json
from flask import Response, stream_with_context, Flask, request, jsonify, render_template
from cache_manager import process_and_cache_series_data, search_series, get_cached_data, get_series_count_by_category
# from config import BASE_URL, USERNAME, PASSWORD # Comment out or remove this line

# Retrieve configuration from environment variables
BASE_URL = os.getenv('BASE_URL')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = 'your-secret-key'


DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')

# Configure session for requests with more robust settings
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "POST"],
    raise_on_redirect=True,
    raise_on_status=True
)

adapter = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=10,
    pool_maxsize=10
)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

def get_categories():
    """Fetch all series categories with improved error handling"""
    url = f"{BASE_URL}/player_api.php"
    params = {
        "username": USERNAME,
        "password": PASSWORD,
        "action": "get_series_categories"
    }
    
    try:
        logger.debug(f"Fetching categories from: {url}")
        response = session.get(url, params=params, timeout=(5, 15))
        response.raise_for_status()
        categories = response.json()
        logger.debug(f"Retrieved {len(categories)} categories")
        return categories
    except requests.exceptions.Timeout:
        logger.error("Request timed out while fetching categories")
        return []
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return []

def get_series_by_category(category_id):
    """Fetch all series in a category"""
    url = f"{BASE_URL}/player_api.php"
    params = {
        "username": USERNAME,
        "password": PASSWORD,
        "action": "get_series",
        "category_id": category_id
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching series list: {str(e)}")
        return []

def get_series_info(series_id):
    """Fetch series information"""
    url = f"{BASE_URL}/player_api.php"
    params = {
        "username": USERNAME,
        "password": PASSWORD,
        "action": "get_series_info",
        "series_id": series_id
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching series info: {str(e)}")
        return None

def download_episode_file(episode, output_path):
    """Download a single episode file with progress"""
    url = f"{BASE_URL}/series/{USERNAME}/{PASSWORD}/{episode['id']}.{episode['container_extension']}"
    
    try:
        logger.debug(f"Attempting to download from: {url}")
        response = session.get(url, stream=True)
        response.raise_for_status()
        
        file_size = int(response.headers.get('content-length', 0))
        logger.debug(f"File size: {file_size} bytes")
        
        # Set up CLI progress bar
        progress_bar = tqdm(
            total=file_size,
            unit='iB',
            unit_scale=True,
            desc=f"Downloading {episode['title']}"
        )
        
        downloaded = 0
        with open(output_path, 'wb') as f:
            for data in response.iter_content(chunk_size=8192):
                if data:
                    size = f.write(data)
                    downloaded += size
                    progress_bar.update(size)
                    # Update web UI progress via SSE
                    progress = {
                        'episode': episode['title'],
                        'progress': (downloaded / file_size) * 100 if file_size > 0 else 0,
                        'status': 'downloading'
                    }
                    sse_queue.put(progress)
        
        progress_bar.close()
        return True
    except Exception as e:
        logger.error(f"Error downloading {episode['title']}: {str(e)}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False

@app.route('/')
@app.route('/page/<int:page>')
def index(page=1):
    page_size = 30 # Changed from 20 to 30
    categories = get_categories()
    if not categories:
        return render_template('error.html', 
                            message="Unable to fetch categories. Please try again later."), 503
    
    # Calculate pagination
    total_categories = len(categories)
    pages = (total_categories + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    
    category_counts = get_series_count_by_category()

    return render_template('index.html', 
                         categories=categories[start:end],
                         current_page=page,
                         total_pages=pages,
                         total_categories=total_categories,
                         category_counts=category_counts)

@app.route('/series/<category_id>')
@app.route('/series/<category_id>/page/<int:page>')
def series(category_id, page=1):
    page_size = 20
    series_list = get_series_by_category(category_id)
    
    # Get category name
    categories = get_categories()
    category_name = next((cat['category_name'] for cat in categories if cat['category_id'] == category_id), 'Unknown Category')
    
    # Calculate pagination
    total = len(series_list)
    pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    
    return render_template('series.html', 
                         series_list=series_list[start:end],
                         current_page=page,
                         total_pages=pages,
                         category_id=category_id,
                         category_name=category_name)

@app.route('/download', methods=['POST'])
def download():
    series_id = request.form.get('series_id')
    logger.debug(f"Downloading series with ID: {series_id}")
    
    series_data = get_series_info(series_id)
    if not series_data:
        return render_template('error.html', 
                             message="Could not fetch series information"), 503
    
    # Pass both series_data and the original series_id
    return render_template('download.html', series=series_data, series_id=series_id)

# Update the download_episodes route
@app.route('/download_episodes', methods=['POST'])
def download_episodes():
    series_id = request.form.get('series_id')
    season = request.form.get('season')
    
    logger.debug(f"Download request - Series ID: {series_id}, Season: {season}")
    
    try:
        start_episode = int(request.form.get('start_episode'))
        end_episode = int(request.form.get('end_episode'))
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid episode numbers: {e}")
        return jsonify({'error': 'Invalid episode numbers'}), 400
    
    # Get series data
    series_data = get_series_info(series_id)
    if not series_data:
        logger.error(f"Could not fetch series info for ID: {series_id}")
        return jsonify({'error': 'Could not fetch series information'}), 503
        
    try:
        episodes = series_data['episodes'][season]
        episodes_to_download = episodes[start_episode-1:end_episode]
        
        if not episodes_to_download:
            return jsonify({'error': 'No episodes found in selected range'}), 400
        
        # Create downloads directory if it doesn't exist
        series_dir = os.path.join(DOWNLOADS_DIR, f"{series_data['info']['name']} - S{season}")
        os.makedirs(series_dir, exist_ok=True)
        
        # Start download process in background thread
        def download_worker():
            try:
                total = len(episodes_to_download)
                for i, episode in enumerate(episodes_to_download, 1):
                    output_path = os.path.join(series_dir, f"{episode['title']}.{episode['container_extension']}")
                    success = download_episode_file(episode, output_path)
                    # Update progress via SSE
                    progress = {
                        'episode': episode['title'],
                        'progress': (i / total) * 100,
                        'status': 'success' if success else 'error'
                    }
                    sse_queue.put(progress)
                
                # Send completion message
                sse_queue.put({
                    'progress': 100,
                    'status': 'complete',
                    'message': 'All downloads completed'
                })
                # Send sentinel to close connection
                sse_queue.put(None)
            except Exception as e:
                logger.error(f"Download worker error: {str(e)}")
                sse_queue.put({
                    'status': 'error',
                    'error': str(e)
                })
                sse_queue.put(None)
        
        thread = threading.Thread(target=download_worker)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Download started for {len(episodes_to_download)} episodes'
        })
        
    except KeyError as e:
        logger.error(f"Invalid season or episode data: {e}")
        return jsonify({'error': 'Invalid season or episode data'}), 400
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add SSE route for progress updates
sse_queue = Queue()

@app.route('/progress')
def progress():
    def generate():
        try:
            while True:
                # Add timeout to prevent infinite blocking
                try:
                    progress = sse_queue.get(timeout=30)
                    if progress is None:  # Use None as sentinel to stop
                        break
                    yield f"data: {json.dumps(progress)}\n\n"
                except Queue.Empty:
                    # Send keep-alive message every 30 seconds
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            # Client disconnected, cleanup
            logger.debug("Client disconnected from progress stream")
        except Exception as e:
            logger.error(f"Error in progress stream: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route('/test_base_html')
def test_base_html():
    return render_template('base.html')

@app.route('/search')
def search():
    query = request.args.get('query')
    results = []
    last_fetch_date = None

    cached_data = get_cached_data()
    if cached_data:
        last_fetch_date = cached_data.get("last_fetch_date")

    if query:
        results, _ = search_series(query) # _ is used to ignore last_fetch_date from search_series as we already got it

    return render_template('search.html', query=query, results=results, last_fetch_date=last_fetch_date)

@app.route('/cache_progress')
def cache_progress():
    def generate():
        while True:
            try:
                progress_data = sse_queue.get(timeout=1) # Short timeout to keep connection alive
                if progress_data is None: # Sentinel to close connection
                    break
                yield f"data: {json.dumps(progress_data)}\n\n"
            except Empty:
                yield ": keep-alive\n\n" # Send keep-alive to prevent timeout
            except GeneratorExit:
                logger.debug("Client disconnected from cache progress stream")
                break
            except Exception as e:
                logger.error(f"Error in cache progress stream: {str(e)}")
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/cache_data')
def cache_data():
    """Endpoint to trigger the caching of series data in a background thread."""
    def caching_worker(app_context):
        with app_context:
            try:
                total_categories = len(get_categories())
                def progress_callback(progress, message, status):
                    sse_queue.put({
                        'progress': progress,
                        'message': message,
                        'status': status
                    })
                
                process_and_cache_series_data(get_categories, get_series_by_category, progress_callback)
                sse_queue.put({
                    'progress': 100,
                    'status': 'complete',
                    'message': 'Caching process completed.'
                })
            except Exception as e:
                logger.error(f"Error during caching process: {str(e)}")
                sse_queue.put({
                    'status': 'error',
                    'message': f'Caching failed: {str(e)}'
                })
            finally:
                sse_queue.put(None) # Sentinel to close the SSE connection

    # Start the caching process in a new thread
    app_context = app.app_context()
    thread = threading.Thread(target=caching_worker, args=(app_context,))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "success", "message": "Caching process initiated in background."})

if __name__ == '__main__':
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)
    # Add host parameter to make it accessible from other devices on the network
    app.run(debug=True, host='0.0.0.0', port=5000)