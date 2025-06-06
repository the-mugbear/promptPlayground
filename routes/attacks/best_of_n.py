import random
import string
import time
import json
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, stream_with_context
from models.model_Endpoints import Endpoint
from models.model_Dialogue import Dialogue
from services.common.http_request_service import execute_api_request
from services.common.header_parser_service import headers_from_apiheader_list
from extensions import db 

best_of_n_bp = Blueprint('best_of_n_bp', __name__, url_prefix='/best_of_n')

@best_of_n_bp.route('/', methods=['GET', 'POST'])
def best_of_n_index():
    endpoints = Endpoint.query.all()

    # Handle POST requests by redirecting to GET with query parameters
    if request.method == 'POST':
        initial_prompt = request.form.get('initial_prompt')
        endpoint_id = request.form.get('registered_endpoint')
        # Basic validation - more robust validation can be added
        if not initial_prompt or not endpoint_id:
            flash("Initial prompt and a registered endpoint are required.", "error")
            # Pass existing endpoints back to the template on error redirect
            return render_template('attacks/best_of_n/index.html', endpoints=endpoints) 
        
        # Check if at least one transformation is selected (assuming checkbox names match keys in 'options')
        transformations_selected = any(request.form.get(key) == 'on' for key in ["rearrange", "capitalization", "substitute", "typo"])
        if not transformations_selected:
             flash("Please select at least one permutation option.", "error")
             return render_template('attacks/best_of_n/index.html', endpoints=endpoints, form_data=request.form) # Pass form data back

        query_params = request.form.to_dict()
        # Redirect to the same route using GET with parameters
        return redirect(url_for('best_of_n_bp.best_of_n_index', **query_params))

    # Handle GET requests - either initial page load or after POST redirect
    if request.args.get('initial_prompt') and request.args.get('registered_endpoint'):
        # --- Parameters for SSE Stream ---
        initial_prompt = request.args.get('initial_prompt')
        endpoint_id = request.args.get('registered_endpoint')
        try:
            num_samples = int(request.args.get('num_samples', 10))
            if num_samples < 1: num_samples = 1 # Ensure at least 1 sample
        except ValueError:
            num_samples = 10

        options = {
            "rearrange": request.args.get('rearrange') == 'on',
            "capitalization": request.args.get('capitalization') == 'on',
            "substitute": request.args.get('substitute') == 'on',
            "typo": request.args.get('typo') == 'on'
        }

        # Check again if transformations selected (important if accessed via GET directly)
        if not any(options.values()):
             flash("Please select at least one permutation option.", "error")
             # Need endpoints for the template render
             return render_template('attacks/best_of_n/index.html', endpoints=Endpoint.query.all(), form_data=request.args)


        endpoint = Endpoint.query.get_or_404(endpoint_id)
        # Override endpoint values with values from query parameters, if provided.
        # This allows using the edited values from the frontend form
        ep_name = request.args.get('ep_name')
        if ep_name:
            endpoint.name = ep_name # Note: This doesn't save the change to DB, only uses for this request
        ep_hostname = request.args.get('ep_hostname')
        if ep_hostname:
            endpoint.hostname = ep_hostname
        ep_endpoint = request.args.get('ep_endpoint')
        if ep_endpoint:
            endpoint.endpoint = ep_endpoint
        ep_payload = request.args.get('ep_payload')
        if ep_payload:
            endpoint.http_payload = ep_payload

        # Use potentially overridden values
        hostname = endpoint.hostname
        endpoint_path = endpoint.endpoint
        payload_template = endpoint.http_payload

        # Generate all permutations upfront (could be changed to generate on-the-fly if needed)
        permutations = generate_permutations(initial_prompt, options, num_samples)
        attempts_log = [] # Log to store results

        def prepare_raw_headers(ep):
            headers_dict = headers_from_apiheader_list(ep.headers)
            # Ensure Content-Type is set, default to application/json if not present
            headers_dict.setdefault("Content-Type", "application/json") 
            return "\n".join([f"{k}: {v}" for k, v in headers_dict.items()])

        def generate():
            nonlocal attempts_log # Allow modification of the outer scope variable
            raw_headers = prepare_raw_headers(endpoint)
            
            # --- Initial Status Update ---
            yield f"data: {json.dumps({'status': 'Starting Best of N process...'})}\n\n"
            time.sleep(0.2) # Small delay for frontend to show initial status

            # --- Loop through permutations ---
            for i, perm in enumerate(permutations):
                
                # --- Status Update: Before Request ---
                status_message = f"Processing permutation {i + 1}/{num_samples}..."
                yield f"data: {json.dumps({'status': status_message})}\n\n"
                
                # Prepare payload for this specific permutation
                # Use try-except for robust replacement, handle potential errors
                try:
                    # Parse the payload template as JSON
                    payload_dict = json.loads(payload_template)
                    # Find and replace the INJECT_PROMPT token in the messages
                    for message in payload_dict.get('messages', []):
                        if 'content' in message and '{{INJECT_PROMPT}}' in message['content']:
                            message['content'] = message['content'].replace('{{INJECT_PROMPT}}', perm)
                    # Convert back to JSON string
                    payload = json.dumps(payload_dict)
                except Exception as e:
                    # Handle error during payload creation (e.g., template issue)
                    error_message = f"Error creating payload for permutation {i + 1}: {e}"
                    yield f"data: {json.dumps({'status': error_message, 'error': True})}\n\n" 
                    # Log the attempt with an error state
                    attempts_log.append({"prompt": perm, "response": f"ERROR: {error_message}", "error": True})
                    continue # Skip to the next permutation

                # --- Make the HTTP request ---
                try:
                    # Add timeout to prevent hanging indefinitely
                    response_data = execute_api_request(hostname, endpoint_path, payload, raw_headers=raw_headers, timeout=30) 
                    response_text = response_data.get("response_text", "No response text received.")
                    is_error = False

                except Exception as e:
                    # Handle network errors or errors from execute_api_request
                    response_text = f"ERROR executing request for permutation {i + 1}: {e}"
                    is_error = True
                    # Yield an error status
                    yield f"data: {json.dumps({'status': response_text, 'error': True})}\n\n"

                # --- Store and Yield Result ---
                attempt_data = {
                    "prompt": perm,
                    "response": response_text
                }
                if is_error:
                     attempt_data["error"] = True # Mark if request failed

                attempts_log.append(attempt_data)
                # Yield the actual prompt/response pair
                yield f"data: {json.dumps(attempt_data)}\n\n"

                # Optional short delay between requests/yields
                time.sleep(0.1) 

            # --- Process finished ---
            yield f"data: {json.dumps({'status': 'Processing complete. Finalizing...'})}\n\n"
            
            # --- Find Best Result (Placeholder - Implement your logic here) ---
            # Example: find the shortest non-error response
            best_prompt = None
            best_response = None
            # Add logic here to evaluate attempts_log and set best_prompt/best_response
            # For now, we'll leave them as None

            # --- Save to Database ---
            try:
                dialogue_record = Dialogue(
                    conversation=json.dumps(attempts_log), 
                    source="best_of_n", 
                    endpoint_id=endpoint.id
                )
                db.session.add(dialogue_record)
                db.session.commit()
            except Exception as e:
                 # Log DB save error, but don't necessarily stop the SSE stream
                 print(f"Error saving dialogue to DB: {e}") 
                 # Optionally yield a status update about the DB error
                 yield f"data: {json.dumps({'status': 'Warning: Could not save results to database.', 'error': True})}\n\n"


            # --- Final Message ---
            final_message = {
                "final": True, 
                "attempts_log": attempts_log,
                # Include best result if found, otherwise frontend handles absence
                "best_prompt": best_prompt, 
                "best_response": best_response 
            }
            yield f"data: {json.dumps(final_message)}\n\n"

        # Return the SSE response
        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    # Default GET request: Render the initial form page
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
