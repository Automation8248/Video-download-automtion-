import os
import yt_dlp
import requests
import subprocess

# --- CONFIGURATION & SECRETS ---
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN") 
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LINKS_FILE = "link.txt"
MAX_MB_LIMIT = 40  # SAFE MARGIN: 50MB limit ke liye 40MB ka target rakhenge

def get_video_duration(file_path):
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"⚠️ Duration nikalne me error: {e}")
        return 0

def compress_video(input_path, output_path, target_mb):
    duration = get_video_duration(input_path)
    
    if duration == 0:
        print("❌ Video duration 0 hai, compression nahi ho sakta.")
        return False

    # Bitrate math
    target_total_bitrate = (target_mb * 8192) / duration
    audio_bitrate = 64  # Audio ko aur chota (64k) kar diya taaki video ko zyada size mile
    video_bitrate = int(target_total_bitrate - audio_bitrate)

    if video_bitrate < 100:
        video_bitrate = 100

    print(f"⚙️ Compressing... Strict Target Bitrate: {video_bitrate}kbps. Please wait...")
    
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-b:v', f'{video_bitrate}k',
        '-maxrate', f'{video_bitrate}k',     # STRICT LIMIT: Isse upar nahi jayega
        '-bufsize', f'{video_bitrate * 2}k', # Strict limit maintain karne ke liye
        '-c:v', 'libx264',
        '-preset', 'ultrafast',              # Super fast compression ke liye
        '-c:a', 'aac',
        '-b:a', f'{audio_bitrate}k',
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Compression error: {e}")
        return False

def send_to_telegram(file_path):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Error: Telegram Token ya Chat ID missing hai!")
        return False

    # STRICT DOUBLE CHECK BEFORE UPLOAD
    final_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if final_size_mb > 49.5:
        print(f"🚫 FINAL BLOCK: File size {final_size_mb:.2f} MB abhi bhi Telegram Bot limit (50MB) se zyada hai.")
        print("💡 Solution: File bahut hi jyada lambi (1-2 ghante ki) hai jisko 50MB me compress nahi kiya ja sakta. Kripya choti video try karein.")
        return False

    print(f"🚀 Uploading to Telegram (Size: {final_size_mb:.2f} MB)...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    
    try:
        with open(file_path, 'rb') as video:
            payload = {'chat_id': CHAT_ID, 'caption': 'Here is your automated video! 🤖'}
            files = {'video': video}
            response = requests.post(url, data=payload, files=files)
            
        if response.status_code == 200:
            print("✅ Successfully sent to Telegram!")
            return True
        else:
            print(f"❌ Upload Failed. Telegram API Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error uploading to Telegram: {e}")
        return False

def process_downloaded_file(info):
    if info:
        original_file = f"{info.get('extractor', 'unknown')}_{info.get('id', 'video')}_video.mp4"
        compressed_file = f"compressed_{original_file}"
        
        if os.path.exists(original_file):
            print("✅ Download Complete!")
            file_size_mb = os.path.getsize(original_file) / (1024 * 1024)
            print(f"📦 File size: {file_size_mb:.2f} MB")
            
            file_to_send = original_file
            
            if file_size_mb > MAX_MB_LIMIT:
                print("⚠️ File 40MB se badi hai! Compression chalu kar rahe hain...")
                success = compress_video(original_file, compressed_file, target_mb=MAX_MB_LIMIT)
                
                # Check karo compression hua ya nahi aur file size choti hui ya nahi
                if success and os.path.exists(compressed_file):
                    comp_size = os.path.getsize(compressed_file) / (1024 * 1024)
                    print(f"📉 New File Size: {comp_size:.2f} MB")
                    file_to_send = compressed_file
                else:
                    print("❌ Compression fail hua ya original use karna safe nahi hai. Upload rok rahe hain taaki API crash na ho.")
                    file_to_send = None # Cancel upload
            
            if file_to_send:
                send_to_telegram(file_to_send)
            
            # Cleanup
            if os.path.exists(original_file): os.remove(original_file)
            if os.path.exists(compressed_file): os.remove(compressed_file)
            print("🗑️ Cleaned up server files.")

def download_and_send(url):
    quality = os.getenv("VIDEO_QUALITY", "720p")
    print(f"\n🎯 Target Quality: {quality} for URL: {url}")

    if quality == "best (Highest available)":
        format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        height = quality.replace('p', '')
        format_string = f'bestvideo[height<=?{height}][ext=mp4]+bestaudio[ext=m4a]/best[height<=?{height}][ext=mp4]/best'

    ydl_opts = {
        'format': format_string,
        'merge_output_format': 'mp4',
        'outtmpl': '%(extractor)s_%(id)s_video.%(ext)s',
        'quiet': False,
        'no_warnings': True,
        'ignoreerrors': False, 
        'geo_bypass': True,
        'extractor_args': {'generic': {'impersonate': True}}, 
        'concurrent_fragment_downloads': 10,  
        'http_chunk_size': 10485760,          
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            process_downloaded_file(info)

    except Exception as e:
        if "videoModel" in str(e) or "ExtractorError" in str(e) or "KeyError" in str(e):
            print("🔄 Broken plugin detected! Raw HTML mode me retry kar rahe hain...")
            ydl_opts['force_generic_extractor'] = True
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    process_downloaded_file(info)
            except Exception as e2:
                print(f"❌ Dono attempts fail. Error: {e2}")

def main():
    if not os.path.exists(LINKS_FILE):
        print(f"❌ Error: '{LINKS_FILE}' nahi mila! GitHub me link.txt file banaiye.")
        return

    with open(LINKS_FILE, 'r') as file:
        links = [line.strip() for line in file if line.strip()]

    for link in links:
        download_and_send(link)

if __name__ == "__main__":
    main()
