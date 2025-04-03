import random
import string
import time
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import parse_raw_headers

def apply_random_transformations(prompt):
    # A simple example of a random transformation
    transformations = [
        lambda s: s.upper(),
        lambda s: s.lower(),
        lambda s: s.capitalize()
    ]
    transform = random.choice(transformations)
    noise = ''.join(random.choices(string.ascii_letters, k=5))
    return f"{transform(prompt)} {noise}"

def is_positive_response(response_text):
    # Placeholder: consider the response positive if it includes 'success'
    return response_text and "success" in response_text.lower()

def evil_agent_jailbreak_generator(adversarial_endpoint, recipient_endpoint, base_prompt, max_samples=10):
    attempts_log = []
    
    def prepare_raw_headers(endpoint):
        return "\n".join([f"{h.key}: {h.value}" for h in endpoint.headers])
    
    for i in range(max_samples):
        trial_prompt = apply_random_transformations(base_prompt)
        
        adv_payload = adversarial_endpoint.http_payload.replace("{{INJECT_PROMPT}}", trial_prompt)
        adv_response = replay_post_request(
            adversarial_endpoint.hostname,
            adversarial_endpoint.endpoint,
            adv_payload,
            raw_headers=prepare_raw_headers(adversarial_endpoint)
        )
        
        rec_payload = recipient_endpoint.http_payload.replace("{{INJECT_PROMPT}}", trial_prompt)
        rec_response = replay_post_request(
            recipient_endpoint.hostname,
            recipient_endpoint.endpoint,
            rec_payload,
            raw_headers=prepare_raw_headers(recipient_endpoint)
        )
        
        attempt_data = {
            'attempt': i + 1,
            'prompt': trial_prompt,
            'response': rec_response.get("response_text")
        }
        attempts_log.append(attempt_data)
        
        # Yield current attempt data to be streamed to the frontend.
        yield attempt_data
        
        if is_positive_response(rec_response.get("response_text")):
            # Yield final result flag and complete log when a successful jailbreak is found.
            yield {
                'final': True,
                'augmented_prompt': trial_prompt,
                'response': rec_response.get("response_text"),
                'attempts_log': attempts_log
            }
            return
        
        time.sleep(0.1)
    
    # If no success after max_samples, yield final message.
    yield {
        'final': True,
        'augmented_prompt': None,
        'response': None,
        'attempts_log': attempts_log
    }
