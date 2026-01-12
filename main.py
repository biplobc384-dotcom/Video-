import telebot
from telebot import types
import sqlite3
import yt_dlp
import os
import threading
import time
import random
from flask import Flask, send_from_directory, render_template_string
from datetime import datetime

# --- কনফিগারেশন ---
API_TOKEN = '8302172779:AAGZMbcQoITVviIrIoWFcqMlFp5PMH7Z_QM'
ADMIN_ID = 6740599881
ADMIN_USERNAME = 'Arifur905'
REQUIRED_CHANNEL = '@ArifurHackworld'
DOWNLOAD_COST = 5

# Render URL
BASE_URL = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:8080')

bot = telebot.TeleBot(API_TOKEN)
db_lock = threading.Lock()
user_current_url = {} 

# --- Web Server & Video Player ---
app = Flask(__name__, static_folder='downloads')

# ১. হোমপেজ
@app.route('/')
def home():
    return f"⚡ Secure Player Running! {datetime.now()}"

# ২. ফাইল সার্ভ করার জন্য (Video Source)
@app.route('/file/<path:filename>')
def serve_file(filename):
    return send_from_directory('downloads', filename)

# ৩. ভিডিও প্লেয়ার পেজ (ভিডিও সাইটের ভেতর চলবে)
@app.route('/watch/<path:filename>')
def watch_video(filename):
    # HTML Player Template
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AHW Secure Player</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ background-color: #0e0e0e; color: white; font-family: sans-serif; text-align: center; padding: 20px; }}
            .container {{ max_width: 800px; margin: auto; }}
            video {{ width: 100%; border-radius: 10px; box-shadow: 0 0 20px rgba(0,255,0,0.2); }}
            .btn {{ display: inline-block; padding: 10px 20px; margin-top: 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; }}
            h2 {{ color: #00ff88; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🎬 AHW Premium Player</h2>
            <p>ভিডিওটি প্লে করতে নিচের প্লেয়ার ব্যবহার করুন</p>
            
            <video controls autoplay>
                <source src="/file/{filename}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
            
            <br><br>
            <a href="/file/{filename}" class="btn" download>📥 Download Video</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- অটো ক্লিনআপ (১৫ মিনিট পর ডিলিট হবে) ---
def cleanup_files():
    while True:
        try:
            now = time.time()
            if os.path.exists('downloads'):
                for f in os.listdir('downloads'):
                    fpath = os.path.join('downloads', f)
                    if os.stat(fpath).st_mtime < now - 900: # ১৫ মিনিট
                        os.remove(fpath)
        except: pass
        time.sleep(60)

# --- ডাটাবেস ফাংশন ---
def init_db():
    with db_lock:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        conn.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER)''')
        conn.commit()
        conn.close()

def get_balance(user_id):
    with db_lock:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        res = c.fetchone()
        conn.close()
        if res: return res[0]
        else:
            with db_lock:
                conn = sqlite3.connect('users.db', check_same_thread=False)
                conn.execute("INSERT INTO users VALUES (?, ?)", (user_id, 10))
                conn.commit()
                conn.close()
            return 10

def update_balance(user_id, amount):
    with db_lock:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        conn.commit()
        conn.close()

init_db()

# --- বট কমান্ডস ---
@bot.message_handler(commands=['start'])
def start(m):
    welcome = (
        "🛡️ **Safe Video Downloader**\n\n"
        "যেকোনো ভিডিওর লিংক দিন। আমি সেটি একটি **সিকিউর প্রাইভেট প্লেয়ারে** ওপেন করে দেব।\n\n"
        "✅ ১৮+ বা যেকোনো ভিডিও নিরাপদভাবে দেখুন।\n"
        "🚫 টেলিগ্রামে কোনো ফাইল আপলোড হবে না (বট সেফ থাকবে)।"
    )
    bot.reply_to(m, welcome, parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    uid = m.from_user.id
    text = m.text
    bal = get_balance(uid)

    if any(x in text.lower() for x in ['http', 'www', '.com']):
        if bal < DOWNLOAD_COST:
            bot.reply_to(m, "❌ ব্যালেন্স শেষ!")
            return
        
        user_current_url[uid] = text.strip()
        
        markup = types.InlineKeyboardMarkup()
        # এখানে বাটন চেঞ্জ করা হয়েছে - সরাসরি প্লেয়ারে নিবে
        markup.add(types.InlineKeyboardButton("▶️ Watch Online (Safe Mode)", callback_data="dl|web"))
        
        bot.reply_to(m, "🔗 **লিংক রিসিভড!**\nভিডিওটি জেনারেট করতে নিচের বাটনে চাপ দিন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.from_user.id
    if call.data == "dl|web":
        url = user_current_url.get(uid)
        if not url:
            bot.answer_callback_query(call.id, "⚠️ লিংক এক্সপায়ার হয়ে গেছে।")
            return
        
        bot.delete_message(uid, call.message.message_id)
        threading.Thread(target=process_video, args=(uid, url)).start()

def process_video(uid, url):
    msg = bot.send_message(uid, "🔄 **সার্ভারে প্রসেস হচ্ছে...**\nদয়া করে অপেক্ষা করুন।")
    
    # কুকিজ ছাড়া কনফিগারেশন
    opts = {
        'outtmpl': f'downloads/{uid}_%(title)s.%(ext)s', 
        'quiet': True,
        'noplaylist': True,
        'format': 'best', # সাইটের প্লেয়ারের জন্য বেস্ট কোয়ালিটি
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'referer': 'https://www.google.com/',
        'nocheckcertificate': True,
        'geo_bypass': True,
    }

    try:
        if not os.path.exists('downloads'): os.makedirs('downloads')
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fpath = ydl.prepare_filename(info)
            file_name = os.path.basename(fpath)
            title = info.get('title', 'Video')

        # --- এখানে আসল ম্যাজিক ---
        # ফাইল টেলিগ্রামে না পাঠিয়ে, ওয়েবসাইটের লিংক দেওয়া হচ্ছে
        watch_link = f"{BASE_URL}/watch/{file_name}"
        
        safe_msg = (
            f"✅ **ভিডিও রেডি!**\n\n"
            f"🎬 **টাইটেল:** `{title}`\n"
            f"🛡️ **মোড:** Safe Web Player\n\n"
            f"নিচের লিংকে ক্লিক করে ভিডিওটি দেখুন বা ডাউনলোড করুন:\n"
            f"👉 [এখানে ক্লিক করুন (Watch Now)]({watch_link})\n\n"
            f"⚠️ লিংকটি ১৫ মিনিট পর মুছে যাবে।"
        )
        
        # ব্যালেন্স কাটা
        update_balance(uid, -DOWNLOAD_COST)
        
        bot.edit_message_text(safe_msg, uid, msg.message_id, parse_mode="Markdown")

    except Exception as e:
        print(e)
        bot.edit_message_text("❌ ভিডিওটি প্রসেস করা যায়নি।", uid, msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=cleanup_files, daemon=True).start()
    t = threading.Thread(target=run_web_server)
    t.start()
    print(f"🚀 Safe Bot Started on: {BASE_URL}")
    bot.infinity_polling()
