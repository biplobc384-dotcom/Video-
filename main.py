import telebot
from telebot import types
import sqlite3
import yt_dlp
import os
import threading
import time
import requests
from flask import Flask, send_from_directory, render_template_string
from datetime import datetime

# --- কনফিগারেশন ---
API_TOKEN = '8302172779:AAEd0TvYOHNGJ_N_V5SSevkdUOKX5fGKy6c'
ADMIN_ID = 6740599881
# Render URL (অটোমেটিক)
BASE_URL = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:8080')

bot = telebot.TeleBot(API_TOKEN)
db_lock = threading.Lock()
user_current_url = {}  # লিংক মেমোরিতে রাখার জন্য (Button fix)

# --- Web Server ---
app = Flask(__name__)

@app.route('/')
def home():
    return f"⚡ Bot is Alive! {datetime.now()}"

@app.route('/file/<path:filename>')
def serve_file(filename):
    # ফাইল ডাউনলোড লিংক
    return send_from_directory('downloads', filename)

@app.route('/watch/<path:filename>')
def watch_video(filename):
    # ভিডিও প্লেয়ার পেজ
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Secure Player</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ background: #000; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: sans-serif; }}
            video {{ max-width: 100%; max-height: 80vh; border: 1px solid #333; }}
            .btn {{ margin-top: 20px; padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <video controls autoplay>
            <source src="/file/{filename}" type="video/mp4">
        </video>
        <a href="/file/{filename}" class="btn" download>📥 Download Now</a>
    </body>
    </html>
    """
    return render_template_string(html)

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- সেলফ পিং (বট যাতে না ঘুমায়) ---
def keep_alive():
    while True:
        time.sleep(600) # ১০ মিনিট পর পর
        try:
            if 'RENDER_EXTERNAL_URL' in os.environ:
                requests.get(os.environ['RENDER_EXTERNAL_URL'])
                print("✅ Pinged successfully to keep awake!")
        except: pass

# --- অটো ক্লিনআপ ---
def cleanup_files():
    while True:
        try:
            now = time.time()
            if not os.path.exists('downloads'): os.makedirs('downloads')
            for f in os.listdir('downloads'):
                fpath = os.path.join('downloads', f)
                # ২০ মিনিট পর ফাইল ডিলিট
                if os.stat(fpath).st_mtime < now - 1200:
                    os.remove(fpath)
        except: pass
        time.sleep(60)

# --- ডাটাবেস ---
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

init_db()

# --- হ্যান্ডলার ---
@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "👋 **হ্যালো!**\nলিংক দিন, আমি ভিডিও প্লেয়ার তৈরি করে দেব।\n(Render Friendly Mode)")

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    uid = m.from_user.id
    text = m.text
    
    if any(x in text.lower() for x in ['http', 'www', '.com']):
        # ১. লিংকটি মেমোরিতে সেভ করছি (বাটনে দিলে এরর হয়)
        user_current_url[uid] = text.strip()
        
        markup = types.InlineKeyboardMarkup()
        # বাটনে কোনো লিংক নেই, শুধু কমান্ড আছে
        markup.add(types.InlineKeyboardButton("▶️ Watch / Download", callback_data="process_video"))
        
        bot.reply_to(m, "🔗 **লিংক পেয়েছি!**\nভিডিও তৈরি করতে নিচের বাটনে চাপ দিন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.from_user.id
    if call.data == "process_video":
        url = user_current_url.get(uid)
        if not url:
            bot.answer_callback_query(call.id, "⚠️ লিংক মেয়াদোত্তীর্ণ, আবার দিন।")
            return
        
        bot.delete_message(uid, call.message.message_id)
        # আলাদা থ্রেডে পাঠানো
        threading.Thread(target=download_process, args=(uid, url)).start()

def download_process(uid, url):
    msg = bot.send_message(uid, "🔄 **প্রসেসিং...** (অপেক্ষা করুন)")
    
    # ২. র‍্যাম বাঁচানোর কনফিগারেশন (Low Quality for Server Safety)
    opts = {
        'outtmpl': f'downloads/{uid}_%(title)s.%(ext)s', 
        'quiet': True,
        'noplaylist': True,
        # রেজুলেশন ৪৮০পি এর মধ্যে রাখা যাতে সার্ভার ক্র্যাশ না করে
        'format': 'best[height<=480]/best', 
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
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

        watch_link = f"{BASE_URL}/watch/{file_name}"
        
        final_msg = (
            f"✅ **রেডি!**\n\n"
            f"🎬 `{title}`\n"
            f"👉 [এখানে ক্লিক করে দেখুন]({watch_link})\n\n"
            f"⚠️ লিংকটি ২০ মিনিট পর নষ্ট হয়ে যাবে।"
        )
        bot.edit_message_text(final_msg, uid, msg.message_id, parse_mode="Markdown")

    except Exception as e:
        print(f"Error: {e}")
        bot.edit_message_text("❌ ভিডিওটি প্রসেস করা যায়নি। (Server Overload or Invalid Link)", uid, msg.message_id)

if __name__ == "__main__":
    # থ্রেড চালু করা
    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=cleanup_files, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    print("🚀 Bot Started...")
    
    # ৩. পোলিং লুপ (যাতে নেট এররে বন্ধ না হয়)
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"Polling Error: {e}")
            time.sleep(5)
