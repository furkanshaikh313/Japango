const video = document.getElementById('webcam');
const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const startRecognitionButton = document.getElementById('startRecognitionButton');
const accuracyScore = document.getElementById('accuracyScore');
const sentence = "The quick brown fox jumps over the lazy dog.";

let mediaStream = null;
let recognition;

// Start the webcam
startButton.addEventListener('click', async () => {
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
        video.srcObject = mediaStream;
    } catch (error) {
        console.error("Error accessing the webcam: ", error);
    }
});

// Stop the webcam
stopButton.addEventListener('click', () => {
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        video.srcObject = null;
    }
});

// Initialize Speech Recognition
if ('webkitSpeechRecognition' in window) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        checkAccuracy(transcript);
    };

    recognition.onerror = (event) => {
        console.error("Error occurred in recognition: ", event.error);
    };
} else {
    alert("Speech recognition not supported in this browser.");
}

// Start Speech Recognition
startRecognitionButton.addEventListener('click', () => {
    accuracyScore.textContent = ""; // Clear previous score
    recognition.start();
});

// Check accuracy of user's spoken input
function checkAccuracy(userText) {
    const normalizedUserText = userText.toLowerCase().replace(/[^\w\s]/gi, '');
    const normalizedSentence = sentence.toLowerCase().replace(/[^\w\s]/gi, '');

    const accuracy = (normalizedUserText === normalizedSentence) ? "100% Accuracy" : "Try Again!";
    accuracyScore.textContent = accuracy;
}
