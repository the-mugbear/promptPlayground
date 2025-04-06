from flask import Blueprint, render_template
import json
from models.model_Dialogue import Dialogue

dialogue_bp = Blueprint('dialogue_bp', __name__, url_prefix='/dialogues')

@dialogue_bp.route('/', methods=['GET'])
def list_dialogues():
    dialogues = Dialogue.query.order_by(Dialogue.created_at.desc()).all()
    # Pre-load the conversation for each dialogue.
    for dialogue in dialogues:
        dialogue.loaded_conversation = json.loads(dialogue.conversation)
    return render_template('attacks/best_of_n/view_dialogues.html', dialogues=dialogues)
