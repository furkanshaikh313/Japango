from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
import asyncio
import edge_tts
import os
import librosa
import numpy as np
from scipy.spatial.distance import cdist
import tempfile
import traceback
import logging
import re

app = Flask(__name__)

# Configure Google Gemini API key
GEMINI_API_KEY = "your gemini api key"  # Replace with your actual API key
genai.configure(api_key=GEMINI_API_KEY)

# Text-to-Speech configuration
VOICES = ['ja-JP-NanamiNeural']  # Japanese voice for TTS
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'static', 'audio')

# Make zip function available to templates
app.jinja_env.globals.update(zip=zip)

def sanitize_filename(filename):
    # Remove any characters that are not alphanumeric, space, or underscore
    sanitized = re.sub(r'[^\w\s-]', '', filename)
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    # Limit filename length
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



# ... (previous imports remain the same)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def compare_audio_files(file1, file2):
    try:
        logger.info(f"Comparing files: {file1} and {file2}")
        
        if not os.path.exists(file1):
            raise FileNotFoundError(f"File not found: {file1}")
        if not os.path.exists(file2):
            raise FileNotFoundError(f"File not found: {file2}")
        
        audio1, sr1 = librosa.load(file1, sr=None)
        audio2, sr2 = librosa.load(file2, sr=None)

        logger.debug(f"Audio1 shape: {audio1.shape}, sr1: {sr1}")
        logger.debug(f"Audio2 shape: {audio2.shape}, sr2: {sr2}")

        if sr1 != sr2:
            logger.info(f"Resampling audio. sr1: {sr1}, sr2: {sr2}")
            if sr1 > sr2:
                audio1 = librosa.resample(audio1, orig_sr=sr1, target_sr=sr2)
                sr1 = sr2
            else:
                audio2 = librosa.resample(audio2, orig_sr=sr2, target_sr=sr1)
                sr2 = sr1

        # Trim silence from both audio files
        audio1, _ = librosa.effects.trim(audio1)
        audio2, _ = librosa.effects.trim(audio2)

        logger.debug(f"After trimming - Audio1 shape: {audio1.shape}, Audio2 shape: {audio2.shape}")

        # Pad the shorter audio to match the length of the longer one
        max_length = max(len(audio1), len(audio2))
        audio1 = librosa.util.fix_length(audio1, size=max_length)
        audio2 = librosa.util.fix_length(audio2, size=max_length)

        logger.debug(f"After padding - Audio1 shape: {audio1.shape}, Audio2 shape: {audio2.shape}")

        mfcc1 = librosa.feature.mfcc(y=audio1, sr=sr1, n_mfcc=13)
        mfcc2 = librosa.feature.mfcc(y=audio2, sr=sr2, n_mfcc=13)

        logger.debug(f"MFCC1 shape: {mfcc1.shape}, MFCC2 shape: {mfcc2.shape}")

        similarity = np.mean(cdist(mfcc1.T, mfcc2.T, metric='cosine'))
        return 1 - similarity
    except Exception as e:
        logger.error(f"Error in compare_audio_files: {str(e)}")
        logger.error(traceback.format_exc())
        raise


@app.route('/')
def index():
    sentence = "The quick brown fox jumps over the lazy dog"
    word = sentence.split()
    return render_template('index.html', word=word)

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
    
    return render_template('results.html', words=words, audio_files=audio_files)

@app.route('/upload', methods=['POST'])
def upload_audio():
    try:
        word = request.form['word']
        user_audio = request.files['user_audio']
        
        logger.info(f"Processing upload for word: {word}")
        
        # Create a temporary file with a unique name
        user_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        user_audio_path = user_audio_file.name
        user_audio_file.close()  # Close the file immediately
        
        # Save the uploaded audio to the temporary file
        user_audio.save(user_audio_path)
        logger.info(f"Saved user audio to: {user_audio_path}")

        sanitized_word = sanitize_filename(word)
        generated_audio = os.path.join(OUTPUT_DIR, f"{sanitized_word}.mp3")
        
        if not os.path.exists(generated_audio):
            raise FileNotFoundError(f"Generated audio file not found: {generated_audio}")
        
        similarity = compare_audio_files(generated_audio, user_audio_path)
        similarity_percentage = similarity * 100
        message = f"Your pronunciation is {similarity_percentage:.2f}% similar to the original."
        logger.info(message)
    except FileNotFoundError as e:
        logger.error(f"File not found: {str(e)}")
        similarity_percentage = 0
        message = f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        logger.error(traceback.format_exc())
        similarity_percentage = 0
        message = "An unexpected error occurred while processing the audio."
    finally:
        # Attempt to delete the temporary file
        try:
            if 'user_audio_path' in locals():
                os.unlink(user_audio_path)
                logger.info(f"Deleted temporary file: {user_audio_path}")
        except Exception as e:
            logger.error(f"Failed to delete temporary file: {str(e)}")

    return jsonify({
        "similarity": similarity_percentage,
        "message": message
    })
if __name__ == '__main__':
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    app.run(debug=False)
