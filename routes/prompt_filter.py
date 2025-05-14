from flask import Blueprint, render_template, request, redirect, flash, url_for
from extensions import db
from models.model_PromptFilter import PromptFilter 
import json

prompt_filter_bp = Blueprint('prompt_filter_bp', __name__, url_prefix='/prompt_filters')

# ********************************
# ROUTES
# ********************************
@prompt_filter_bp.route('/prompt-filter/new', methods=['GET', 'POST'])
def create_prompt_filter():
    if request.method == 'POST':
        name = request.form.get('name')
        invalid_chars_input = request.form.get('invalid_characters', '').strip()
        words_input = request.form.get('words_to_replace', '').strip()

        # Process invalid characters - split only by spaces, preserving all other characters
        invalid_characters = ','.join(char for char in invalid_chars_input.split() if char)

        # Try interpreting the input as JSON; enforce dict
        try:
            parsed = json.loads(words_input)
            if not isinstance(parsed, dict):
                raise ValueError("Expected JSON object mapping words to replacements")
            words_to_replace = parsed
        except (json.JSONDecodeError, TypeError, ValueError):
            # Fallback: parse comma-separated "word:replacement" pairs
            words_to_replace = {}
            for pair in words_input.split(','):
                if ':' in pair:
                    key, val = pair.split(':', 1)
                    words_to_replace[key.strip()] = val.strip()

        new_filter = PromptFilter(
            name=name,
            invalid_characters=invalid_characters,
            words_to_replace=words_to_replace
        )
        db.session.add(new_filter)
        db.session.commit()
        flash('Prompt filter created successfully!', 'success')
        return redirect(url_for('prompt_filter_bp.create_prompt_filter'))

    return render_template('prompt_filters/create_prompt_filter.html')


@prompt_filter_bp.route('/prompt-filter/list', methods=['GET'])
def list_prompt_filters():
    prompt_filters = PromptFilter.query.order_by(PromptFilter.created_at.desc()).all()
    return render_template('prompt_filters/list_prompt_filters.html', prompt_filters=prompt_filters)


@prompt_filter_bp.route('/prompt-filter/<int:filter_id>', methods=['GET'])
def view_prompt_filter(filter_id):
    prompt_filter = PromptFilter.query.get_or_404(filter_id)
    return render_template('prompt_filters/filter_details.html', prompt_filter=prompt_filter)


# ********************************
# SERVICES
# ********************************
@prompt_filter_bp.route('/<int:filter_id>/delete', methods=['POST'])
def delete_prompt_filter(filter_id):
    pf = PromptFilter.query.get_or_404(filter_id)
    db.session.delete(pf)
    db.session.commit()
    flash(f'Prompt filter "{pf.name}" deleted.', 'success')
    return redirect(url_for('prompt_filter_bp.list_prompt_filters'))
