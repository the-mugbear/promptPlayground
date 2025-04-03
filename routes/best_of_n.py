import random
import string
import time
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from models.model_Endpoints import Endpoint
from services.common.http_request_service import replay_post_request

best_of_n_bp = Blueprint('best_of_n_bp', __name__, url_prefix='/best_of_n')

# ********************************
# ROUTES
# ********************************
@best_of_n_bp.route('/', methods=['GET', 'POST'])
def best_of_n_index():
    # Query the registered endpoints from the database.
    endpoints = Endpoint.query.all()
    if request.method == 'POST':
        initial_prompt = request.form.get('initial_prompt')
        endpoint_id = request.form.get('registered_endpoint')
        try:
            num_samples = int(request.form.get('num_samples', 10))
        except ValueError:
            num_samples = 10

        options = {
            "rearrange": request.form.get('rearrange') == 'on',
            "capitalization": request.form.get('capitalization') == 'on',
            "substitute": request.form.get('substitute') == 'on'
        }
        
        if not initial_prompt or not endpoint_id:
            flash("Initial prompt and a registered endpoint are required.", "error")
            return redirect(url_for('best_of_n_bp.best_of_n_index'))
        
        # Get the selected endpoint.
        endpoint = Endpoint.query.get_or_404(endpoint_id)
        hostname = endpoint.hostname
        endpoint_path = endpoint.endpoint
        payload_template = endpoint.http_payload
        
        # Generate the permutations.
        permutations = generate_permutations(initial_prompt, options, num_samples)
        attempts_log = []
        for perm in permutations:
            # Replace the placeholder in the payload template.
            payload = payload_template.replace("{{INJECT_PROMPT}}", perm)
            response = replay_post_request(hostname, endpoint_path, payload, raw_headers="")
            attempts_log.append({
                "prompt": perm,
                "response": response.get("response_text")
            })
            time.sleep(0.1)
        
        return render_template('best_of_n/result.html', attempts_log=attempts_log)
    
    return render_template('best_of_n/index.html', endpoints=endpoints)

@best_of_n_bp.route('/endpoint_details/<int:endpoint_id>', methods=['GET'])
def endpoint_details(endpoint_id):
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    headers_list = [{"key": h.key, "value": h.value} for h in endpoint.headers]
    return jsonify({
        "id": endpoint.id,
        "name": endpoint.name,
        "hostname": endpoint.hostname,
        "endpoint": endpoint.endpoint,
        "http_payload": endpoint.http_payload,
        "headers": headers_list
    })


# ********************************
# SERVICES
# ********************************
def rearrange_letters(s):
    """Randomly rearrange the middle letters of one word (if available)."""
    words = s.split()
    candidates = [w for w in words if len(w) > 3]
    if not candidates:
        return s
    word = random.choice(candidates)
    index = words.index(word)
    first, middle, last = word[0], list(word[1:-1]), word[-1]
    random.shuffle(middle)
    new_word = first + "".join(middle) + last
    words[index] = new_word
    return " ".join(words)

def random_capitalize(s):
    """Randomly toggle the case of each alphabetical character."""
    result = ""
    for ch in s:
        if ch.isalpha() and random.random() < 0.5:
            result += ch.upper() if ch.islower() else ch.lower()
        else:
            result += ch
    return result

def substitute_random_letter(s):
    """Substitute one randomly chosen letter with another random letter."""
    indices = [i for i, ch in enumerate(s) if ch.isalpha()]
    if not indices:
        return s
    idx = random.choice(indices)
    random_letter = random.choice(string.ascii_letters)
    return s[:idx] + random_letter + s[idx+1:]

def generate_permutations(prompt, options, n):
    """Generate n permutations of the prompt using the selected options."""
    permutations = []
    for i in range(n):
        perm = prompt
        if options.get("rearrange"):
            perm = rearrange_letters(perm)
        if options.get("capitalization"):
            perm = random_capitalize(perm)
        if options.get("substitute"):
            perm = substitute_random_letter(perm)
        permutations.append(perm)
    return permutations


