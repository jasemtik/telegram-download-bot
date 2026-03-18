import os
import random
import requests
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import yt_dlp

# ==================== إعدادات التسجيل ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== الإعدادات الأساسية ====================
# قراءة التوكن والكوكيز من بيئة العمل (GitHub Secrets)
TOKEN = os.getenv('BOT_TOKEN', '8447817377:AAEJy2vZ5CmyAnVQdPernH3GD7PCWbZiWkE')
COOKIES_CONTENT = os.getenv('YOUTUBE_COOKIES') # محتوى ملف الكوكيز النصي
DOWNLOAD_DIR = 'downloads'
COOKIES_FILE = 'cookies.txt'
PROXY_LIST = []

# إنشاء مجلد التحميلات
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# إنشاء ملف الكوكيز برمجياً إذا كان متوفراً في Secrets
if COOKIES_CONTENT:
    with open(COOKIES_FILE, 'w') as f:
        f.write(COOKIES_CONTENT)
    logger.info("✅ تم إنشاء ملف الكوكيز من إعدادات السيرفر")

# ==================== نظام البروكسي ====================
def update_proxies():
    global PROXY_LIST
    try:
        url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            PROXY_LIST = [p.strip() for p in response.text.splitlines() if p.strip()]
            logger.info(f"✅ تم تحميل {len(PROXY_LIST)} بروكسي")
    except Exception as e:
        logger.error(f"❌ فشل تحميل البروكسيات: {e}")

update_proxies()

# ==================== إعدادات yt-dlp المحسنة ====================
def get_ydl_opts(mode="video", use_proxy=False):
    """إعدادات قوية لتجاوز خطأ Failed to extract player response"""
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    opts = {
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        'user_agent': random.choice(user_agents),
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s_%(id)s.%(ext)s',
        # الإضافة السحرية لتجاوز الحظر:
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
                'player_skip': ['webpage']
            }
        },
    }

    if use_proxy and PROXY_LIST:
        proxy = random.choice(PROXY_LIST)
        opts['proxy'] = f"http://{proxy}"

    if mode == "video":
        opts['format'] = 'best[height<=720][ext=mp4]/best'
    else:
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    
    return opts

# ==================== معالجة النصوص والبحث ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 **مرحباً بك!**\nأرسل رابط فيديو أو اسم للبحث.", parse_mode='Markdown')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith(('http://', 'https://')):
        keyboard = [
            [InlineKeyboardButton("📺 تحميل فيديو", callback_data=f"video_{text}")],
            [InlineKeyboardButton("🎵 تحميل MP3", callback_data=f"audio_{text}")]
        ]
        await update.message.reply_text("🔽 **اختر الصيغة:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        status = await update.message.reply_text("🔍 **جاري البحث...**")
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                search_results = ydl.extract_info(f"ytsearch5:{text}", download=False)
                if search_results and 'entries' in search_results:
                    keyboard = [[InlineKeyboardButton(f"🎬 {e['title'][:45]}...", callback_data=f"select_https://youtube.com/watch?v={e['id']}")] for e in search_results['entries'] if e]
                    await status.edit_text("✅ **نتائج البحث:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except Exception as e:
            await status.edit_text(f"❌ حدث خطأ: {str(e)[:50]}")

# ==================== معالجة التحميل والضغط ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("select_"):
        url = data.replace("select_", "")
        keyboard = [[InlineKeyboardButton("📺 فيديو", callback_data=f"video_{url}"), InlineKeyboardButton("🎵 MP3", callback_data=f"audio_{url}")]]
        await query.edit_message_text("🔽 **اختر النوع:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith(("video_", "audio_")):
        mode, url = data.split("_", 1)
        progress = await query.edit_message_text("⏳ **جاري التحميل...**")
        
        success = False
        for attempt in [False, True]: # محاولة بدون بروكسي ثم ببروكسي
            try:
                opts = get_ydl_opts(mode, use_proxy=attempt)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    if mode == "audio": filename = filename.rsplit('.', 1)[0] + '.mp3'
                    
                    with open(filename, 'rb') as f:
                        if mode == "video":
                            await query.message.reply_video(video=f, caption=f"🎥 {info.get('title')}")
                        else:
                            await query.message.reply_audio(audio=f, title=info.get('title'))
                    
                    if os.path.exists(filename): os.remove(filename)
                    success = True
                    break
            except Exception as e:
                logger.error(f"فشل: {e}")
                continue
        
        await progress.delete()
        if not success:
            await query.message.reply_text("❌ فشل التحميل. قد يكون الرابط محمي أو السيرفر محظور.")

# ==================== التشغيل ====================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🚀 البوت بدأ العمل...")
    app.run_polling()

if __name__ == '__main__':
    main()
