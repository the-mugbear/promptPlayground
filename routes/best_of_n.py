import random
import string
import time
import json
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, stream_with_context
from models.model_Endpoints import Endpoint
from models.model_Dialogue import Dialogue
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import headers_from_apiheader_list

best_of_n_bp = Blueprint('best_of_n_bp', __name__, url_prefix='/best_of_n')

@best_of_n_bp.route('/', methods=['GET', 'POST'])
def best_of_n_index():
    endpoints = Endpoint.query.all()
    if request.method == 'POST':
        initial_prompt = request.form.get('initial_prompt')
        endpoint_id = request.form.get('registered_endpoint')
        if not initial_prompt or not endpoint_id:
            flash("Initial prompt and a registered endpoint are required.", "error")
            return redirect(url_for('best_of_n_bp.best_of_n_index'))
        query_params = request.form.to_dict()
        return redirect(url_for('best_of_n_bp.best_of_n_index', **query_params))
    
    if request.args.get('initial_prompt') and request.args.get('registered_endpoint'):
        initial_prompt = request.args.get('initial_prompt')
        endpoint_id = request.args.get('registered_endpoint')
        try:
            num_samples = int(request.args.get('num_samples', 10))
        except ValueError:
            num_samples = 10

        options = {
            "rearrange": request.args.get('rearrange') == 'on',
            "capitalization": request.args.get('capitalization') == 'on',
            "substitute": request.args.get('substitute') == 'on',
            "typo": request.args.get('typo') == 'on'
        }
        
        endpoint = Endpoint.query.get_or_404(endpoint_id)
        # Override endpoint values with values from query parameters, if provided.
        ep_name = request.args.get('ep_name')
        if ep_name:
            endpoint.name = ep_name
        ep_hostname = request.args.get('ep_hostname')
        if ep_hostname:
            endpoint.hostname = ep_hostname
        ep_endpoint = request.args.get('ep_endpoint')
        if ep_endpoint:
            endpoint.endpoint = ep_endpoint
        ep_payload = request.args.get('ep_payload')
        if ep_payload:
            endpoint.http_payload = ep_payload

        hostname = endpoint.hostname
        endpoint_path = endpoint.endpoint
        payload_template = endpoint.http_payload
        
        permutations = generate_permutations(initial_prompt, options, num_samples)
        attempts_log = []
        
        def prepare_raw_headers(endpoint):
            headers_dict = headers_from_apiheader_list(endpoint.headers)
            headers_dict.setdefault("Content-Type", "application/json")
            return "\n".join([f"{k}: {v}" for k, v in headers_dict.items()])
        
        def generate():
            raw_headers = prepare_raw_headers(endpoint)
            for perm in permutations:
                payload = payload_template.replace("{{INJECT_PROMPT}}", perm)
                response = replay_post_request(hostname, endpoint_path, payload, raw_headers=raw_headers)
                attempt_data = {
                    "prompt": perm,
                    "response": response.get("response_text")
                }
                attempts_log.append(attempt_data)
                yield f"data: {json.dumps(attempt_data)}\n\n"
                time.sleep(0.1)
            final_message = {"final": True, "attempts_log": attempts_log}
            dialogue_record = Dialogue(conversation=json.dumps(attempts_log), source="best_of_n", endpoint_id=endpoint.id)
            from extensions import db  # ensure db is imported within this context
            db.session.add(dialogue_record)
            db.session.commit()
            yield f"data: {json.dumps(final_message)}\n\n"
        
        return Response(stream_with_context(generate()), mimetype="text/event-stream")
    
    return render_template('attacks/best_of_n/index.html', endpoints=endpoints)



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

def substitute_common_typo(s):
    """
    Substitute one randomly chosen letter in the input string with an adjacent key 
    (based on a QWERTY keyboard layout) to mimic a common typing error.
    """
    keyboard_adjacent = {
        'q': ['w', 'a'],
        'w': ['q', 'e', 'a', 's'],
        'e': ['w', 'r', 's', 'd'],
        'r': ['e', 't', 'd', 'f'],
        't': ['r', 'y', 'f', 'g'],
        'y': ['t', 'u', 'g', 'h'],
        'u': ['y', 'i', 'h', 'j'],
        'i': ['u', 'o', 'j', 'k'],
        'o': ['i', 'p', 'k', 'l'],
        'p': ['o', 'l'],
        'a': ['q', 'w', 's', 'z'],
        's': ['a', 'w', 'e', 'd', 'z', 'x'],
        'd': ['s', 'e', 'r', 'f', 'x', 'c'],
        'f': ['d', 'r', 't', 'g', 'c', 'v'],
        'g': ['f', 't', 'y', 'h', 'v', 'b'],
        'h': ['g', 'y', 'u', 'j', 'b', 'n'],
        'j': ['h', 'u', 'i', 'k', 'n', 'm'],
        'k': ['j', 'i', 'o', 'l', 'm'],
        'l': ['k', 'o', 'p'],
        'z': ['a', 's', 'x'],
        'x': ['z', 's', 'd', 'c'],
        'c': ['x', 'd', 'f', 'v'],
        'v': ['c', 'f', 'g', 'b'],
        'b': ['v', 'g', 'h', 'n'],
        'n': ['b', 'h', 'j', 'm'],
        'm': ['n', 'j', 'k']
    }
    indices = [i for i, ch in enumerate(s) if ch.isalpha()]
    if not indices:
        return s
    idx = random.choice(indices)
    original_letter = s[idx]
    lower_letter = original_letter.lower()
    if lower_letter in keyboard_adjacent:
        neighbors = keyboard_adjacent[lower_letter]
        new_letter = random.choice(neighbors)
        if original_letter.isupper():
            new_letter = new_letter.upper()
    else:
        new_letter = random.choice(string.ascii_letters)
    return s[:idx] + new_letter + s[idx+1:]


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
        if options.get("typo"):
            perm = substitute_common_typo(perm)
        permutations.append(perm)
    return permutations
