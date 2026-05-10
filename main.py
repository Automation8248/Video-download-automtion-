import os
import yt_dlp
import requests
import subprocess

# --- CONFIGURATION & SECRETS ---
# Note: Aapke environment me TELEGRAM_TOKEN use hota hai, isliye wahi rakha gaya hai
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN") 
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LINKS_FILE = "link.txt"
MAX_MB_LIMIT = 48  # 50MB limit hoti hai, hum safe side 48MB le rahe hain

def get_video_duration(file_path):
    """FFmpeg ki madad se video ki length (seconds) nikalta hai."""
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
    """Video ko target size (MB) ke andar forcefully compress karta hai."""
    duration = get_video_duration(input_path)
    
    if duration == 0:
        print("❌ Video duration 0 hai, compression fail ho sakta hai.")
        return False

    # Exact bitrate calculate karna taaki file 50MB ke andar aaye
    # Formula: Total Bitrate (kbps) = (Target Size in KB) / Duration in seconds
    target_total_bitrate = (target_mb * 8192) / duration
    audio_bitrate = 128  # Audio ko 128kbps denge
    video_bitrate = int(target_total_bitrate - audio_bitrate)

    # Agar video bahut lamba hai, toh bitrate bahut kam ho jayega
    if video_bitrate < 100:
        print("⚠️ Video bahut lamba hai! Quality bahut blur ho jayegi lekin hum phir bhi compress kar rahe hain.")
        video_bitrate = 100

    print(f"⚙️ Compressing Video... Target Bitrate: {video_bitrate}kbps. Isme thoda time lag sakta hai...")
    
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-b:v', f'{video_bitrate}k',
        '-c:v', 'libx264',
        '-preset', 'fast',  # 'fast' speed ke liye, GitHub action ka time bachane ke liye
        '-c:a', 'aac',
        '-b:a', f'{audio_bitrate}k',
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ Compression successful!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Compression error: {e}")
        return False

def send_to_telegram(file_path):
    """Video ko Telegram par bhejta hai."""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Error: Telegram Token ya Chat ID missing hai!")
        return False

    print("🚀 Uploading to Telegram... kripya wait karein.")
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

def download_and_send(url):
    """Video download karega aur agar zaroorat padi toh compress bhi karega."""
    quality = os.getenv("VIDEO_QUALITY", "720p")
    print(f"\n🎯 Target Quality: {quality} for URL: {url}")

    if quality == "best (Highest available)":
        format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        height = quality.replace('p', '')
        # Yahan '?' add kiya hai: agar site ko height nahi pata, toh wo size/bitrate ke hisaab se best match uthayega
        format_string = f'bestvideo[height<=?{height}][ext=mp4]+bestaudio[ext=m4a]/best[height<=?{height}][ext=mp4]/best'

    ydl_opts = {
        'format': format_string,
        'merge_output_format': 'mp4',
        'outtmpl': '%(extractor)s_%(id)s_video.%(ext)s',
        'quiet': False,
        'no_warnings': True,
        'ignoreerrors': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'extractor_args': {'generic': {'impersonate': True}}, 
        'concurrent_fragment_downloads': 10,  
        'http_chunk_size': 10485760,          
        'buffersize': 1024 * 1024 * 5,        
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"🔗 Extracting Video Details...")
            info = ydl.extract_info(url, download=False)
            
            if info:
                print(f"📥 Starting download...")
                ydl.download([url])
                
                original_file = f"{info.get('extractor', 'unknown')}_{info.get('id', 'video')}_video.mp4"
                compressed_file = f"compressed_{original_file}"
                
                if os.path.exists(original_file):
                    print("✅ Download Complete!")
                    
                    # File Size Check
                    file_size_mb = os.path.getsize(original_file) / (1024 * 1024)
                    print(f"📦 Original File size: {file_size_mb:.2f} MB")
                    
                    file_to_send = original_file

                    # Agar 50MB limit se bada hai, toh compress karo
                    if file_size_mb > MAX_MB_LIMIT:
                        print(f"⚠️ File 50MB se badi hai! Compression chalu kar rahe hain...")
                        success = compress_video(original_file, compressed_file, target_mb=MAX_MB_LIMIT)
                        if success and os.path.exists(compressed_file):
                            new_size = os.path.getsize(compressed_file) / (1024 * 1024)
                            print(f"📉 New File Size: {new_size:.2f} MB")
                            file_to_send = compressed_file
                        else:
                            print("❌ Compression fail ho gaya. Original file send karne ka try kar rahe hain (par shayad limit lag jaye).")
                    
                    # Telegram par bhejna
                    send_to_telegram(file_to_send)
                    
                    # Safai abhiyan (Local files delete karna)
                    if os.path.exists(original_file):
                        os.remove(original_file)
                    if os.path.exists(compressed_file):
                        os.remove(compressed_file)
                    print("🗑️ Cleaned up server files.")
                else:
                    print("❌ File save nahi ho payi.")
            else:
                print("❌ Extract fail! Yeh website heavily protected hai.")

    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    if not os.path.exists(LINKS_FILE):
        print(f"❌ Error: '{LINKS_FILE}' nahi mila! GitHub me link.txt file banaiye.")
        return

    with open(LINKS_FILE, 'r') as file:
        links = [line.strip() for line in file if line.strip()]

    if not links:
        print("⚠️ link.txt khali hai.")
        return

    for link in links:
        download_and_send(link)

if __name__ == "__main__":
    main()
