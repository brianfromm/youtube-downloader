from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import yt_dlp
import os
import requests
import re
from urllib.parse import quote

app = Flask(__name__)
CORS(app)

def clean_filename_for_storage(filename):
    """Clean filename for file storage - keep most characters including ! and &"""
    # Handle None or undefined values
    if not filename or filename is None:
        return "video"
    
    # Ensure we have a string
    filename = str(filename)
    
    # Only remove characters that are truly problematic for file systems
    # Keep ! and & since they're safe in filenames
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace underscores with spaces for readability
    filename = re.sub(r'_+', ' ', filename)
    # Clean up multiple spaces
    filename = re.sub(r'\s+', ' ', filename)
    # Trim and limit length
    filename = filename.strip()
    if len(filename) > 100:
        filename = filename[:100].strip()
    
    # Final fallback if string becomes empty
    if not filename:
        return "video"
    
    return filename

def sanitize_for_http_header(filename):
    """Sanitize filename specifically for HTTP Content-Disposition header"""
    # Handle None or undefined values
    if not filename or filename is None:
        return "video"
    
    # Ensure we have a string
    filename = str(filename)
    
    # Only remove characters that actually break HTTP headers (quotes)
    # Keep ! and & since we're using URL encoding anyway
    filename = re.sub(r'[\'"]', '', filename)  # Only remove quotes
    filename = filename.strip()
    
    # Final fallback if string becomes empty
    if not filename:
        return "video"
    
    # URL encode the filename to handle any remaining special chars/emojis safely
    return quote(filename.encode('utf-8'), safe=' -.()[]!&')

# Serve the HTML file
@app.route('/')
def serve_html():
    try:
        return send_from_directory('.', 'youtube-extractor.html')
    except Exception as e:
        return f"Error serving HTML file: {str(e)}. Make sure 'youtube-extractor.html' is in the same directory as this server file."

def clean_youtube_url(url):
    """Clean YouTube URL by removing tracking parameters and normalizing format"""
    import re
    from urllib.parse import urlparse, parse_qs
    
    # Extract video ID from various YouTube URL formats
    video_id_match = re.search(r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    
    if not video_id_match:
        return url  # Return original if we can't parse it
    
    video_id = video_id_match.group(1)
    
    # Extract timestamp if present (t= or start= parameter)
    timestamp = None
    try:
        parsed = urlparse(url)
        if parsed.query:
            params = parse_qs(parsed.query)
            # Check for t parameter (youtube.com) or start parameter
            if 't' in params:
                timestamp = params['t'][0]
            elif 'start' in params:
                timestamp = params['start'][0]
        
        # Also check for #t= in fragment (youtu.be format)
        if parsed.fragment and parsed.fragment.startswith('t='):
            timestamp = parsed.fragment[2:]
            
        # Handle &t= in youtu.be URLs
        if '&t=' in url:
            t_match = re.search(r'[&?]t=([^&]+)', url)
            if t_match:
                timestamp = t_match.group(1)
                
    except:
        pass  # If URL parsing fails, continue without timestamp
    
    # Return clean youtube.com format
    clean_url = f"https://www.youtube.com/watch?v={video_id}"
    if timestamp:
        clean_url += f"&t={timestamp}"
    
    return clean_url

@app.route('/extract', methods=['POST'])
def extract_video_info():
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Clean the URL to remove tracking parameters
        clean_url = clean_youtube_url(url)
        print(f"🎬 Extracting video info from: {clean_url}", flush=True)
        if clean_url != url:
            print(f"🧹 Cleaned URL from: {url}", flush=True)
        
        # Configure yt-dlp options
        ydl_opts = {
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            
            # Extract relevant information
            video_data = {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration_string', 'Unknown'),
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': f"{info.get('view_count', 0):,}" if info.get('view_count') else 'Unknown',
                'upload_date': info.get('upload_date', 'Unknown'),
                'formats': []
            }
            
            print(f"📹 Processing: \"{video_data['title']}\" by {video_data['uploader']}", flush=True)
            
            # Process formats
            for fmt in info.get('formats', []):
                if fmt.get('url'):  # Only requirement is that it has a URL
                    format_entry = {
                        'format_id': fmt.get('format_id', ''),
                        'ext': fmt.get('ext', ''),
                        'vcodec': fmt.get('vcodec', 'none'),
                        'acodec': fmt.get('acodec', 'none'),
                        'url': fmt.get('url', ''),
                        'protocol': fmt.get('protocol', 'unknown'),
                        'height': fmt.get('height'),
                        'width': fmt.get('width'),
                        'abr': fmt.get('abr'),
                        'tbr': fmt.get('tbr'),
                        'fps': fmt.get('fps')
                    }
                    
                    # Better type detection
                    has_video = fmt.get('height') and fmt.get('height') > 0
                    has_audio = fmt.get('acodec') and fmt.get('acodec') != 'none'
                    
                    # Some formats like 18, 22 are combined video+audio even if acodec shows 'none'
                    # These are legacy YouTube formats that include audio
                    combined_format_ids = ['17', '18', '22', '36', '37', '38', '43', '44', '45', '46', '59', '78', '82', '83', '84', '85']
                    is_combined = fmt.get('format_id') in combined_format_ids
                    
                    # Also detect if format explicitly has both video and audio codecs
                    explicit_audio = (fmt.get('acodec') and 
                                    fmt.get('acodec') not in ['none', None] and 
                                    fmt.get('acodec') != 'None')
                    
                    if has_video and (has_audio or explicit_audio or is_combined):
                        format_entry['type'] = 'video+audio'
                        format_entry['quality'] = f"{fmt.get('height')}p"
                    elif has_video:
                        format_entry['type'] = 'video-only'
                        format_entry['quality'] = f"{fmt.get('height')}p"
                    elif fmt.get('abr') or fmt.get('acodec') != 'none':
                        format_entry['type'] = 'audio-only'
                        format_entry['quality'] = f"{fmt.get('abr', 'Unknown')}kbps"
                    else:
                        format_entry['type'] = 'other'
                        format_entry['quality'] = fmt.get('format_note', 'Unknown')
                    
                    # Skip storyboard and playlist formats for cleaner display
                    if (fmt.get('format_note') == 'storyboard' or 
                        fmt.get('protocol') == 'm3u8_native' or 
                        fmt.get('ext') == 'mhtml'):
                        continue
                    
                    # File size
                    if fmt.get('filesize'):
                        format_entry['filesize'] = f"{fmt.get('filesize') / (1024*1024):.1f} MB"
                    else:
                        format_entry['filesize'] = 'Unknown'
                    
                    video_data['formats'].append(format_entry)
            
            # Sort formats by type and quality
            video_audio_formats = [f for f in video_data['formats'] if f['type'] == 'video+audio']
            video_only_formats = [f for f in video_data['formats'] if f['type'] == 'video-only']
            audio_only_formats = [f for f in video_data['formats'] if f['type'] == 'audio-only']
            other_formats = [f for f in video_data['formats'] if f['type'] == 'other']
            
            print(f"📊 Found {len(video_audio_formats)} video+audio, {len(video_only_formats)} video-only, {len(audio_only_formats)} audio-only formats", flush=True)
            
            # Sort each group by quality (highest first)
            def sort_by_quality(format_list, is_audio=False):
                def get_quality_number(fmt):
                    if is_audio:
                        # For audio, extract kbps number
                        import re
                        quality = fmt.get('quality', '0')
                        match = re.search(r'(\d+)', quality.replace('kbps', ''))
                        return int(match.group(1)) if match else 0
                    else:
                        # For video, use height directly
                        return fmt.get('height', 0) or 0
                
                return sorted(format_list, key=get_quality_number, reverse=True)
            
            video_audio_formats = sort_by_quality(video_audio_formats)
            video_only_formats = sort_by_quality(video_only_formats)
            audio_only_formats = sort_by_quality(audio_only_formats, is_audio=True)
            
            # For combining, select formats with different resolutions, not just different encodings
            unique_resolutions = {}
            for fmt in video_only_formats:
                height = fmt.get('height')
                if height and height not in unique_resolutions:
                    # Prefer MP4 over WebM for compatibility
                    if fmt.get('ext') == 'mp4':
                        unique_resolutions[height] = fmt
                    elif height not in unique_resolutions:
                        unique_resolutions[height] = fmt
            
            # Sort by height descending and take top 3 different resolutions
            sorted_heights = sorted(unique_resolutions.keys(), reverse=True)
            video_only_formats = [unique_resolutions[height] for height in sorted_heights[:3]]
            
            # Combine in priority order: video+audio, video-only, audio-only, other
            video_data['formats'] = video_audio_formats + video_only_formats + audio_only_formats + other_formats
            
            print(f"✅ Extraction complete - returning {len(video_data['formats'])} total formats", flush=True)
            return jsonify(video_data)
            
    except Exception as e:
        print(f"❌ Extraction failed: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to extract video information: {str(e)}'}), 500

@app.route('/combine', methods=['POST'])
def combine_video_audio():
    try:
        data = request.json
        url = data.get('url')
        video_format_id = data.get('video_format_id')
        audio_format_id = data.get('audio_format_id')
        
        if not all([url, video_format_id, audio_format_id]):
            return jsonify({'error': 'URL, video_format_id, and audio_format_id required'}), 400
        
        # Clean format IDs - remove any suffixes after hyphens
        video_format_id = str(video_format_id).split('-')[0]
        audio_format_id = str(audio_format_id).split('-')[0]
        
        # Clean the URL to remove tracking parameters  
        clean_url = clean_youtube_url(url)
        print(f"🔧 Starting combination: video format {video_format_id} + audio format {audio_format_id}", flush=True)
        if clean_url != url:
            print(f"🧹 Using cleaned URL for combination", flush=True)
        
        # Get video info for filename
        ydl_opts_info = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            title = info.get('title', 'video')
        
        # Clean filename
        clean_title = clean_filename_for_storage(title)

        # Get video resolution for filename
        video_resolution = "Unknown"
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                formats_info = ydl.extract_info(clean_url, download=False)
                for fmt in formats_info.get('formats', []):
                    if fmt.get('format_id') == video_format_id:
                        if fmt.get('height'):
                            video_resolution = f"{fmt.get('height')}p"
                        break
        except:
            video_resolution = "Unknown"
        
        print(f"📁 Output filename: \"{clean_title} ({video_resolution}).mp4\"", flush=True)
        
        # Create temp directory for processing
        import tempfile
        import os
        import time
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Define output filename
            output_filename = f"{clean_title} ({video_resolution}).mp4"
            output_path = os.path.join(temp_dir, output_filename)
            
            # Use yt-dlp with specific format selection and merging
            ydl_opts = {
                'format': f'{video_format_id}+{audio_format_id}/best[height<=1080]',
                'outtmpl': output_path,
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'writesubtitles': False,
                'writeautomaticsub': False,
                'quiet': True,
                'no_warnings': True,
            }
            
            try:
                print("⚙️ Processing with yt-dlp...", flush=True)
                start_time = time.time()
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([clean_url])
                
                processing_time = time.time() - start_time
                print(f"⏱️ yt-dlp processing took {processing_time:.1f} seconds", flush=True)
                
                # Check if file exists
                if not os.path.exists(output_path):
                    print(f"❌ Expected output file not found at: {output_path}", flush=True)
                    print(f"📂 Files in temp dir: {os.listdir(temp_dir)}", flush=True)
                    print("🔄 yt-dlp method failed, trying manual FFmpeg combination...", flush=True)
                    return manual_combine(clean_url, video_format_id, audio_format_id, clean_title, video_resolution, temp_dir)
                
                print(f"✅ Output file created successfully: {os.path.basename(output_path)}", flush=True)
                
                # Read and return the file
                with open(output_path, 'rb') as f:
                    video_data = f.read()
                
                file_size_mb = len(video_data) / (1024*1024)
                print(f"✅ yt-dlp combination successful - file size: {file_size_mb:.1f} MB", flush=True)
                
                from flask import Response
                response = Response(
                    video_data,
                    mimetype='video/mp4',
                    headers={
                        'Content-Disposition': f'attachment; filename*=UTF-8\'\'{sanitize_for_http_header(output_filename)}',
                        'Content-Length': str(len(video_data))
                    }
                )
                return response
                
            except Exception as e:
                processing_time = time.time() - start_time if 'start_time' in locals() else 0
                print(f"⚠️ yt-dlp combination failed after {processing_time:.1f}s: {str(e)}", flush=True)
                print("🔄 Trying manual method...", flush=True)
                return manual_combine(clean_url, video_format_id, audio_format_id, clean_title, video_resolution, temp_dir)
            
    except Exception as e:
        print(f"❌ Combination error: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Combine error: {str(e)}'}), 500

def manual_combine(clean_url, video_format_id, audio_format_id, clean_title, video_resolution, temp_dir):
    """Manually download video and audio, then combine with FFmpeg"""
    try:
        import subprocess
        import os
        import time
        
        print("🔧 Starting manual FFmpeg combination...", flush=True)
        start_time = time.time()
        
        video_path = os.path.join(temp_dir, 'video.mp4')
        audio_path = os.path.join(temp_dir, 'audio.m4a')
        output_path = os.path.join(temp_dir, f"{clean_title} ({video_resolution}).mp4")
        
        # Download video
        print("📥 Downloading video stream...", flush=True)
        video_opts = {
            'format': video_format_id,
            'outtmpl': video_path,
            'quiet': True,
        }
        
        video_start = time.time()
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            ydl.download([url])
        video_time = time.time() - video_start
        print(f"📥 Video download completed in {video_time:.1f}s", flush=True)
        
        # Download audio  
        print("🎵 Downloading audio stream...", flush=True)
        audio_opts = {
            'format': audio_format_id,
            'outtmpl': audio_path,
            'quiet': True,
        }
        
        audio_start = time.time()
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
        audio_time = time.time() - audio_start
        print(f"🎵 Audio download completed in {audio_time:.1f}s", flush=True)
        
        # Combine with FFmpeg
        print("🎬 Combining streams with FFmpeg...", flush=True)
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path, 
            '-c:v', 'copy',
            '-c:a', 'aac',  # Re-encode audio to AAC for broad compatibility and to avoid issues with direct stream copy
            '-shortest',
            output_path
        ]
        
        ffmpeg_start = time.time()
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        ffmpeg_time = time.time() - ffmpeg_start
        
        if result.returncode != 0:
            print(f"❌ FFmpeg failed: {result.stderr}", flush=True)
            return jsonify({'error': f'FFmpeg failed: {result.stderr}'}), 500
        
        print(f"🎬 FFmpeg processing completed in {ffmpeg_time:.1f}s", flush=True)
        
        # Read and return combined file
        with open(output_path, 'rb') as f:
            video_data = f.read()
        
        file_size_mb = len(video_data) / (1024*1024)
        total_time = time.time() - start_time
        print(f"✅ Manual combination successful - file size: {file_size_mb:.1f} MB, total time: {total_time:.1f}s", flush=True)
        
        from flask import Response
        full_filename = f"{clean_title} ({video_resolution}).mp4"
        response = Response(
            video_data,
            mimetype='video/mp4',
            headers={
                'Content-Disposition': f'attachment; filename*=UTF-8\'\'{sanitize_for_http_header(full_filename)}',
                'Content-Length': str(len(video_data))
            }
        )
        return response
        
    except Exception as e:
        print(f"❌ Manual combination failed: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Manual combine failed: {str(e)}'}), 500

@app.route('/download/<format_id>')
def download_file(format_id):
    try:
        # Get the URL from the query parameter
        video_url = request.args.get('url')
        if not video_url:
            return jsonify({'error': 'URL parameter required'}), 400
        
        print(f"⬇️ Starting download for format {format_id}", flush=True)
        
        # Extract info again to get the download URL
        ydl_opts = {
            'format': format_id,
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # Find the requested format
            selected_format = None
            for fmt in info.get('formats', []):
                if fmt.get('format_id') == format_id:
                    selected_format = fmt
                    break
            
            if not selected_format:
                print(f"❌ Format {format_id} not found", flush=True)
                return jsonify({'error': f'Format {format_id} not found'}), 404
            
            # Clean up the title for use as filename
            title = info.get('title', 'video')
            clean_title = clean_filename_for_storage(title)
            
            # Get resolution for filename  
            resolution_text = ""
            if selected_format.get('height'):
                resolution_text = f"({selected_format.get('height')}p)"
            elif selected_format.get('abr'):
                resolution_text = f"({selected_format.get('abr')}kbps)"

            if resolution_text:
                filename = f"{clean_title} {resolution_text}.{selected_format.get('ext', 'mp4')}"
            else:
                filename = f"{clean_title}.{selected_format.get('ext', 'mp4')}"
            
            print(f"📁 Download filename: \"{filename}\"", flush=True)
            
            # Redirect to the video URL with download headers
            from flask import redirect, make_response
            import requests
            
            # Stream the file with proper download headers
            video_response = requests.get(selected_format.get('url'), stream=True)
            
            def generate():
                for chunk in video_response.iter_content(chunk_size=8192):
                    yield chunk
            
            response = make_response(generate())
            response.headers['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{sanitize_for_http_header(filename)}'
            response.headers['Content-Type'] = 'application/octet-stream'
            
            print(f"✅ Download started successfully", flush=True)
            return response
            
    except Exception as e:
        print(f"❌ Download failed: {str(e)}", flush=True)
        return jsonify({'error': f'Download error: {str(e)}'}), 500

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('.', 'favicon.ico')

@app.route('/test')
def test_route():
    return "Server is working! HTML file should be at the root route /"

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'Server is running'}), 200

if __name__ == '__main__':
    print("🚀 Starting YouTube Extractor Server...")
    print("📍 Server will be available at: http://0.0.0.0:8080")
    print("🧪 Test route available at: http://0.0.0.0:8080/test")
    print("⚡ Press Ctrl+C to stop the server")
    app.run(debug=False, port=8080, host='0.0.0.0')