from flask import Flask, request, jsonify, render_template, session
import pandas as pd
import numpy as np
import ollama
import os
import re
import requests as req_lib

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ── Load data and prepare the Suggestion engine ────────────────────────

REGIONAL_DIET = {
    'Rajasthan': 'vegetarian',   'Haryana': 'vegetarian',
    'Punjab': 'any',             'Uttar Pradesh': 'vegetarian',
    'Uttarakhand': 'vegetarian', 'Himachal Pradesh': 'any',
    'Jammu & Kashmir': 'any',    'NCT of Delhi': 'any',
    'Madhya Pradesh': 'vegetarian', 'Chhattisgarh': 'vegetarian',
    'Bihar': 'any',
    'Gujarat': 'vegetarian',
    'Maharashtra': 'any',        'Goa': 'non vegetarian',
    'Karnataka': 'any',          'Tamil Nadu': 'any',
    'Kerala': 'non vegetarian',  'Andhra Pradesh': 'any',
    'Telangana': 'any',
    'West Bengal': 'non vegetarian', 'Odisha': 'any',
    'Jharkhand': 'any',
    'Assam': 'non vegetarian',   'Nagaland': 'non vegetarian',
    'Manipur': 'any',            'Tripura': 'non vegetarian',
    'Meghalaya': 'non vegetarian', 'Mizoram': 'non vegetarian',
    'Arunachal Pradesh': 'non vegetarian', 'Sikkim': 'non vegetarian',
}

REGIONAL_FLAVOR = {
    'Rajasthan': 'spicy',    'Gujarat': 'sweet',     'Punjab': 'spicy',
    'Uttar Pradesh': 'spicy','Tamil Nadu': 'spicy',   'Kerala': 'spicy',
    'West Bengal': 'sweet',  'Maharashtra': 'spicy',  'Karnataka': 'spicy',
    'Andhra Pradesh': 'spicy','Telangana': 'spicy',   'Goa': 'spicy',
    'Bihar': 'spicy',        'Odisha': 'sweet',       'Assam': 'spicy',
    'Haryana': 'spicy',      'Himachal Pradesh': 'spicy',
    'Jammu & Kashmir': 'spicy', 'NCT of Delhi': 'spicy',
    'Madhya Pradesh': 'spicy', 'Chhattisgarh': 'spicy',
    'Uttarakhand': 'spicy',
}

CSV_PATH = os.path.join(os.path.dirname(__file__), 'indian_food.csv')
df = pd.read_csv(CSV_PATH)


def _norm_text(s: pd.Series) -> pd.Series:
    return s.astype(str).replace('nan', np.nan).str.strip()


def preprocess(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, list, dict]:
    dataframe = dataframe.copy()
    dataframe.replace({'-1': np.nan, -1: np.nan}, inplace=True)
    text_cols = ['name', 'ingredients', 'diet', 'flavor_profile', 'course', 'state', 'region']
    for c in text_cols:
        if c in dataframe.columns:
            dataframe[c] = _norm_text(dataframe[c])
    if 'diet' in dataframe.columns:
        dataframe['diet'] = dataframe['diet'].str.lower().replace({
            'veg': 'vegetarian', 'nonveg': 'non vegetarian',
            'non-veg': 'non vegetarian', 'non-vegetarian': 'non vegetarian',
            'non vegetarian ': 'non vegetarian', 'vegetarian ': 'vegetarian',
        })
    for c in ['flavor_profile', 'course', 'region']:
        if c in dataframe.columns:
            dataframe[c] = dataframe[c].str.lower()
    dataframe = dataframe.dropna(subset=['name', 'ingredients'], how='any').reset_index(drop=True)
    states = dataframe['state'].dropna().unique().tolist()
    state_to_region = (dataframe[['state', 'region']]
                       .dropna().drop_duplicates()
                       .set_index('state')['region'].to_dict())
    return dataframe, states, state_to_region


df, STATES, STATE_TO_REGION = preprocess(df)

# In-memory chat history per session id
chat_histories: dict[str, list[dict]] = {}


def match_state(detected_state: str) -> str | None:
    if not detected_state:
        return None
    det = detected_state.lower().strip()
    for s in STATES:
        if s.lower() == det:
            return s
    for s in sorted(STATES, key=len, reverse=True):
        if s.lower() in det or det in s.lower():
            return s
    return None


def reverse_geocode_state(lat: float, lon: float) -> str | None:
    try:
        resp = req_lib.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'lat': lat, 'lon': lon, 'format': 'json', 'zoom': 5},
            headers={'User-Agent': 'aiml_project_food_reco'},
            timeout=5,
        )
        if resp.ok:
            address = resp.json().get('address', {})
            return address.get('state') or address.get('state_district')
    except Exception:
        pass
    return None


def build_prompt(description: str, location_info: str, history: list[dict]) -> list[dict]:
    dish_summary = (
        df.groupby(['region', 'diet'], dropna=False)['name']
        .apply(lambda x: ', '.join(x.dropna().unique()[:12]))
        .reset_index().to_string(index=False)
    )
    sample = df.to_string(index=False)

    system_msg = (
        "You are an Indian food recommendation chatbot. "
        "You help users discover Indian dishes based on their preferences and location.\n\n"
        f"USER LOCATION:\n{location_info}\n\n"
        f"AVAILABLE DISHES BY REGION AND DIET:\n{dish_summary}\n\n"
        f"FULL DISH DATABASE (name, ingredients, diet, prep_time, cook_time, flavor_profile, course, state, region):\n{sample}\n\n"
        "Rules:\n"
        "- Only suggest dishes that exist in the data above.\n"
        "- Always consider the user's location and regional preferences when making recommendations.\n"
        "- Be conversational and friendly.\n"
        "- If the user asks about a dish, provide its ingredients, prep time, etc. from the data.\n"
        "- Keep recommendations relevant to the user's location and preferences.\n"
    )

    messages = [{'role': 'system', 'content': system_msg}]
    for msg in history:
        messages.append({'role': msg['role'], 'content': msg['content']})
    messages.append({'role': 'user', 'content': description})
    return messages


# ── Routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({'error': 'No message provided'}), 400

    user_message = data['message']
    session_id = data.get('session_id', 'default')
    lat = data.get('lat')
    lon = data.get('lon')
    city = data.get('city', 'unknown')
    state_raw = data.get('state', '')
    country = data.get('country', 'unknown')

    # Resolve state
    matched = match_state(state_raw)
    if not matched and lat is not None and lon is not None:
        try:
            fallback = reverse_geocode_state(float(lat), float(lon))
            if fallback:
                matched = match_state(fallback)
        except (ValueError, TypeError):
            pass

    regional_diet = REGIONAL_DIET.get(matched, 'any') if matched else 'any'
    regional_flavor = REGIONAL_FLAVOR.get(matched, 'any') if matched else 'any'

    location_info = (
        f"City: {city}, State: {matched or state_raw or 'unknown'}, "
        f"Country: {country}, "
        f"Regional diet: {regional_diet}, Regional flavor: {regional_flavor}"
    )

    # Get or create chat history
    if session_id not in chat_histories:
        chat_histories[session_id] = []
    history = chat_histories[session_id]

    messages = build_prompt(user_message, location_info, history)

    response = ollama.chat(model='llama3.2', messages=messages)
    assistant_reply = response['message']['content']

    # Save to history
    history.append({'role': 'user', 'content': user_message})
    history.append({'role': 'assistant', 'content': assistant_reply})

    return jsonify({'reply': assistant_reply})


@app.route('/api/clear', methods=['POST'])
def clear_memory():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')
    chat_histories.pop(session_id, None)
    return jsonify({'status': 'cleared'})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
