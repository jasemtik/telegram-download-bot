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
TOKEN = '8447817377:AAGjY_CGHnrEcN3cxP91BKZuqJ_CHCLHXAY'  # التوكن الخاص بالبوت
DOWNLOAD_DIR = 'downloads'
COOKIES_FILE = 'cookies.txt'
PROXY_LIST = []

# إنشاء مجلد التحميلات
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# ==================== نظام البروكسي ====================
def update_proxies():
    """تحديث قائمة البروكسيات المجانية"""
    global PROXY_LIST
    try:
        url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            PROXY_LIST = response.text.splitlines()
            logger.info(f"✅ تم تحميل {len(PROXY_LIST)} بروكسي")
    except Exception as e:
        logger.error(f"❌ فشل تحميل البروكسيات: {e}")

update_proxies()

# ==================== إعدادات yt-dlp ====================
def get_ydl_opts(mode="video", use_proxy=False):
    """إعدادات التحميل"""
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1',
    ]
    
    opts = {
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        'user_agent': random.choice(user_agents),
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s_%(id)s.%(ext)s',
    }

    if use_proxy and PROXY_LIST:
        proxy = random.choice(PROXY_LIST)
        opts['proxy'] = f"http://{proxy}"

    if mode == "video":
        opts['format'] = 'best[height<=720][ext=mp4]/best[height<=720]/best'
    else:
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    
    return opts

# ==================== معالجة الأوامر ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_message = """
🎯 **مرحباً بك في بوت التحميل الشامل!**

📥 **ماذا يمكنني أن أفعل؟**
• تحميل فيديوهات من:
  - TikTok
  - Instagram
  - Facebook
  - YouTube
  - Twitter/X
  - والمزيد...

🎵 **ميزات البوت:**
• تحميل فيديو بصيغة MP4
• تحميل صوت بصيغة MP3
• بحث في YouTube
• دعم البروكسيات لتجاوز الحظر

🔍 **كيفية الاستخدام:**
• أرسل رابط فيديو للتحميل
• أو اكتب اسم أغنية/فنان للبحث
    """
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النصوص والروابط"""
    text = update.message.text
    
    if text.startswith(('http://', 'https://')):
        # إذا كان الرابط، عرض خيارات التحميل
        keyboard = [
            [InlineKeyboardButton("📺 تحميل فيديو (MP4)", callback_data=f"video_{text}")],
            [InlineKeyboardButton("🎵 تحميل صوت (MP3)", callback_data=f"audio_{text}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🔽 **اختر نوع التحميل:**", reply_markup=reply_markup, parse_mode='Markdown')
    
    else:
        # إذا كان نص عادي، البحث في YouTube
        status_message = await update.message.reply_text("🔍 **جاري البحث...**", parse_mode='Markdown')
        
        try:
            # إعدادات البحث
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # البحث عن 5 نتائج
                search_query = f"ytsearch5:{text}"
                search_results = ydl.extract_info(search_query, download=False)
                
                if search_results and 'entries' in search_results:
                    keyboard = []
                    for entry in search_results['entries']:
                        if entry:
                            title = entry.get('title', 'بدون عنوان')
                            short_title = title[:45] + '...' if len(title) > 45 else title
                            video_url = f"https://youtube.com/watch?v={entry['id']}"
                            keyboard.append([InlineKeyboardButton(f"🎬 {short_title}", callback_data=f"select_{video_url}")])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await status_message.edit_text("✅ **نتائج البحث:**", reply_markup=reply_markup, parse_mode='Markdown')
                else:
                    await status_message.edit_text("❌ **لا توجد نتائج للبحث**", parse_mode='Markdown')
        
        except Exception as e:
            await status_message.edit_text(f"❌ **حدث خطأ:** {str(e)[:100]}", parse_mode='Markdown')

# ==================== معالجة الأزرار ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("select_"):
        # تم اختيار فيديو من نتائج البحث
        url = data.replace("select_", "")
        keyboard = [
            [InlineKeyboardButton("📺 تحميل فيديو", callback_data=f"video_{url}")],
            [InlineKeyboardButton("🎵 تحميل MP3", callback_data=f"audio_{url}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🔽 **اختر الصيغة المطلوبة:**", reply_markup=reply_markup, parse_mode='Markdown')
    
    elif data.startswith(("video_", "audio_")):
        # بدء التحميل
        mode, url = data.split("_", 1)
        await query.edit_message_text(f"⏳ **جاري التحميل...**\nالنوع: {'📺 فيديو' if mode == 'video' else '🎵 MP3'}", parse_mode='Markdown')
        
        # محاولة التحميل (محاولتين)
        for attempt in range(2):
            try:
                # الحصول على إعدادات التحميل
                ydl_opts = get_ydl_opts(mode, use_proxy=(attempt == 1))
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # استخراج المعلومات والتحميل
                    info = ydl.extract_info(url, download=True)
                    
                    # تحديد مسار الملف
                    if mode == "video":
                        filename = ydl.prepare_filename(info)
                    else:
                        filename = ydl.prepare_filename(info)
                        filename = filename.rsplit('.', 1)[0] + '.mp3'
                    
                    # التحقق من وجود الملف
                    if not os.path.exists(filename):
                        for file in os.listdir(DOWNLOAD_DIR):
                            if info['id'] in file:
                                filename = os.path.join(DOWNLOAD_DIR, file)
                                break
                    
                    # إرسال الملف
                    with open(filename, 'rb') as f:
                        if mode == "video":
                            await query.message.reply_video(
                                video=f,
                                caption=f"🎥 **{info.get('title', 'فيديو')}**",
                                parse_mode='Markdown'
                            )
                        else:
                            await query.message.reply_audio(
                                audio=f,
                                title=info.get('title', 'أغنية'),
                                performer=info.get('uploader', 'فنان'),
                                parse_mode='Markdown'
                            )
                    
                    # حذف الملف بعد الإرسال
                    os.remove(filename)
                    
                    # حذف رسالة "جاري التحميل"
                    await query.message.delete()
                    
                    # إرسال رسالة نجاح
                    await query.message.reply_text("✅ **تم التحميل بنجاح!**", parse_mode='Markdown')
                    return  # نجاح التحميل
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ محاولة {attempt + 1} فشلت: {error_msg}")
                
                if attempt == 1:  # فشلت المحاولة الثانية
                    error_text = f"❌ **فشل التحميل**\nالخطأ: {error_msg[:150]}"
                    await query.message.reply_text(error_text, parse_mode='Markdown')
                    
                    # تحديث قائمة البروكسيات للمرة القادمة
                    if "proxy" in error_msg.lower() or "connection" in error_msg.lower():
                        update_proxies()

# ==================== تحديث البروكسيات تلقائياً ====================
async def scheduled_proxy_update():
    """تحديث البروكسيات كل ساعة"""
    while True:
        await asyncio.sleep(3600)  # ساعة
        update_proxies()
        logger.info("🔄 تم تحديث قائمة البروكسيات")

# ==================== تشغيل البوت ====================
def main():
    """تشغيل البوت"""
    
    # إنشاء التطبيق
    app = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # بدء مهمة تحديث البروكسيات في الخلفية
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(scheduled_proxy_update())
    
    # تشغيل البوت
    logger.info("✅ البوت يعمل الآن...")
    app.run_polling()

if __name__ == '__main__':
    main()