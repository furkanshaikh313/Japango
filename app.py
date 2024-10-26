from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
import asyncio
import edge_tts
import librosa
import numpy as np
from scipy.spatial.distance import cdist
import tempfile
import re
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import jwt
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from functools import wraps
import os

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

# Database connection
DATABASE_URL = "postgresql://project_owner:T1GqOno0PZgr@ep-crimson-haze-a5axs926.us-east-2.aws.neon.tech/project?sslmode=require"
pool = SimpleConnectionPool(1, 20, DATABASE_URL)

SECRET_KEY = 'your_secret_key'

# Configure Google Gemini API key
GEMINI_API_KEY = "AIzaSyC1ONZtLOgvCqPHJYjPfkyKzyqsQWTgDlo"  # Replace with your actual API key
genai.configure(api_key=GEMINI_API_KEY)

# Text-to-Speech configuration
VOICES = ['ja-JP-NanamiNeural']  # Japanese voice for TTS
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'static', 'audio')

# Make zip function available to templates
app.jinja_env.globals.update(zip=zip)

def get_db_connection():
    return pool.getconn()

def release_db_connection(conn):
    pool.putconn(conn)

def authenticate_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:
            token = token.split()[1]  # Remove 'Bearer ' prefix
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = data['userId']
        except:
            return jsonify({'error': 'Token is invalid'}), 403
        return f(current_user, *args, **kwargs)
    return decorated

def sanitize_filename(filename):
    sanitized = re.sub(r'[^\w\s-]', '', filename)
    sanitized = sanitized.replace(' ', '_')
    return sanitized[:50]

def keep_japanese(text_array):
    japanese_pattern = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]+')
    return [''.join(japanese_pattern.findall(text)) for text in text_array]

def generate_words(difficulty: str):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"give me 10 words in japanese for a {difficulty} learner"
    response = model.generate_content(prompt)
    print(response)
    return response.text.strip().split('\n')

async def text_to_speech(text, voice, output_file):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def compare_audio_files(file1, file2):
    audio1, sr1 = librosa.load(file1, sr=None)
    audio2, sr2 = librosa.load(file2, sr=None)

    if sr1 != sr2:
        if sr1 > sr2:
            audio1 = librosa.resample(audio1, orig_sr=sr1, target_sr=sr2)
            sr1 = sr2
        else:
            audio2 = librosa.resample(audio2, orig_sr=sr2, target_sr=sr1)
            sr2 = sr1

    audio1, _ = librosa.effects.trim(audio1)
    audio2, _ = librosa.effects.trim(audio2)

    max_length = max(len(audio1), len(audio2))
    audio1 = librosa.util.fix_length(audio1, size=max_length)
    audio2 = librosa.util.fix_length(audio2, size=max_length)

    mfcc1 = librosa.feature.mfcc(y=audio1, sr=sr1, n_mfcc=13)
    mfcc2 = librosa.feature.mfcc(y=audio2, sr=sr2, n_mfcc=13)

    similarity = np.mean(cdist(mfcc1.T, mfcc2.T, metric='cosine'))
    return 1 - similarity

@app.route('/')
def index():
    return render_template('auth.html')

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    try:
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s) RETURNING id",
                    (username, email, hashed_password))
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        release_db_connection(conn)
        
        token = jwt.encode({'userId': user_id}, SECRET_KEY, algorithm="HS256")
        return jsonify({'token': token})
    except Exception as e:
        print(e)
        return jsonify({'error': 'Error signing up'}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        release_db_connection(conn)
        
        if user:
            if bcrypt.check_password_hash(user[3], password):  # Assuming password is the 4th column
                token = jwt.encode({'userId': user[0]}, SECRET_KEY, algorithm="HS256")
                return jsonify({'token': token})
            else:
                return jsonify({'error': 'Invalid credentials'}), 400
        else:
            return jsonify({'error': 'User not found'}), 400
    except Exception as e:
        print(e)
        return jsonify({'error': 'Error logging in'}), 500

@app.route('/home')
def home():
    sentence = "The quick brown fox jumps over the lazy dog"
    word = sentence.split()
    return render_template('index.html', word=word)

@app.route('/generate', methods=['POST'])
def generate():
    difficulty = request.form['difficulty']
    words = generate_words(difficulty)
    
    japanese_only = keep_japanese(words)
    audio_files = []
    for word in japanese_only:
        sanitized_word = sanitize_filename(word)
        output_file = os.path.join(OUTPUT_DIR, f"{sanitized_word}.mp3")
        try:
            asyncio.run(text_to_speech(word, VOICES[0], output_file))
            audio_files.append(f"{sanitized_word}.mp3")
        except Exception as e:
            print(f"Error generating audio for word '{word}': {str(e)}")
            continue
    
    return render_template('results.html', words=japanese_only, audio_files=audio_files)

@app.route('/upload', methods=['POST'])
def upload_audio():
    word = request.form['word']
    user_audio = request.files['user_audio']
    
    user_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    user_audio_path = user_audio_file.name
    user_audio_file.close()
    
    user_audio.save(user_audio_path)

    sanitized_word = sanitize_filename(word)
    generated_audio = os.path.join(OUTPUT_DIR, f"{sanitized_word}.mp3")
    
    try:
        similarity = compare_audio_files(generated_audio, user_audio_path)
        similarity_percentage = similarity * 100
        message = f"Your pronunciation is {similarity_percentage:.2f}% similar to the original."
    except Exception as e:
        print(f"Error comparing audio files: {str(e)}")
        similarity_percentage = 0
        message = "An error occurred while comparing the audio files."
    
    try:
        os.unlink(user_audio_path)
    except PermissionError:
        try:
            os.rename(user_audio_path, user_audio_path + '.delete_me')
        except Exception as e:
            print(f"Failed to rename temporary file: {str(e)}")

    return jsonify({
        "similarity": similarity_percentage,
        "message": message
    })

if __name__ == '__main__':
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    app.run(debug=True)