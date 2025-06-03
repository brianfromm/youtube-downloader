from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import yt_dlp
import os
import requests

app = Flask(__name__)
CORS(app)

# Serve the HTML file
@app.route('/')
def serve_html():
    try:
        return send_from_directory('.', 'youtube-extractor.html')
    except Exception as e:
        return f"Error serving HTML file: {str(e)}. Make sure 'youtube-extractor.html' is in the same directory as this server file."

@app.route('/extract', methods=['POST'])
def extract_video_info():
    try:
        print("=== EXTRACT REQUEST RECEIVED ===")
        data = request.json
        url = data.get('url')
        print(f"URL received: {url}")
        
        if not url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Configure yt-dlp options
        ydl_opts = {
            'quiet': False,  # Changed to False to see more output
            'no_warnings': False,  # Changed to False to see warnings
            'extract_flat': False,
        }
        
        print("Starting yt-dlp extraction...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f"Extraction completed. Title: {info.get('title', 'Unknown')}")
            
            # Extract relevant information
            video_data = {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration_string', 'Unknown'),
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': f"{info.get('view_count', 0):,}" if info.get('view_count') else 'Unknown',
                'upload_date': info.get('upload_date', 'Unknown'),
                'formats': []
            }
            
            print(f"Total formats found: {len(info.get('formats', []))}")
            
            # Debug: Let's see ALL formats first, then apply filtering
            all_format_info = []
            for fmt in info.get('formats', []):
                format_info = f"ID:{fmt.get('format_id')} | ext:{fmt.get('ext')} | {fmt.get('height')}p | protocol:{fmt.get('protocol')} | note:{fmt.get('format_note', '')} | acodec:{fmt.get('acodec')}"
                all_format_info.append(format_info)
                print(f"ALL FORMATS: {format_info}")
            
            # Simplified approach - show ALL formats with minimal filtering
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
                    
                    # Print ALL formats for debugging
                    print(f"Format: {fmt.get('format_id')} | {fmt.get('ext')} | {fmt.get('height')}p | {fmt.get('protocol')} | {fmt.get('format_note', '')}")
            
            print(f"Final format count: {len(video_data['formats'])}")
            
            # Sort formats by type and quality
            video_audio_formats = [f for f in video_data['formats'] if f['type'] == 'video+audio']
            video_only_formats = [f for f in video_data['formats'] if f['type'] == 'video-only']
            audio_only_formats = [f for f in video_data['formats'] if f['type'] == 'audio-only']
            other_formats = [f for f in video_data['formats'] if f['type'] == 'other']
            
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
            
            print("=== SENDING RESPONSE ===")
            return jsonify(video_data)
            
    except Exception as e:
        print(f"ERROR in extract_video_info: {str(e)}")
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
        
        print(f"Combining video format {video_format_id} with audio format {audio_format_id}")
        
        # Get video info for filename
        ydl_opts_info = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')
        
        # Clean filename
        import re
        clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
        clean_title = clean_title.replace(' ', '_')
        if len(clean_title) > 100:  # Changed from 50 to 100
            clean_title = clean_title[:100]

        # Get video resolution for filename
        video_resolution = "Unknown"
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                formats_info = ydl.extract_info(url, download=False)
                for fmt in formats_info.get('formats', []):
                    if fmt.get('format_id') == video_format_id:
                        if fmt.get('height'):
                            video_resolution = f"{fmt.get('height')}p"
                        break
        except:
            video_resolution = "Unknown"
        
        # Create temp directory for processing
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Working in temp directory: {temp_dir}")
            
            # Define output filename
            output_filename = f"{clean_title}_{video_resolution}.mp4"
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
                print(f"Attempting to download with format: {video_format_id}+{audio_format_id}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # Check if file exists
                if not os.path.exists(output_path):
                    # Try alternative approach - download separately and merge with FFmpeg
                    print("Direct combination failed, trying manual merge...")
                    return manual_combine(url, video_format_id, audio_format_id, clean_title, video_resolution, temp_dir)
                
                # Read and return the file
                with open(output_path, 'rb') as f:
                    video_data = f.read()
                
                print(f"Successfully combined video. File size: {len(video_data)} bytes")
                
                from flask import Response
                response = Response(
                    video_data,
                    mimetype='video/mp4',
                    headers={
                        'Content-Disposition': f'attachment; filename="{output_filename}"',
                        'Content-Length': str(len(video_data))
                    }
                )
                return response
                
            except Exception as e:
                print(f"yt-dlp combine error: {str(e)}")
                # Fallback to manual combination
                return manual_combine(url, video_format_id, audio_format_id, clean_title, video_resolution, temp_dir)
            
    except Exception as e:
        print(f"Error in combine_video_audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Combine error: {str(e)}'}), 500

def manual_combine(url, video_format_id, audio_format_id, clean_title, video_resolution, temp_dir):
    """Manually download video and audio, then combine with FFmpeg"""
    try:
        import subprocess
        import os
        
        print("Starting manual combination process...")
        
        video_path = os.path.join(temp_dir, 'video.mp4')
        audio_path = os.path.join(temp_dir, 'audio.m4a')
        output_path = os.path.join(temp_dir, f"{clean_title}_{video_resolution}.mp4")
        
        # Download video
        video_opts = {
            'format': video_format_id,
            'outtmpl': video_path,
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            ydl.download([url])
        
        # Download audio  
        audio_opts = {
            'format': audio_format_id,
            'outtmpl': audio_path,
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
        
        # Combine with FFmpeg
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path, 
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            output_path
        ]
        
        print(f"Running FFmpeg: {' '.join(ffmpeg_cmd)}")
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            return jsonify({'error': f'FFmpeg failed: {result.stderr}'}), 500
        
        # Read and return combined file
        with open(output_path, 'rb') as f:
            video_data = f.read()
        
        print(f"Manual combination successful. File size: {len(video_data)} bytes")
        
        from flask import Response
        response = Response(
            video_data,
            mimetype='video/mp4',
            headers={
                'Content-Disposition': f'attachment; filename="{clean_title}_{video_resolution}.mp4"',
                'Content-Length': str(len(video_data))
            }
        )
        return response
        
    except Exception as e:
        print(f"Manual combine error: {str(e)}")
        return jsonify({'error': f'Manual combine failed: {str(e)}'}), 500

@app.route('/download/<format_id>')
def download_file(format_id):
    try:
        # Get the URL from the query parameter
        video_url = request.args.get('url')
        if not video_url:
            return "URL parameter required", 400
        
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
                return "Format not found", 404
            
            # Clean up the title for use as filename
            title = info.get('title', 'video')
            import re
            clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
            clean_title = clean_title.replace(' ', '_')
            if len(clean_title) > 100:  # Changed from 50 to 100
                clean_title = clean_title[:100]
            
            # Get resolution for filename
            resolution = ""
            if selected_format.get('height'):
                resolution = f"_{selected_format.get('height')}p"
            elif selected_format.get('abr'):
                resolution = f"_{selected_format.get('abr')}kbps"
            
            filename = f"{clean_title}{resolution}.{selected_format.get('ext', 'mp4')}"
            
            # Redirect to the video URL with download headers
            from flask import redirect, make_response
            import requests
            
            # Stream the file with proper download headers
            video_response = requests.get(selected_format.get('url'), stream=True)
            
            def generate():
                for chunk in video_response.iter_content(chunk_size=8192):
                    yield chunk
            
            response = make_response(generate())
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.headers['Content-Type'] = 'application/octet-stream'
            
            return response
            
    except Exception as e:
        print(f"Error in download_file: {str(e)}")
        return f"Download error: {str(e)}", 500

@app.route('/test')
def test_route():
    return "Server is working! HTML file should be at the root route /"

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'Server is running'}), 200

if __name__ == '__main__':
    print("Starting YouTube Extractor Server...")
    print("Server will be available at: http://0.0.0.0:8080")
    print("Test route available at: http://0.0.0.0:8080/test")
    print("Press Ctrl+C to stop the server")
    app.run(debug=False, port=8080, host='0.0.0.0')