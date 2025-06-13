# routes/chains/views_core.py
import json

from flask import render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from forms import ChainForm, ChainStepForm
from models.model_APIChain import APIChain, APIChainStep
from models import Endpoint
from extensions import db

from . import chains_bp

@chains_bp.route('/', methods=['GET'])
@login_required
def list_chains():
    """
    Renders the page that lists all API Chains.
    """
    # Query all chains, you can add pagination later
    chains = APIChain.query.order_by(APIChain.name).all()
    return render_template('chains/list_chains.html', chains=chains)


@chains_bp.route('/<int:chain_id>', methods=['GET'])
@login_required
def view_chain(chain_id):
    """
    Displays the details of a single API Chain and a form to add new steps.
    This simplified version is for the list-based view.
    """
    chain = APIChain.query.filter_by(id=chain_id).first_or_404()
    
    # We still need the form for the "Add New Step" card at the bottom of the page
    form = ChainStepForm()
    
    # We also still need to populate the dropdown choices for that form
    form.endpoint.choices = [
        (e.id, f"{e.name} ({e.method} {e.hostname}{e.endpoint})") 
        for e in Endpoint.query.order_by(Endpoint.name).all()
    ]

    # The logic to build the 'graph_definition' string has been removed.
    # The template will now handle iterating through chain.steps directly to build the list.
    return render_template(
        'chains/chain_details.html', 
        chain=chain, 
        title=chain.name, 
        form=form
    )

@chains_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_chain():
    """
    Handles the creation of a new API Chain.
    """
    form = ChainForm()
    if form.validate_on_submit():
        # Check if a chain with this name already exists for the user to avoid duplicates
        existing_chain = APIChain.query.filter_by(
            name=form.name.data, user_id=current_user.id).first()
        if existing_chain:
            flash(
                'A chain with this name already exists. Please choose a different name.', 'warning')
            return render_template('create_chain.html', form=form, title="Create New Chain")

        new_chain = APIChain(
            name=form.name.data,
            description=form.description.data,
            user_id=current_user.id
        )
        db.session.add(new_chain)
        db.session.commit()
        flash(f'Successfully created new chain: "{new_chain.name}"', 'success')
        # After creating, redirect to the new chain's detail page (which we will create next)
        # For now, let's redirect back to the list.
        return redirect(url_for('chains.list_chains'))

    return render_template('chains/create_chain.html', form=form, title="Create New Chain")


@chains_bp.route('/<int:chain_id>/steps/add', methods=['POST'])
@login_required
def add_step(chain_id):
    """
    Handles the form submission for adding a new step to a chain.
    """
    chain = APIChain.query.filter_by(id=chain_id).first_or_404()
    form = ChainStepForm()

    # Repopulate choices in case of validation error and re-render
    form.endpoint.choices = [
        (e.id, f"{e.name} ({e.method} {e.hostname}{e.endpoint})")
        for e in Endpoint.query.order_by(Endpoint.name).all()
    ]

    if form.validate_on_submit():
        # Determine the order for the new step
        last_step = db.session.query(APIChainStep).filter_by(
            chain_id=chain.id).order_by(APIChainStep.step_order.desc()).first()
        new_order = (last_step.step_order + 1) if last_step else 0

        # Validate the data_extraction_rules as JSON
        rules_json = None
        rules_str = form.data_extraction_rules.data.strip()
        if rules_str:
            try:
                rules_json = json.loads(rules_str)
                if not isinstance(rules_json, list):
                    raise ValueError(
                        "Data extraction rules must be a JSON array.")
            except (json.JSONDecodeError, ValueError) as e:
                flash(f"Invalid JSON for Data Extraction Rules: {e}", "error")
                return redirect(url_for('.view_chain', chain_id=chain.id))

        new_step = APIChainStep(
            chain_id=chain.id,
            endpoint_id=form.endpoint.data,
            step_order=new_order,
            name=form.name.data,
            data_extraction_rules=rules_json
        )
        db.session.add(new_step)
        db.session.commit()
        flash("New step added to the chain successfully!", "success")
    else:
        # Handle form validation errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(
                    f"Error in {getattr(form, field).label.text}: {error}", "error")

    return redirect(url_for('.view_chain', chain_id=chain.id))

@chains_bp.route('/<int:chain_id>/steps/<int:step_id>/delete', methods=['POST'])
@login_required
def delete_step(chain_id, step_id):
    """
    Deletes a step from a chain and re-orders the remaining steps.
    """
    chain = APIChain.query.filter_by(id=chain_id, user_id=current_user.id).first_or_404()
    step_to_delete = APIChainStep.query.filter_by(id=step_id, chain_id=chain.id).first_or_404()

    db.session.delete(step_to_delete)
    db.session.commit()

    # After deletion, re-order the remaining steps to ensure the sequence is always contiguous.
    remaining_steps = APIChainStep.query.filter_by(
        chain_id=chain.id
    ).order_by(APIChainStep.step_order).all()

    for index, step in enumerate(remaining_steps):
        step.step_order = index

    db.session.commit()

    flash('Step deleted successfully.', 'success')
    return redirect(url_for('chains_bp.view_chain', chain_id=chain_id))

@chains_bp.route('/<int:chain_id>/steps/<int:step_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_step(chain_id, step_id):
    """
    Handles editing an existing step in a chain.
    """
    chain = APIChain.query.filter_by(id=chain_id, user_id=current_user.id).first_or_404()
    step = APIChainStep.query.filter_by(id=step_id, chain_id=chain.id).first_or_404()

    # We reuse the same form as the "Add Step" feature
    form = ChainStepForm(obj=step) # Pass the step object to pre-populate the form

    # Populate the endpoint choices, setting the current one as the default
    form.endpoint.choices = [
        (e.id, f"{e.name} ({e.method})") 
        for e in Endpoint.query.order_by(Endpoint.name).all()
    ]
    
    if request.method == 'GET':
        # Pre-populate the form fields with the step's current data
        form.endpoint.data = step.endpoint_id
        form.name.data = step.name
        # Pretty-print the JSON for easier editing in the textarea
        if step.data_extraction_rules:
            form.data_extraction_rules.data = json.dumps(step.data_extraction_rules, indent=2)

    if form.validate_on_submit():
        # Validate and update the step with the submitted form data
        rules_json = None
        rules_str = form.data_extraction_rules.data.strip()
        if rules_str:
            try:
                rules_json = json.loads(rules_str)
                if not isinstance(rules_json, list):
                    raise ValueError("Data extraction rules must be a JSON array.")
            except (json.JSONDecodeError, ValueError) as e:
                flash(f"Invalid JSON for Data Extraction Rules: {e}", "error")
                return render_template('chains/edit_step.html', form=form, chain=chain, step=step, title="Edit Step")

        # Update the step object with new values
        step.endpoint_id = form.endpoint.data
        step.name = form.name.data
        step.data_extraction_rules = rules_json
        
        db.session.commit()
        flash(f"Step {step.step_order} updated successfully!", "success")
        return redirect(url_for('chains_bp.view_chain', chain_id=chain.id))

    return render_template('chains/edit_step.html', form=form, chain=chain, step=step, title="Edit Step")
