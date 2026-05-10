import os
import yt_dlp
import requests

# --- CONFIGURATION ---
# We use environment variables so you don't hardcode secrets on GitHub
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LINKS_FILE = "link.txt"

def send_to_telegram(file_path):
    """Sends the downloaded video to Telegram."""
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: Telegram Bot Token or Chat ID is missing!")
        return False

    # Check file size (Telegram Bot API limit is 50MB)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    print(f"File size: {file_size_mb:.2f} MB")
    
    if file_size_mb > 50:
        print(f"❌ Skipping Telegram upload. File ({file_size_mb:.2f}MB) exceeds the 50MB bot limit.")
        return False

    print("Uploading to Telegram... this might take a minute.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    
    try:
        with open(file_path, 'rb') as video:
            payload = {'chat_id': CHAT_ID, 'caption': 'Here is your high-quality video!'}
            files = {'video': video}
            response = requests.post(url, data=payload, files=files)
            
        if response.status_code == 200:
            print("✅ Successfully sent to Telegram!")
            return True
        else:
            print(f"❌ Failed to send. Telegram API Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error uploading to Telegram: {e}")
        return False

def download_and_send(url):
    """Force downloads the highest quality video and sends it."""
    # yt-dlp configuration to force 1080p/4K and merge to mp4
    ydl_opts = {
        # Force best video (up to 4K) + best audio
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        # Name the file uniquely to avoid overwriting
        'outtmpl': '%(id)s_video.%(ext)s',
        'quiet': False,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"\n--- Processing: {url} ---")
            
            # Extract info to get the exact filename
            info = ydl.extract_info(url, download=True)
            
            # Construct the final expected filename (since we force merge to mp4)
            file_path = f"{info['id']}_video.mp4"
            
            if os.path.exists(file_path):
                print("✅ Download complete.")
                
                # Send to Telegram
                send_to_telegram(file_path)
                
                # Cleanup: Delete file from server after sending
                os.remove(file_path)
                print("🗑️ Cleaned up local file.")
            else:
                print("❌ Download failed: File not found after download.")

    except Exception as e:
        print(f"❌ An error occurred with yt-dlp: {e}")

def main():
    # Check if the text file exists
    if not os.path.exists(LINKS_FILE):
        print(f"Error: {LINKS_FILE} not found!")
        return

    # Read links from the file, ignoring empty lines
    with open(LINKS_FILE, 'r') as file:
        links = [line.strip() for line in file if line.strip()]

    if not links:
        print("No links found in the file.")
        return

    # Process each link
    for link in links:
        download_and_send(link)

if __name__ == "__main__":
    main()
