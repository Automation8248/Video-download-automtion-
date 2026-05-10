import os
import yt_dlp
import requests

# --- CONFIGURATION & SECRETS ---
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN") 
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LINKS_FILE = "link.txt"

def send_to_telegram(file_path):
    """Downloads hone ke baad video ko Telegram par bhejta hai."""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Error: Telegram Token ya Chat ID missing hai!")
        return False

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    print(f"📦 File size: {file_size_mb:.2f} MB")
    
    if file_size_mb > 50:
        print(f"⚠️ Skipping Telegram upload. File ({file_size_mb:.2f}MB) Telegram bot ki 50MB limit se badi hai.")
        print("💡 Tip: GitHub Actions me chhoti quality (720p/480p) select karein.")
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
    """Video ko selected quality me fastest speed ke sath download karta hai."""
    
    quality = os.getenv("VIDEO_QUALITY", "720p")
    print(f"\n🎯 Target Quality: {quality}")

    if quality == "best (Highest available)":
        format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        height = quality.replace('p', '')
        format_string = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    # --- FASTEST DOWNLOAD LOGIC ---
    ydl_opts = {
        'format': format_string,
        'merge_output_format': 'mp4',
        'outtmpl': '%(id)s_video.%(ext)s',
        'quiet': False,
        'no_warnings': True,
        'concurrent_fragment_downloads': 10,  
        'http_chunk_size': 10485760,          
        'buffersize': 1024 * 1024 * 5,        
        'retries': 5,                         
        'fragment_retries': 5,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"🔗 Processing Link: {url}")
            
            info = ydl.extract_info(url, download=True)
            file_path = f"{info['id']}_video.mp4"
            
            if os.path.exists(file_path):
                print("✅ Download Complete at maximum speed!")
                
                send_to_telegram(file_path)
                
                os.remove(file_path)
                print("🗑️ Cleaned up local file from server.")
            else:
                print("❌ Download failed: File nahi mili.")

    except Exception as e:
        print(f"❌ yt-dlp Error: {e}")

def main():
    if not os.path.exists(LINKS_FILE):
        print(f"❌ Error: '{LINKS_FILE}' nahi mila! GitHub me link.txt file banaiye.")
        return

    with open(LINKS_FILE, 'r') as file:
        links = [line.strip() for line in file if line.strip()]

    if not links:
        print("⚠️ link.txt khali hai. Koi links nahi mile.")
        return

    for link in links:
        download_and_send(link)

if __name__ == "__main__":
    main()
