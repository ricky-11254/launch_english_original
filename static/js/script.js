document.addEventListener('DOMContentLoaded', (event) => {

  const serverUrl = "{{ server_url }}";
  const mic = document.getElementById('mic');
  const recordBtn = document.getElementById('record-btn');

  let isRecording = false;
  recordBtn.addEventListener('click', () => {
    isRecording = !isRecording;

    if (isRecording) {
      // Start recording, add animation
      mic.classList.add('recording');
      recordBtn.textContent = 'Stop Recording'; 
    } else {
      // Stop recording, remove animation
      mic.classList.remove('recording');
      recordBtn.textContent = 'Start Recording';
    }
  });

  const recordingElements = [
    { start: 'startRecording1', stop: 'stopRecording1', output: 'output1' },
    { start: 'startRecording2', stop: 'stopRecording2', output: 'output2' },
    { start: 'startRecording3', stop: 'stopRecording3', output: 'output3' }
  ];

  let mediaRecorder;
  let audioChunks = [];

  recordingElements.forEach(({ start, stop, output }) => {
    const startButton = document.getElementById(start);
    const stopButton = document.getElementById(stop);
    const outputDiv = document.getElementById(output);

    startButton.addEventListener('click', async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: 'audio/wav' });
        sendAudioToServer(blob, outputDiv);
        audioChunks = [];
      };

      mediaRecorder.start();
      startButton.disabled = true;
      stopButton.disabled = false;
    });

    stopButton.addEventListener('click', () => {
      mediaRecorder.stop();
      startButton.disabled = false;
      stopButton.disabled = true;
    });
  });

  function sendAudioToServer(audioBlob, outputDiv) {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.wav');

    fetch(`${serverUrl}/upload`, {
      method: 'POST',
      body: formData
    })
    .then((response) => response.json())
    .then((data) => {
      outputDiv.innerHTML = `
        <h2>Results:</h2>
        <p><strong>Transcription:</strong> ${data.transcription}</p>
        <p><strong>Correction:</strong> ${data.correction}</p>
      `;
    })
    .catch((error) => {
      console.error('Error:', error);
      alert('Error uploading audio');
    });
  }
  });

