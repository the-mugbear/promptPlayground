import json

def process_transformations(form):
    ordered_transformations_json = form.get('ordered_transformations')
    if ordered_transformations_json:
        ordered_transformations = json.loads(ordered_transformations_json)
    else:
        ordered_transformations = []
    
    prepend_text = form.get('text_to_prepend')
    postpend_text = form.get('text_to_postpend')
    final_transformations = []
    for t in ordered_transformations:
        if t == "prepend_text":
            final_transformations.append({"type": t, "value": prepend_text})
        elif t == "postpend_text":
            final_transformations.append({"type": t, "value": postpend_text})
        else:
            final_transformations.append({"type": t})
    return final_transformations
