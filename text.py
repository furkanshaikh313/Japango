from flask import Flask, request, jsonify, render_template, session
import google.generativeai as genai
import asyncio
import edge_tts
import os
import librosa
import numpy as np
from scipy.spatial.distance import cdist
import tempfile
import re
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a real secret key

# Configure Google Gemini API key
GEMINI_API_KEY = "YOUR_API_KEY_HERE"  # Replace with your actual API key
genai.configure(api_key=GEMINI_API_KEY)

# Text-to-Speech configuration
VOICES = ['ja-JP-NanamiNeural']  # Japanese voice for TTS
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'static', 'audio')

# Make zip function available to templates
app.jinja_env.globals.update(zip=zip)

def sanitize_filename(filename):
    sanitized = re.sub(r'[^\w\s-]', '', filename)
    sanitized = sanitized.replace(' ', '_')
    return sanitized[:50]

def keep_japanese(text_array):
    japanese_pattern = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]+')
    def filter_japanese(text):
        return ''.join(japanese_pattern.findall(text))
    return [filter_japanese(text) for text in text_array]

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
        raise ValueError("Sample rates of the audio files do not match.")

    mfcc1 = librosa.feature.mfcc(y=audio1, sr=sr1, n_mfcc=13)
    mfcc2 = librosa.feature.mfcc(y=audio2, sr=sr2, n_mfcc=13)

    similarity = np.mean(cdist(mfcc1.T, mfcc2.T, metric='cosine'))
    return 1 - similarity

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    difficulty = request.form['difficulty']
    words = generate_words(difficulty)
    
    japanese_only = keep_japanese(words)
    audio_files = []
    for word in words:
        sanitized_word = sanitize_filename(word)
        output_file = os.path.join(OUTPUT_DIR, f"{sanitized_word}.mp3")
        try:
            asyncio.run(text_to_speech(word, VOICES[0], output_file))
            audio_files.append(f"{sanitized_word}.mp3")
        except Exception as e:
            print(f"Error generating audio for word '{word}': {str(e)}")
            continue
    
    session['words'] = words
    session['audio_files'] = audio_files
    return render_template('results.html', words=words, audio_files=audio_files)

@app.route('/compare_audio', methods=['POST'])
def compare_audio():
    word = request.form['word']
    audio_data = request.form['audio_data']
    
    # Decode the base64 audio data
    audio_bytes = base64.b64decode(audio_data.split(',')[1])
    
    # Save the user's recorded audio temporarily
    user_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    user_audio_file.write(audio_bytes)
    user_audio_file.close()

    sanitized_word = sanitize_filename(word)
    generated_audio = os.path.join(OUTPUT_DIR, f"{sanitized_word}.mp3")
    
    try:
        similarity = compare_audio_files(generated_audio, user_audio_file.name)
    except Exception as e:
        print(f"Error comparing audio files: {str(e)}")
        similarity = 0

    os.unlink(user_audio_file.name)

    # Store the similarity score in the session
    if 'similarities' not in session:
        session['similarities'] = {}
    session['similarities'][word] = similarity
    session.modified = True

    return jsonify({"similarity": similarity})

@app.route('/results')
def results():
    words = session.get('words', [])
    audio_files = session.get('audio_files', [])
    similarities = session.get('similarities', {})
    return render_template('final_results.html', words=words, audio_files=audio_files, similarities=similarities)

if __name__ == '__main__':
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    app.run(debug=True)