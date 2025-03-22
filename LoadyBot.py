import telebot # Library for Telegram API
import requests # Library for making HTTP requests
import instaloader # Library for downloading Instagram media
import time # Library for working with time
import yt_dlp # Library for downloading YouTube media
import logging # Library for logging
from urllib.parse import urlparse # Library for parsing URLs
from collections import defaultdict # Library for working with dictionaries

# Set up logging
logging.basicConfig(
    filename='social_downloader.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Logging is better than print in terminal for debugging because it's easier to filter out errors from other messages

BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN' # Replace with your bot token
bot = telebot.TeleBot(BOT_TOKEN)

# Rate limiting setup
user_cooldown = defaultdict(int)
COOLDOWN_SECONDS = 15

# Function to handle TikTok media
def get_tiktok_media(url):
    try:
        api_url = f"https://www.tikwm.com/api/?url={url}" # API URL
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        if data.get("code") != 0:
            return []

        media_items = []
        result_data = data.get("data", {})
        
        # Handle images with audio
        if 'images' in result_data:
            for img in result_data['images']:
                if isinstance(img, str):
                    image_url = img
                    if not image_url.startswith('http'):
                        image_url = f'https://www.tikwm.com{image_url}'
                    media_items.append(('image', image_url))
            
            if 'music' in result_data:
                music_data = result_data['music']
                audio_url = None
                
                if isinstance(music_data, dict):
                    audio_url = music_data.get('play_url', '')
                elif isinstance(music_data, str):
                    audio_url = music_data
                
                if audio_url:
                    if not audio_url.startswith('http'):
                        audio_url = f'https://www.tikwm.com{audio_url}'
                    media_items.append(('audio', audio_url))

        elif 'play' in result_data:
            video_url = result_data['play']
            if isinstance(video_url, str):
                if not video_url.startswith('http'):
                    video_url = f'https://www.tikwm.com{video_url}'
                media_items.append(('video', video_url))

        return media_items

    except Exception as e:
        logging.error(f"TikTok API Error: {str(e)}", exc_info=True)
        return []

# Function to handle Instagram media
def get_instagram_media(url):
    try:
        loader = instaloader.Instaloader()
        shortcode = url.split("/")[-2]
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        
        media_items = []
        
        if post.mediacount > 1:
            for node in post.get_sidecar_nodes():
                if node.is_video:
                    media_items.append(('video', node.video_url))
                else:
                    media_items.append(('image', node.display_url))
        else:
            if post.is_video:
                media_items.append(('video', post.video_url))
            else:
                media_items.append(('image', post.url))
                
        return media_items
        
    except Exception as e:
        logging.error(f"Instagram Error: {str(e)}", exc_info=True)
        return []

# Function to handle YouTube media
def get_youtube_download_url(youtube_url):
    try:
        ydl_opts = {'format': 'best', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            return [('video', info.get("url"))]
    except Exception as e:
        logging.error(f"YouTube Error: {str(e)}", exc_info=True)
        return []

# Function to handle LinkedIn media (even though I still don't think anybody would want to download LinkedIn videos)
def get_linkedin_media(url):
    try:
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'referer': 'https://www.linkedin.com/'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'url' in info:
                return [('video', info.get("url"))]
            return []
    except Exception as e:
        logging.error(f"LinkedIn Error: {str(e)}", exc_info=True)
        return []

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

# Command handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_msg = (
        "🌟 Welcome to Social Media Downloader Bot! 🌟\n\n"
        "✅ Supported Content:\n"
        "• TikTok: Videos, Images & Audio\n"
        "• Instagram: Posts, Carousels & Reels\n"
        "• YouTube: Videos & Shorts\n"
        "• LinkedIn: Public Videos\n\n"
        "⚠️ Limitations:\n"
        "- Max file size: 50MB\n"
        "- Cooldown: 15 seconds\n"
        "- Public posts only\n\n"
        "⬇️ Send a valid link to get started!"
    )
    bot.reply_to(message, welcome_msg)

# Checks if the user is on cooldown
def check_cooldown(user_id):
    current_time = time.time()
    if current_time - user_cooldown[user_id] < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (current_time - user_cooldown[user_id]))
        return remaining
    user_cooldown[user_id] = current_time
    return 0
# I added cooldown to prevent users from spamming the bot


# Message handler
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    if remaining := check_cooldown(user_id):
        bot.reply_to(message, f"⏳ Please wait {remaining} seconds before your next request.") # Cooldown message
        return

    url = message.text.strip()
    if not is_valid_url(url):
        bot.reply_to(message, "❌ Invalid URL format. Please send a valid link.") # Invalid URL message
        return

    try:
        parsed_url = urlparse(url)
        if "tiktok.com" in url or "tiktok" in parsed_url.netloc: # Check for both "tiktok.com" and "tiktok"
            process_media(message, 'tiktok')
        elif "instagram.com" in parsed_url.netloc: # Check for "instagram.com"
            process_media(message, 'instagram')
        elif "youtube.com" in parsed_url.netloc or "youtu.be" in parsed_url.netloc: # Check for both "youtube.com" and "youtu.be"
            process_media(message, 'youtube')
        elif "linkedin.com" in parsed_url.netloc: # Check for "linkedin.com"
            process_media(message, 'linkedin')
        else:
            bot.reply_to(message, "❌ Unsupported platform. Supported: TikTok, Instagram, YouTube, LinkedIn") 
    except Exception as e:
        logging.error(f"Main Handler Error: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ An error occurred. Please try again later.") 

# Function to process media
def process_media(message, platform):
    try:
        if platform == 'tiktok':
            media_items = get_tiktok_media(message.text)
        elif platform == 'instagram':
            media_items = get_instagram_media(message.text)
        elif platform == 'youtube':
            media_items = get_youtube_download_url(message.text)
        elif platform == 'linkedin':
            media_items = get_linkedin_media(message.text)
        else:
            return

        if not media_items:
            raise ValueError("No media found or invalid URL")

        bot.send_message(message.chat.id, f"📥 Found {len(media_items)} item(s). Starting download...")

        for index, (media_type, media_url) in enumerate(media_items):
            try:
                if media_type == 'video':
                    bot.send_chat_action(message.chat.id, 'upload_video')
                elif media_type == 'image':
                    bot.send_chat_action(message.chat.id, 'upload_photo')
                elif media_type == 'audio':
                    bot.send_chat_action(message.chat.id, 'upload_audio')

                referer = {
                    'tiktok': 'https://www.tiktok.com/',
                    'linkedin': 'https://www.linkedin.com/'
                }.get(platform, "")
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", # FYI: I don't know why, but sometimes bot used to break due to http link and this fixed it. 
                    "Referer": referer
                }
                
                response = requests.get(media_url, headers=headers, stream=True, timeout=30)
                response.raise_for_status()
                
                content_length = int(response.headers.get('content-length', 0))
                if content_length > 50 * 1024 * 1024:
                    bot.send_message(message.chat.id, f"❌ Media {index+1} exceeds 50MB limit")
                    continue

                if media_type == 'video':
                    bot.send_video(message.chat.id, response.content)
                elif media_type == 'image':
                    bot.send_photo(message.chat.id, response.content)
                elif media_type == 'audio':
                    bot.send_audio(message.chat.id, response.content,
                                 title="TikTok Audio",
                                 performer="Original Sound")
                
                time.sleep(1)

            except Exception as e:
                logging.error(f"{platform.capitalize()} Media {index+1} Error: {str(e)}", exc_info=True)
                bot.send_message(message.chat.id, f"⚠️ Failed to download media {index+1}") # Error message

        bot.send_message(message.chat.id, "✅ Download complete!") # Success message

    # Handle exceptions
    except Exception as e:
        logging.error(f"{platform.capitalize()} Error: {str(e)}", exc_info=True)
        error_msg = {
            'tiktok': "❌ Failed to download TikTok content. Ensure:\n1. Link is valid\n2. Video isn't private\n3. URL format: https://www.tiktok.com/@user/video/123",
            'instagram': "❌ Failed to download Instagram content. Ensure:\n1. Post is public\n2. Account isn't private\n3. URL is valid",
            'youtube': "❌ Failed to download YouTube video. Ensure:\n1. Video is available\n2. Not age-restricted\n3. Under 15 minutes",
            'linkedin': "❌ Failed to download LinkedIn video. Ensure:\n1. Video is from public post\n2. URL is valid\n3. Not a live stream"
        }.get(platform, "❌ Download failed")
        bot.reply_to(message, error_msg)

if __name__ == "__main__":
    print("Bot status: ONLINE") # Status message
    bot.polling()