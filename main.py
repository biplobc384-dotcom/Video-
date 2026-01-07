import telebot
from telebot import types
import sqlite3
import yt_dlp
import os
import threading
import time
import random
from flask import Flask
from datetime import datetime, timedelta

# --- কনফিগারেশন ---
API_TOKEN = '8302172779:AAH6OuORRGFkRXTp9DC3--U1JbjoSxU-H8w'   # আপনার বটের টোকেন
ADMIN_ID = 6740599881               # আপনার অ্যাডমিন আইডি
ADMIN_USERNAME = 'Arifur905'
REQUIRED_CHANNEL = '@ArifurHackworld' # আপনার চ্যানেল
DOWNLOAD_COST = 5                   # ভিডিও ডাউনলোডের খরচ
REFERRAL_BONUS = 50                 # রেফার বোনাস

bot = telebot.TeleBot(API_TOKEN)
user_state = {} 

# --- Render Web Server (Keep Alive) ---
app = Flask(__name__)

@app.route('/')
def home():
    return f"⚡ Fast Bot is Running! {datetime.now()}"

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- ডাটাবেস সেটআপ ---
def init_db():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, balance INTEGER, name TEXT, 
                  join_date TEXT, last_bonus TEXT, referrals INTEGER, is_banned INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes
                 (code TEXT PRIMARY KEY, amount INTEGER, uses_left INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS used_promos
                 (user_id INTEGER, code TEXT, PRIMARY KEY (user_id, code))''')
    conn.commit()
    conn.close()

def get_user_data(user_id, name="Unknown"):
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

def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💾 ব্যাকআপ", "📂 রিস্টোর")
    markup.add("➕ কুপন তৈরি", "📢 ব্রডকাস্ট")
    markup.add("🔙 ব্যাক")
    return markup

# --- প্রগ্রেস বার (মডার্ন ডিজাইন) ---
def progress_bar(percent):
    filled = int(12 * percent // 100)
    bar = '▰' * filled + '▱' * (12 - filled)
    return bar

# --- হ্যান্ডলার ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    # Force Join
    if not check_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        clean = REQUIRED_CHANNEL.replace('@', '')
        markup.add(types.InlineKeyboardButton("📢 জয়েন চ্যানেল", url=f"https://t.me/{clean}"))
        markup.add(types.InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_join"))
        bot.send_message(user_id, f"⚠️ বট ব্যবহার করতে হলে আমাদের চ্যানেলে জয়েন করুন।\n\nচ্যানেল: {REQUIRED_CHANNEL}", reply_markup=markup)
        return

    get_user_data(user_id, message.from_user.first_name)
    # রেফারাল চেক
    args = message.text.split()
    if len(args) > 1:
        try:
            ref_id = int(args[1])
            if ref_id != user_id:
                conn = sqlite3.connect('users.db')
                exists = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
                if not exists: 
                     now = datetime.now().strftime("%Y-%m-%d")
                     conn.execute("INSERT INTO users (user_id, balance, name, join_date, last_bonus, referrals, is_banned) VALUES (?, ?, ?, ?, ?, ?, 0)", 
                      (user_id, 10, message.from_user.first_name, now, None, 0))
                     conn.commit()
                     update_balance(ref_id, REFERRAL_BONUS)
                     conn.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id=?", (ref_id,))
                     conn.commit()
                     bot.send_message(ref_id, f"🎉 নতুন রেফারাল! +{REFERRAL_BONUS} টোকেন।")
                conn.close()
        except: pass

    bot.reply_to(message, f"স্বাগতম {message.from_user.first_name}! 👋\nলিংক দিন, সুপার ফাস্ট ডাউনলোড করুন! 🚀", reply_markup=main_menu(user_id))

# --- টেক্সট হ্যান্ডলার ---
@bot.message_handler(func=lambda m: True)
def handle_text(m):
    user_id = m.from_user.id
    text = m.text

    if not check_subscription(user_id):
        bot.reply_to(m, f"⚠️ চ্যানেলে জয়েন করুন: {REQUIRED_CHANNEL}")
        return

    bal, _, refs, banned, join_date = get_user_data(user_id, m.from_user.first_name)
    if banned: return

    # --- মেনু ফিচার ---
    if text == "👤 প্রোফাইল":
        msg = f"""
╭━━━ ⚡ **FAST PROFILE** ━━━╮
┃ 📛 নাম: {m.from_user.first_name}
┃ 🆔 আইডি: `{user_id}`
┃ 💰 ওয়ালেট: **{bal}** টোকেন
┃ 👥 রেফার: {refs} জন
┃ 📅 জয়েনিং: {join_date}
╰━━━━━━━━━━━━━━━━━━━━━━╯
"""
        bot.reply_to(m, msg, parse_mode="Markdown")

    elif text == "⚡ ফাস্ট ডাউনলোড":
        bot.reply_to(m, "🚀 **ফাস্ট মোড:** যেকোনো ভিডিওর লিংক দিন, আমি অটোমেটিক সেরা কোয়ালিটি ডাউনলোড করে দেব। কোনো বাটন চাপতে হবে না!")

    elif text == "🎰 লাকি স্পিন":
        if bal < 10:
            bot.reply_to(m, "❌ স্পিন করতে ১০ টোকেন লাগে।")
            return
        update_balance(user_id, -10)
        msg = bot.reply_to(m, "🎲 ঘুরছে...")
        time.sleep(2)
        win = random.choice([0, 20, 0, 50, 0])
        if win > 0:
            update_balance(user_id, win)
            bot.edit_message_text(f"🎉 জ জিতেছেন: {win} টোকেন!", user_id, msg.message_id)
        else:
            bot.edit_message_text("😢 হেরে গেছেন।", user_id, msg.message_id)

    elif text == "💸 ট্রান্সফার":
        bot.reply_to(m, "লিখুন: `ID Amount`\nযেমন: `12345 50`")
        user_state[user_id] = {'type': 'transfer'}

    # ফিক্স: NoneType এরর সমাধান করা হয়েছে
    elif user_state.get(user_id) and user_state[user_id].get('type') == 'transfer':
        try:
            tid, amt = map(int, text.split())
            if bal >= amt and amt >= 10:
                conn = sqlite3.connect('users.db')
                if conn.execute("SELECT user_id FROM users WHERE user_id=?", (tid,)).fetchone():
                    update_balance(user_id, -amt)
                    update_balance(tid, amt)
                    bot.reply_to(m, "✅ ট্রান্সফার সফল!")
                    try: bot.send_message(tid, f"🎁 {amt} টোকেন পেয়েছেন!") 
                    except: pass
                else: bot.reply_to(m, "❌ ইউজার পাওয়া যায়নি।")
                conn.close()
            else: bot.reply_to(m, "❌ ব্যালেন্স নেই বা পরিমাণ কম।")
        except: bot.reply_to(m, "❌ ভুল ফরম্যাট।")
        user_state.pop(user_id, None) # স্টেট ক্লিয়ার করা হচ্ছে

    elif text == "👥 রেফার":
        link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        bot.reply_to(m, f"🔗 **ইনভাইট লিংক:**\n`{link}`\n\nবোনাস: {REFERRAL_BONUS} টোকেন!", parse_mode="Markdown")

    elif text == "💎 টোকেন কিনুন":
        bot.reply_to(m, f"👨‍💻 টোকেন কিনতে অ্যাডমিনকে নক দিন: t.me/{ADMIN_ID}")

    # --- অ্যাডমিন ---
    elif text == "👑 অ্যাডমিন প্যানেল" and user_id == ADMIN_ID:
        bot.reply_to(m, "স্বাগতম বস!", reply_markup=admin_menu())
    
    elif text == "💾 ব্যাকআপ" and user_id == ADMIN_ID:
        if os.path.exists("users.db"):
            with open("users.db", "rb") as f: bot.send_document(user_id, f)
    
    elif text == "📂 রিস্টোর" and user_id == ADMIN_ID:
        msg = bot.reply_to(m, "`users.db` ফাইলটি দিন:")
        bot.register_next_step_handler(msg, restore_db)
    
    elif text == "📢 ব্রডকাস্ট" and user_id == ADMIN_ID:
        msg = bot.reply_to(m, "মেসেজটি লিখুন:")
        user_state[user_id] = {'type': 'broadcast'}

    elif user_state.get(user_id) and user_state[user_id].get('type') == 'broadcast':
        conn = sqlite3.connect('users.db')
        users = conn.execute("SELECT user_id FROM users").fetchall()
        conn.close()
        count = 0
        for u in users:
            try:
                bot.send_message(u[0], f"📢 <b>নোটিশ:</b>\n{text}", parse_mode="HTML")
                count += 1
            except: pass
        bot.reply_to(m, f"✅ পাঠানো হয়েছে: {count} জন")
        user_state.pop(user_id, None)

    elif text == "🔙 ব্যাক":
        bot.reply_to(m, "মেনু:", reply_markup=main_menu(user_id))

    # --- ভিডিও লিংক (Modern UI) ---
    elif any(x in text.lower() for x in ['facebook', 'fb.watch', 'tiktok', 'youtube', 'youtu.be', 'instagram']):
        bal, _, _, _, _ = get_user_data(user_id)
        if bal < DOWNLOAD_COST:
            bot.reply_to(m, "❌ টোকেন শেষ! রিচার্জ করুন।")
            return
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Fast Download (Auto) ⚡", callback_data=f"dl|fast|{text}"))
        markup.add(types.InlineKeyboardButton("🎬 Video (Select)", callback_data=f"dl|best|{text}"),
                   types.InlineKeyboardButton("🎵 Audio", callback_data=f"dl|audio|{text}"))
        
        bot.reply_to(m, f"📹 **ভিডিও পাওয়া গেছে!**\nলিংক: {text[:30]}...\n\nকিভাবে নামাতে চান?", reply_markup=markup)
    else:
        bot.reply_to(m, "সঠিক লিংক দিন।")

# --- সহায়ক ফাংশন ---
def restore_db(m):
    if m.document and m.document.file_name == "users.db":
        file_info = bot.get_file(m.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        with open("users.db", "wb") as f: f.write(downloaded)
        bot.reply_to(m, "✅ রিস্টোর সম্পন্ন!")

# --- ডাউনলোড ও কলব্যাক ---
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.from_user.id
    if call.data == "check_join":
        if check_subscription(uid):
            bot.delete_message(uid, call.message.message_id)
            bot.send_message(uid, "✅ ধন্যবাদ!", reply_markup=main_menu(uid))
        else: bot.answer_callback_query(call.id, "❌ জয়েন করেননি!", show_alert=True)
        return

    if call.data.startswith("dl|"):
        data = call.data.split('|')
        action = data[1]
        url = data[2]
        
        # ব্যালেন্স চেক
        bal, _, _, _, _ = get_user_data(uid)
        if bal < DOWNLOAD_COST:
             bot.answer_callback_query(call.id, "টোকেন নেই!", show_alert=True)
             return

        bot.delete_message(uid, call.message.message_id) # আগের বাটন মুছে ফেলবে
        threading.Thread(target=download_task, args=(uid, url, action)).start()

def download_task(uid, url, action):
    msg = bot.send_message(uid, "🚀 **কানেক্টিং সার্ভার...**", parse_mode="Markdown")
    last_update = [0]
    
    def hook(d):
        if d['status'] == 'downloading' and time.time() - last_update[0] > 2:
            try:
                p = d.get('_percent_str', '0%').replace('%','')
                speed = d.get('_speed_str', 'N/A')
                bar = progress_bar(float(p))
                bot.edit_message_text(f"⚡ **ডাউনলোড হচ্ছে...**\n{bar} {d['_percent_str']}\n🚀 স্পিড: {speed}", uid, msg.message_id, parse_mode="Markdown")
                last_update[0] = time.time()
            except: pass

    # Fast Download Settings
    opts = {
        'outtmpl': f'downloads/{uid}_%(id)s.%(ext)s', 
        'quiet': True, 
        'progress_hooks': [hook],
        'writethumbnail': True,
        'concurrent_fragment_downloads': 5, # স্পিড বাড়াবে (Multi-thread)
        'buffersize': 1024,
    }
    
    if action == 'fast': opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' # সেরা mp4
    elif action == 'best': opts['format'] = 'bestvideo+bestaudio/best'
    else: 
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]

    try:
        if not os.path.exists('downloads'): os.makedirs('downloads')
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fpath = ydl.prepare_filename(info)
            if action == 'audio': fpath = os.path.splitext(fpath)[0] + ".mp3"
            title = info.get('title', 'Video')

        if os.path.exists(fpath):
            thumb = fpath.rsplit('.', 1)[0] + ".jpg"
            if not os.path.exists(thumb): thumb = fpath.rsplit('.', 1)[0] + ".webp"
            
            update_balance(uid, -DOWNLOAD_COST)
            caption = f"✅ **COMPLETED**\n🎬 {title}\n⚡ স্পিড: Super Fast\n🤖 @{bot.get_me().username}"
            
            with open(fpath, 'rb') as f:
                t = open(thumb, 'rb') if os.path.exists(thumb) else None
                if action == 'audio': bot.send_audio(uid, f, caption=caption, thumbnail=t, parse_mode='Markdown')
                else: bot.send_video(uid, f, caption=caption, thumbnail=t, parse_mode='Markdown')
            
            os.remove(fpath)
            if os.path.exists(thumb): os.remove(thumb)
            bot.delete_message(uid, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ এরর: ভিডিওটি প্রাইভেট বা ডাউনলোড করা যাচ্ছে না।", uid, msg.message_id)

if __name__ == "__main__":
    t = threading.Thread(target=run_web_server)
    t.start()
    print("🚀 Super Fast Bot Started...")
    bot.infinity_polling()
    
