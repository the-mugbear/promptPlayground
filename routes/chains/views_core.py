import json
from flask import render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from forms import ChainForm, ChainStepForm
from models.model_APIChain import APIChain, APIChainStep
from models import Endpoint
from services.common.templating_service import get_template_variables
from extensions import db
from sqlalchemy import func

from . import chains_bp

@chains_bp.route('/wizard', methods=['GET'])
@login_required
def chain_wizard():
    """Guided chain creation wizard"""
    endpoints = Endpoint.query.filter_by(user_id=current_user.id).all()
    return render_template('chains/wizard.html', endpoints=endpoints, title="Chain Creation Wizard")

@chains_bp.route('/', methods=['GET'])
@login_required
def list_chains():
    """
    Renders the page that lists all API Chains with their step counts
    in an optimized query.
    """
    # This query efficiently joins the chains with their steps and counts them
    # in a single database request, avoiding the N+1 query problem.
    chains_with_step_counts = db.session.query(
        APIChain,
        func.count(APIChainStep.id).label('step_count')
    ).outerjoin(APIChainStep, APIChain.id == APIChainStep.chain_id)\
    .group_by(APIChain.id)\
    .order_by(APIChain.name)\
    .all()

    return render_template('chains/list_chains.html', chains_data=chains_with_step_counts, title="API Chains")

@chains_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_chain():
    """
    Handles the creation of a new API Chain.
    """
    form = ChainForm()
    if form.validate_on_submit():
        new_chain = APIChain(
            name=form.name.data,
            description=form.description.data,
            user_id=current_user.id
        )
        db.session.add(new_chain)
        db.session.commit()
        flash(f'Successfully created new chain: "{new_chain.name}"', 'success')
        return redirect(url_for('chains_bp.chain_details', chain_id=new_chain.id))
    return render_template('chains/create_chain.html', form=form, title="Create New Chain")

@chains_bp.route('/<int:chain_id>', methods=['GET'], endpoint='chain_details')
@login_required
def chain_details_view(chain_id):
    """
    Displays the details of a single API Chain and a form to add a new step.
    """
    chain = db.session.get(APIChain, chain_id)
    if not chain or chain.user_id != current_user.id:
        abort(404)
    
    # Pre-process steps to include input/output analysis
    processed_steps = []
    # Sort steps by their defined order before processing
    sorted_steps = sorted(chain.steps, key=lambda s: s.step_order)

    for step in sorted_steps:
        # --- CORRECTED LOGIC ---

        # 1. Determine the correct PAYLOAD template to parse.
        #    Use the step's own payload if it exists, otherwise fall back to the endpoint's default.
        payload_template_to_parse = step.payload if step.payload is not None else (step.endpoint.payload_template.template if step.endpoint.payload_template else None)

        # 2. Determine the correct HEADERS template to parse.
        #    Use the step's own headers if they exist, otherwise build them from the endpoint's defaults.
        if step.headers is not None:
            headers_template_to_parse = step.headers
        else:
            # The endpoint's headers are a list of objects; build a JSON string from them.
            headers_dict = {h.key: h.value for h in step.endpoint.headers}
            headers_template_to_parse = json.dumps(headers_dict)

        # 3. Parse the chosen templates to find the input variables.
        payload_vars = get_template_variables(payload_template_to_parse or '')
        header_vars = get_template_variables(headers_template_to_parse or '')
        
        # 4. Get the output variables from the step's rules (this was already correct).
        produced_vars = {rule.get('variable_name') for rule in (step.data_extraction_rules or []) if rule.get('variable_name')}
        
        processed_steps.append({
            'step_obj': step,
            'inputs': sorted(list(payload_vars.union(header_vars))),
            'outputs': sorted(list(produced_vars))
        })

    form = ChainStepForm()
    form.endpoint.choices = [(e.id, e.name) for e in db.session.query(Endpoint).order_by(Endpoint.name).all()]

    return render_template('chains/chain_details.html', chain=chain, form=form, processed_steps=processed_steps, title=chain.name)

@chains_bp.route('/<int:chain_id>/steps/add', methods=['POST'])
@login_required
def add_step(chain_id):
    """
    Handles the form submission for adding a new step to a chain.
    """
    chain = db.session.get(APIChain, chain_id)
    if not chain or chain.user_id != current_user.id:
        abort(404)

    form = ChainStepForm(request.form)
    
    # We must populate choices before validation
    form.endpoint.choices = [(e.id, e.name) for e in db.session.query(Endpoint).order_by(Endpoint.name).all()]

    if form.validate_on_submit():
        new_step = APIChainStep(
            chain_id=chain.id,
            step_order=chain.steps.count() + 1,
            name=form.name.data,
            endpoint_id=form.endpoint.data,
            headers=form.headers.data,
            payload=form.payload.data,
            data_extraction_rules=json.loads(form.data_extraction_rules.data or '[]')
        )
        db.session.add(new_step)
        db.session.commit()
        flash('Step added successfully!', 'success')
    else:
        # If the form has errors, flash them to the user
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "danger")

    return redirect(url_for('chains_bp.chain_details', chain_id=chain.id))


@chains_bp.route('/<int:chain_id>/steps/<int:step_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_step(chain_id, step_id):
    """
    Handles editing an existing step in a chain.
    """
    chain = db.session.get(APIChain, chain_id)
    step = db.session.get(APIChainStep, step_id)
    if not chain or not step or chain.user_id != current_user.id or step.chain_id != chain.id:
        abort(404)

    form = ChainStepForm(obj=step)
    form.endpoint.choices = [(e.id, e.name) for e in db.session.query(Endpoint).order_by(Endpoint.name).all()]
    
    # Get available inputs from previous steps
    previous_steps = []
    all_available_vars = set()
    
    # Get all steps before this one, sorted by step_order
    prior_steps = APIChainStep.query.filter(
        APIChainStep.chain_id == chain.id,
        APIChainStep.step_order < step.step_order
    ).order_by(APIChainStep.step_order).all()
    
    for prior_step in prior_steps:
        step_vars = set()
        if prior_step.data_extraction_rules:
            for rule in prior_step.data_extraction_rules:
                if rule.get('variable_name'):
                    step_vars.add(rule['variable_name'])
        
        previous_steps.append({
            'step': prior_step,
            'variables': sorted(list(step_vars))
        })
        all_available_vars.update(step_vars)
    
    if form.validate_on_submit():
        # Update the step object with new values from the form
        step.name = form.name.data
        step.endpoint_id = form.endpoint.data
        step.headers = form.headers.data
        step.payload = form.payload.data

        try:
            step.data_extraction_rules = json.loads(form.data_extraction_rules.data or '[]')
            db.session.commit()
            flash(f"Step {step.step_order} updated successfully!", "success")
            return redirect(url_for('chains_bp.chain_details', chain_id=chain.id))
        except json.JSONDecodeError:
            flash("Invalid JSON in Data Extraction Rules.", "danger")
    
    # For GET request, pre-populate the text area with formatted JSON
    if request.method == 'GET':
        form.name.data = step.name
        form.endpoint.data = step.endpoint_id # Set the dropdown to the correct endpoint
        form.payload.data = step.payload
        form.headers.data = step.headers
        if step.data_extraction_rules:
            form.data_extraction_rules.data = json.dumps(step.data_extraction_rules, indent=2)

    return render_template('chains/edit_step.html', 
                         form=form, 
                         chain=chain, 
                         step=step, 
                         previous_steps=previous_steps,
                         all_available_vars=sorted(list(all_available_vars)),
                         title="Edit Step")

@chains_bp.route('/<int:chain_id>/steps/<int:step_id>/delete', methods=['POST'])
@login_required
def delete_step(chain_id, step_id):
    """
    Deletes a step from a chain and re-orders the remaining steps.
    """
    step_to_delete = db.session.get(APIChainStep, step_id)
    if not step_to_delete or step_to_delete.chain.user_id != current_user.id:
        abort(404)

    db.session.delete(step_to_delete)
    db.session.commit()

    # Re-order the remaining steps
    remaining_steps = APIChainStep.query.filter_by(chain_id=chain.id).order_by(APIChainStep.step_order).all()
    for index, step in enumerate(remaining_steps, 1):
        step.step_order = index
    db.session.commit()

    flash('Step deleted successfully.', 'success')
    return redirect(url_for('chains_bp.chain_details', chain_id=chain_id))

@chains_bp.route('/<int:chain_id>/debugger', methods=['GET'])
@login_required
def chain_debugger(chain_id):
    """Renders the interactive chain debugger page."""
    chain = db.session.get(APIChain, chain_id)
    if not chain or chain.user_id != current_user.id:
        abort(404)
    return render_template('chains/debugger.html', chain=chain, title=f"Debugger: {chain.name}")