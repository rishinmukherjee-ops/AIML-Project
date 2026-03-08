(() => {
    const messagesEl = document.getElementById('messages');
    const chatContainer = document.getElementById('chat-container');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const clearBtn = document.getElementById('clear-btn');
    const locationBadge = document.getElementById('location-badge');

    // Session ID for server-side memory
    const SESSION_KEY = 'food_chat_session_id';
    const HISTORY_KEY = 'food_chat_history';

    let sessionId = localStorage.getItem(SESSION_KEY);
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        localStorage.setItem(SESSION_KEY, sessionId);
    }

    // Location data from browser
    let userLocation = { lat: null, lon: null, city: 'unknown', state: '', country: 'unknown' };

    // ── Location detection ──────────────────────────────────────────

    function detectLocation() {
        if (!navigator.geolocation) {
            locationBadge.textContent = '📍 Unavailable';
            return;
        }

        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                userLocation.lat = pos.coords.latitude;
                userLocation.lon = pos.coords.longitude;

                // Reverse geocode with Nominatim
                try {
                    const url = `https://nominatim.openstreetmap.org/reverse?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}&format=json&zoom=10`;
                    const resp = await fetch(url, {
                        headers: { 'User-Agent': 'aiml_project_food_reco' }
                    });
                    if (resp.ok) {
                        const data = await resp.json();
                        const addr = data.address || {};
                        userLocation.city = addr.city || addr.town || addr.village || 'unknown';
                        userLocation.state = addr.state || addr.state_district || '';
                        userLocation.country = addr.country || 'unknown';
                    }
                } catch (_) { /* use defaults */ }

                const display = userLocation.city !== 'unknown'
                    ? `${userLocation.city}, ${userLocation.state}`
                    : `${userLocation.lat.toFixed(1)}, ${userLocation.lon.toFixed(1)}`;
                locationBadge.textContent = `📍 ${display}`;
                locationBadge.classList.add('active');
            },
            () => {
                locationBadge.textContent = '📍 Denied';
            },
            { enableHighAccuracy: false, timeout: 8000 }
        );
    }

    locationBadge.addEventListener('click', detectLocation);
    detectLocation();

    // ── Chat history (localStorage cache) ───────────────────────────

    function loadHistory() {
        try {
            const raw = localStorage.getItem(HISTORY_KEY);
            if (!raw) return;
            const history = JSON.parse(raw);
            history.forEach(msg => appendMessage(msg.role, msg.content, false));
            scrollToBottom();
        } catch (_) { /* corrupt data, ignore */ }
    }

    function saveHistory() {
        const bubbles = messagesEl.querySelectorAll('.message');
        const history = [];
        bubbles.forEach(el => {
            // skip the initial greeting (first assistant message from HTML)
            if (history.length === 0 && el.classList.contains('assistant') && !el.dataset.saved) return;
            const role = el.classList.contains('user') ? 'user' : 'assistant';
            history.push({ role, content: el.querySelector('.bubble').textContent.trim() });
        });
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    }

    function clearHistory() {
        localStorage.removeItem(HISTORY_KEY);
        // Clear server-side memory
        fetch('/api/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId }),
        });
        // Reset session
        sessionId = crypto.randomUUID();
        localStorage.setItem(SESSION_KEY, sessionId);
        // Clear UI — keep only the greeting
        messagesEl.innerHTML = `
            <div class="message assistant">
                <div class="bubble">
                    Hey there! 👋 I'm your Indian food recommender. Tell me what you're in the mood for — spicy, sweet, a main course, a snack, vegetarian, non-veg — and I'll suggest dishes suited to your taste and location!
                </div>
            </div>`;
        scrollToBottom();
    }

    clearBtn.addEventListener('click', clearHistory);

    // ── Message rendering ───────────────────────────────────────────

    function appendMessage(role, text, save = true) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.dataset.saved = 'true';
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.textContent = text;
        div.appendChild(bubble);
        messagesEl.appendChild(div);
        scrollToBottom();
        if (save) saveHistory();
    }

    function showTyping() {
        const div = document.createElement('div');
        div.className = 'message assistant typing-indicator';
        div.id = 'typing';
        div.innerHTML = `<div class="bubble"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>`;
        messagesEl.appendChild(div);
        scrollToBottom();
    }

    function hideTyping() {
        const el = document.getElementById('typing');
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // ── Send message ────────────────────────────────────────────────

    async function sendMessage(text) {
        appendMessage('user', text);
        input.value = '';
        sendBtn.disabled = true;
        showTyping();

        try {
            const resp = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    session_id: sessionId,
                    lat: userLocation.lat,
                    lon: userLocation.lon,
                    city: userLocation.city,
                    state: userLocation.state,
                    country: userLocation.country,
                }),
            });

            hideTyping();

            if (!resp.ok) {
                appendMessage('assistant', 'Sorry, something went wrong. Please try again.');
                return;
            }

            const data = await resp.json();
            appendMessage('assistant', data.reply);
        } catch (err) {
            hideTyping();
            appendMessage('assistant', 'Could not reach the server. Is the backend running?');
        } finally {
            sendBtn.disabled = false;
            input.focus();
        }
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        sendMessage(text);
    });

    // ── Init ────────────────────────────────────────────────────────

    loadHistory();
    input.focus();
})();
