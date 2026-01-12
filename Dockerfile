FROM python:3.9-slim

# FFmpeg ইনস্টল করা (এটি ছাড়া হাই কোয়ালিটি মার্জ হবে না)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ফাইল কপি করা
COPY . /app

# পাইথন প্যাকেজ ইনস্টল
RUN pip install --no-cache-dir -r requirements.txt

# অ্যাপ রান করা
CMD ["python", "main.py"]
