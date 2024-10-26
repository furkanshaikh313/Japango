Japango
Japango is a Japanese language learning website built in Python, emphasizing learning through spoken language. With the integration of Google Gemini API, users can practice and improve their Japanese by engaging in interactive speaking exercises.

Features
Speaking-Based Learning: Emphasizes speaking to aid in language retention.
Google Gemini API: Used for advanced language processing capabilities.
Text-to-Speech Integration: Uses edge-tts for text-to-speech functionality.
Prerequisites
Google Gemini API Key

Get your API key from Google Gemini.
Add the key to the .env file in the project root.
Edge TTS and FFMPEG

Install edge-tts by following instructions on its GitHub repository.
Ensure FFMPEG is installed as it’s required for text-to-speech.
Installation
Clone this repository:

bash
Copy code
git clone https://github.com/yourusername/japango.git
Install dependencies:

bash
Copy code
pip install -r requirements.txt
Set up .env file:

Add your Google Gemini API key in the .env file as follows:
plaintext
Copy code
GEMINI_API_KEY=your_api_key_here
Usage
To start the application, run the following command:

bash
Copy code
python3 app.py
Contributing
Contributions are welcome! If you’d like to improve the project, please fork the repository and create a pull request.

License
This project is licensed under the MIT License.

