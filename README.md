# AIML-Project - Location-aware Food Preference Classifier

An intelligent, location-aware Indian food recommendation chatbot powered by a local LLM (Llama 3.2 via Ollama) and a curated dataset of Indian dishes. The app detects the user's location and uses regional dietary and flavor preferences to suggest relevant dishes in a conversational interface.

---

## Features

- **Location-aware recommendations** — Detects the user's city and state via the browser Geolocation API, then maps regional preferences (e.g. vegetarian in Gujarat, non-vegetarian in West Bengal, sweet in Odisha) to personalize suggestions.
- **Conversational chat interface** — Multi-turn chat with persistent session memory, powered by Llama 3.2 running locally via Ollama.
- **Rich dish database** — The `indian_food.csv` dataset covers dishes across Indian states and regions, with fields for ingredients, diet type, prep/cook time, flavor profile, and course.
- **Session memory** — Chat history is stored both client-side (localStorage) and server-side (in-memory per session), with a one-click clear option.
- **Reverse geocoding fallback** — If the browser state label doesn't match the dataset, the app falls back to Nominatim (OpenStreetMap) to resolve the state name.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| LLM | Llama 3.2 via [Ollama](https://ollama.com) |
| Data | Pandas, NumPy |
| Frontend | Vanilla HTML/CSS/JS |
| Geocoding | Browser Geolocation API + Nominatim |

---

## Project Structure

```
.
├── app.py              # Flask backend — API routes, LLM integration, data logic
├── indian_food.csv     # Dataset of Indian dishes with regional metadata
├── templates/
│   └── index.html      # Main chat UI (served by Flask)
└── static/
    ├── style.css       # Dark-theme chat UI styles
    └── script.js       # Frontend chat logic, location detection, session management
```

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally
- Llama 3.2 model pulled: `ollama pull llama3.2`

### Install Dependencies

```bash
pip install flask pandas numpy ollama requests
```

### Run the App

```bash
python app.py
```

The app will be available at `http://localhost:5000`.

---

## Dataset

The `indian_food.csv` file contains Indian dishes with the following columns:

| Column | Description |
|---|---|
| `name` | Dish name |
| `ingredients` | Comma-separated ingredient list |
| `diet` | `vegetarian` or `non vegetarian` |
| `prep_time` | Preparation time in minutes |
| `cook_time` | Cooking time in minutes |
| `flavor_profile` | e.g. `spicy`, `sweet`, `sour` |
| `course` | e.g. `main course`, `dessert`, `snack` |
| `state` | Indian state of origin |
| `region` | Broad region (North, South, East, West, etc.) |

---

## How It Works

1. The user opens the app and the browser requests their location.
2. The detected state is matched against a regional preference map (dietary type and flavor profile) hardcoded in `app.py`.
3. On each message, the Flask backend builds a prompt that includes the user's location context, the full dish database summary, and the conversation history, then sends it to Llama 3.2 via Ollama.
4. The assistant responds with dish recommendations grounded in the dataset.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the chat UI |
| `POST` | `/api/chat` | Sends a user message, returns assistant reply |
| `POST` | `/api/clear` | Clears the server-side chat history for a session |

### `/api/chat` Request Body

```json
{
  "message": "I want something spicy and vegetarian",
  "session_id": "uuid-string",
  "lat": 22.5726,
  "lon": 88.3639,
  "city": "Kolkata",
  "state": "West Bengal",
  "country": "India"
}
```

---

## Notes

- The LLM is instructed to only recommend dishes present in the dataset.
- Session memory is stored in-memory on the server and will reset on restart.
- Network access is required for Nominatim reverse geocoding fallback; the app works without it if the browser provides a usable state name.
