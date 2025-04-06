document.addEventListener('DOMContentLoaded', () => {
    console.log("[DEBUG 1] DOM loaded");
    const voiceBtn = document.getElementById('voiceCommandBtn');
    const voiceResult = document.getElementById('voiceResult');

    // 1. Browser Support Check
    if (!('webkitSpeechRecognition' in window)) {
        console.error("[ERROR] Web Speech API missing");
        voiceBtn.textContent = "❌ Voice not supported";
        return;
    }
    console.log("[DEBUG 2] Browser supports speech");

    // 2. Initialize Recognizer
    const recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    // 3. Click Handler
    voiceBtn.addEventListener('click', () => {
        console.log("[DEBUG 3] Mic button clicked");
        voiceResult.innerHTML = "<div class='status'>Starting microphone...</div>";
        
        try {
            recognition.start();
            console.log("[DEBUG 4] Recognition started");
        } catch (err) {
            console.error("[ERROR] Recognition start failed:", err);
            voiceResult.innerHTML = `<div class='error'>Microphone error: ${err}</div>`;
        }
    });

    // 4. Speech Result
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        console.log("[DEBUG 5] Received speech:", transcript);
        voiceResult.innerHTML = `<div class='query'>You asked: <strong>"${transcript}"</strong></div>`;
        
        processCommand(transcript).then(response => {
            console.log("[DEBUG 6] API response:", response);
            voiceResult.innerHTML += formatResponse(response);
            speak(response);
        }).catch(err => {
            console.error("[ERROR] Processing failed:", err);
            voiceResult.innerHTML += `<div class='error'>${err.message}</div>`;
        });
    };

    // 5. Error Handling
    recognition.onerror = (event) => {
        console.error("[ERROR] Recognition error:", event.error);
        voiceResult.innerHTML += `<div class='error'>Error: ${event.error}</div>`;
    };

    // Helper Functions
    async function processCommand(query) {
    const product = extractProduct(query);
    console.log("Extracted product:", product);  // Debug
    
    try {
        const response = await fetch('/analyze-voice', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'  // Explicitly ask for JSON
            },
            body: JSON.stringify({
                product: product
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error("API Error:", errorText);
            throw new Error("Analysis failed");
        }

        return await response.json();
        
    } catch (err) {
        console.error("Fetch Error:", err);
        throw err;
    }
}
    
    function extractProduct(query) {
        // Improved regex for questions like:
        // "Is ___ safe?" / "Can I eat ___?" / "What about ___?"
        const match = query.match(/(is|can i|what about)\s(.+?)(\?|safe|okay)/i);
        return match ? match[2].trim() : null;
    }
    
    function formatResponse(data) {
        return `
            <div class="response">
                <p><strong>${data.product}</strong> is <span class="${data.verdict.toLowerCase()}">${data.verdict}</span></p>
                <p>${data.details || ''}</p>
                ${data.alternatives ? `<p>Alternatives: ${data.alternatives}</p>` : ''}
            </div>
        `;
    }
    
    function speak(data) {
        const utterance = new SpeechSynthesisUtterance();
        utterance.text = `For ${data.product}, our analysis shows: ${data.verdict}.`;
        window.speechSynthesis.speak(utterance);
    }
});