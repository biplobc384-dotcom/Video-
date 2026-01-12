import telebot
from telebot import types
import sqlite3
import yt_dlp
import os
import threading
import time
import random
from flask import Flask, send_from_directory
from datetime import datetime

# --- কনফিগারেশন ---
API_TOKEN = '8302172779:AAHLhBP1IVGm689BRXc741ui2-dbyoNfu5Y'
ADMIN_ID = 6740599881
ADMIN_USERNAME = 'Arifur905'
REQUIRED_CHANNEL = '@ArifurHackworld'
DOWNLOAD_COST = 5
REFERRAL_BONUS = 50

# Render URL (অটোমেটিক ডিটেক্ট করবে অথবা ম্যানুয়ালি বসাতে পারেন)
# উদাহরণ: https://your-app-name.onrender.com
BASE_URL = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:8080')

bot = telebot.TeleBot(API_TOKEN)
user_state = {}
db_lock = threading.Lock()

# --- Render Web Server & File Server ---
# ডাউনলোড ফোল্ডারকে পাবলিক করার জন্য কনফিগারেশন
app = Flask(__name__, static_folder='downloads')

@app.route('/')
def home():
    return f"⚡ AHW Bot is Running! {datetime.now()}"

# এই রাউটটি ফাইল ডাউনলোড করার জন্য লিংক তৈরি করবে
@app.route('/file/<path:filename>')
def serve_file(filename):
    return send_from_directory('downloads', filename, as_attachment=True)

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- অটোমেটিক ফাইল ক্লিনআপ (Render এর স্টোরেজ বাঁচানোর জন্য) ---
def cleanup_files():
    while True:
        try:
            now = time.time()
            if os.path.exists('downloads'):
                for f in os.listdir('downloads'):
                    fpath = os.path.join('downloads', f)
                    # ১০ মিনিটের বেশি পুরনো ফাইল ডিলিট করবে
                    if os.stat(fpath).st_mtime < now - 600:
                        os.remove(fpath)
                        print(f"Deleted old file: {f}")
        except: pass
        time.sleep(60)

# --- ডাটাবেস সেটআপ ---
def init_db():
    with db_lock:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, balance INTEGER, name TEXT, 
                      join_date TEXT, last_bonus TEXT, referrals INTEGER, is_banned INTEGER DEFAULT 0)''')
        conn.commit()
        conn.close()

def get_user_data(user_id, name="Unknown"):
    with db_lock:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute("SELECT balance, last_bonus, referrals, is_banned, join_date FROM users WHERE user_id=?", (user_id,))
            result = c.fetchone()
            if result is None:
                now = datetime.now().strftime("%Y-%m-%d")
                c.execute("INSERT INTO users (user_id, balance, name, join_date, last_bonus, referrals, is_banned) VALUES (?, ?, ?, ?, ?, ?, 0)", 
                          (user_id, 10, name, now, None, 0))
                conn.commit()
                data = (10, None, 0, 0, now)
            else:
                data = result
        except: data = (10, None, 0, 0, "N/A")
        finally: conn.close()
    return data

def update_balance(user_id, amount):
    with db_lock:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        conn.commit()
        conn.close()

def check_subscription(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if member.status in ['creator', 'administrator', 'member', 'restricted']:
            return True
    except: return True 
    return False

init_db()

# --- কীবোর্ড ---
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("⚡ ফাস্ট ডাউনলোড", "👤 প্রোফাইল")
    markup.add("🎰 লাকি স্পিন", "💸 ট্রান্সফার")
    markup.add("💎 টোকেন কিনুন", "👥 রেফার")
    if user_id == ADMIN_ID: markup.add("👑 অ্যাডমিন প্যানেল")
    return markup

def progress_bar(percent):
    filled = int(12 * percent // 100)
    bar = '▰' * filled + '▱' * (12 - filled)
    return bar

# --- হ্যান্ডলার ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    if not check_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        clean = REQUIRED_CHANNEL.replace('@', '')
        markup.add(types.InlineKeyboardButton("📢 জয়েন চ্যানেল", url=f"https://t.me/{clean}"))
        markup.add(types.InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_join"))
        bot.send_message(user_id, f"⚠️ বট ব্যবহার করতে হলে আমাদের চ্যানেলে জয়েন করুন।\n\nচ্যানেল: {REQUIRED_CHANNEL}", reply_markup=markup)
        return

    get_user_data(user_id, name)
    welcome_msg = (
        f"👋 **হ্যালো {name}! Render সার্ভারে স্বাগতম!**\n\n"
        "🚀 **ফিচার:**\n"
        "• ৫০MB এর নিচের ফাইল সরাসরি টেলিগ্রামে পাবেন।\n"
        "• ৫০MB এর ওপরের ফাইলের জন্য **হাই-স্পিড ডাউনলোড লিংক** পাবেন।\n\n"
        "যেকোনো লিংক দিন শুরু করতে!"
    )
    bot.reply_to(message, welcome_msg, reply_markup=main_menu(user_id), parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    user_id = m.from_user.id
    text = m.text
    bal, _, _, banned, _ = get_user_data(user_id, m.from_user.first_name)

    if banned: return

    # সিম্পল মেনু হ্যান্ডলিং
    if text == "👤 প্রোফাইল":
        bot.reply_to(m, f"💰 ব্যালেন্স: {bal} টোকেন")
    elif text == "⚡ ফাস্ট ডাউনলোড":
        bot.reply_to(m, "🚀 লিংক দিন, আমি প্রসেস করছি...")
    elif any(x in text.lower() for x in ['http', 'www', '.com', 'youtu']):
        if bal < DOWNLOAD_COST:
            bot.reply_to(m, "❌ ব্যালেন্স শেষ!")
            return
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Fast (Auto)", callback_data=f"dl|fast|{text}"))
        markup.add(types.InlineKeyboardButton("🎬 Best Quality (Link)", callback_data=f"dl|best|{text}"))
        markup.add(types.InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"dl|audio|{text}"))
        
        bot.reply_to(m, f"🔍 লিংক পাওয়া গেছে!\nকিভাবে ডাউনলোড করবেন?", reply_markup=markup)
    else:
        # অন্যান্য কমান্ড হ্যান্ডলিং (আপনার আগের কোডের মতো রাখতে পারেন)
        pass

# --- ডাউনলোড হ্যান্ডলার ---
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.from_user.id
    if call.data == "check_join":
        # জয়েন চেক লজিক (আপনার আগের মতো)
        bot.delete_message(uid, call.message.message_id)
        bot.send_message(uid, "✅ ধন্যবাদ!", reply_markup=main_menu(uid))
        return

    if call.data.startswith("dl|"):
        data = call.data.split('|')
        action = data[1]
        url = data[2]
        
        bot.delete_message(uid, call.message.message_id)
        threading.Thread(target=download_task, args=(uid, url, action)).start()

def download_task(uid, url, action):
    msg = bot.send_message(uid, "🔄 **সার্ভারে ডাউনলোড হচ্ছে...**", parse_mode="Markdown")
    last_update = [0]
    
    def hook(d):
        if d['status'] == 'downloading' and time.time() - last_update[0] > 4:
            try:
                p = d.get('_percent_str', '0%').replace('%','')
                bar = progress_bar(float(p))
                bot.edit_message_text(f"⚡ **সার্ভারে লোড হচ্ছে...**\n{bar} {d['_percent_str']}", uid, msg.message_id, parse_mode="Markdown")
                last_update[0] = time.time()
            except: pass

    # --- কনফিগারেশন ---
    # Render এ কুকিজ কাজ করাতে হলে কুকিজ ফাইল প্রোজেক্ট ফোল্ডারে থাকতে হবে
    opts = {
        'outtmpl': f'downloads/{uid}_%(title)s.%(ext)s', 
        'quiet': True, 
        'progress_hooks': [hook],
        'noplaylist': True,
        'cookiefile': 'cookies.txt', 
        'writethumbnail': True,
        'geo_bypass': True,
        'restrictfilenames': True,
    }
    
    if action == 'audio':
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]
        opts['outtmpl'] = f'downloads/{uid}_%(title)s.%(ext)s'
    else:
        # বেস্ট কোয়ালিটি ডাউনলোড হবে
        opts['format'] = 'bestvideo+bestaudio/best'

    fpath = None
    try:
        if not os.path.exists('downloads'): os.makedirs('downloads')
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if action == 'audio':
                fpath = ydl.prepare_filename(info).rsplit('.', 1)[0] + ".mp3"
            else:
                fpath = ydl.prepare_filename(info)
            
            title = info.get('title', 'Video')
            thumb = fpath.rsplit('.', 1)[0] + ".jpg"

        # --- ফাইল সাইজ চেক ---
        file_size_mb = os.path.getsize(fpath) / (1024 * 1024)
        
        # ৫০ MB এর বেশি হলে লিংক দেবে
        if file_size_mb > 49:
            file_name = os.path.basename(fpath)
            # Render URL জেনারেট
            download_link = f"{BASE_URL}/file/{file_name}"
            
            link_msg = (
                f"✅ **ডাউনলোড রেডি!**\n\n"
                f"🎬 **টাইটেল:** `{title}`\n"
                f"📦 **সাইজ:** {round(file_size_mb, 2)} MB\n"
                f"⚠️ **নোট:** ফাইলটি বড় হওয়ায় টেলিগ্রামে পাঠানো যাচ্ছে না। নিচ থেকে ডাউনলোড করুন।\n\n"
                f"🔗 **ডাউনলোড লিংক:**\n{download_link}\n\n"
                f"⏳ লিংকটি ১০ মিনিট পর এক্সপায়ার হবে।"
            )
            bot.edit_message_text(link_msg, uid, msg.message_id, parse_mode="Markdown")
            # ব্যালেন্স কাটবে না বা কম কাটতে পারেন
            
        else:
            # ৫০ MB এর কম হলে টেলিগ্রামে পাঠাবে
            bot.edit_message_text("📤 **টেলিগ্রামে আপলোড হচ্ছে...**", uid, msg.message_id, parse_mode="Markdown")
            with open(fpath, 'rb') as f:
                t = open(thumb, 'rb') if thumb and os.path.exists(thumb) else None
                try:
                    if action == 'audio': 
                        bot.send_audio(uid, f, caption=f"✅ `{title}`", thumbnail=t, parse_mode='Markdown')
                    else: 
                        bot.send_video(uid, f, caption=f"✅ `{title}`", thumbnail=t, parse_mode='Markdown', supports_streaming=True)
                    update_balance(uid, -DOWNLOAD_COST)
                except Exception as e:
                    bot.send_message(uid, f"⚠️ আপলোড এরর: {e}")

        # ছোট ফাইলের ক্ষেত্রে সাথে সাথে ক্লিনআপ
        if file_size_mb <= 49:
            try:
                os.remove(fpath)
                if thumb and os.path.exists(thumb): os.remove(thumb)
                bot.delete_message(uid, msg.message_id)
            except: pass

    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(uid, "❌ ডাউনলোড ফেইলড! ভিডিওটি খুব বড় বা রেস্ট্রিকটেড হতে পারে।")

if __name__ == "__main__":
    # ক্লিনআপ থ্রেড চালু করা
    threading.Thread(target=cleanup_files, daemon=True).start()
    
    # ওয়েব সার্ভার চালু করা
    t = threading.Thread(target=run_web_server)
    t.start()
    
    print(f"🚀 Bot Started on Render... URL: {BASE_URL}")
    bot.infinity_polling()
