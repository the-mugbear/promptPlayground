import json
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from extensions import db
from models import Endpoint, EndpointHeader, PayloadTemplate # Import the new model
from forms import EndpointForm 
from services.common.header_parser_service import parse_raw_headers

from . import endpoints_bp

@endpoints_bp.route('/')
@login_required
def list_endpoints():
    """Renders the page that lists all configured Endpoints."""
    endpoints = Endpoint.query.filter_by(user_id=current_user.id).order_by(Endpoint.name).all()
    return render_template('endpoints/list_endpoints.html', endpoints=endpoints, title="Endpoints")

@endpoints_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_endpoint():
    """Handles both displaying the form for and processing the creation of a new Endpoint."""
    form = EndpointForm()
    # The QuerySelectField in the form handles populating its own choices.
    
    if form.validate_on_submit():
        # Handle payload template creation based on user selection
        payload_template = None
        
        if form.payload_option.data == 'existing':
            payload_template = form.payload_template.data
        elif form.payload_option.data == 'new':
            # Create a new payload template
            new_payload_template = PayloadTemplate(
                user_id=current_user.id,
                name=form.new_template_name.data,
                description=form.new_template_description.data or '',
                template=form.new_template_content.data
            )
            db.session.add(new_payload_template)
            db.session.flush()  # Get the ID without committing
            payload_template = new_payload_template
            
            flash(f'New payload template "{new_payload_template.name}" created successfully!', 'success')
        # If payload_option is 'none', payload_template remains None
        
        # Create a new Endpoint object from the validated form data
        new_endpoint = Endpoint(
            user_id=current_user.id,
            name=form.name.data,
            description=form.description.data,
            base_url=form.base_url.data,
            path=form.path.data,
            method=form.method.data,
            payload_template=payload_template,
            auth_method=form.auth_method.data,
            # NOTE: In a production app, you would encrypt this value before saving.
            credentials_encrypted=form.credentials_encrypted.data,
            timeout_seconds=form.timeout_seconds.data,
            retry_attempts=form.retry_attempts.data
        )
        db.session.add(new_endpoint)
        db.session.commit()

        if form.raw_headers.data:
            parsed_headers = parse_raw_headers(form.raw_headers.data)
            for key, value in parsed_headers.items():
                header = EndpointHeader(endpoint_id=new_endpoint.id, key=key, value=value)
                db.session.add(header)
            db.session.commit() 

        flash(f'Endpoint "{new_endpoint.name}" created successfully!', 'success')
        return redirect(url_for('endpoints_bp.edit_endpoint', endpoint_id=new_endpoint.id))

    return render_template('endpoints/create_endpoint.html', form=form, title="Create New Endpoint")


@endpoints_bp.route('/<int:endpoint_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_endpoint(endpoint_id):
    """Handles both displaying and processing edits for an existing Endpoint."""
    endpoint = db.session.get(Endpoint, endpoint_id)
    if not endpoint or endpoint.user_id != current_user.id:
        abort(404)

    # Pass the existing endpoint object to the form to pre-populate it
    form = EndpointForm(obj=endpoint)

    if form.validate_on_submit():
        # Instead of creating a new object, we update the existing one
        endpoint.name = form.name.data
        endpoint.description = form.description.data
        endpoint.base_url = form.base_url.data
        endpoint.path = form.path.data
        endpoint.method = form.method.data
        endpoint.payload_template = form.payload_template.data
        endpoint.auth_method = form.auth_method.data
        if form.credentials_encrypted.data: # Only update credentials if a new value is provided
             endpoint.credentials_encrypted = form.credentials_encrypted.data
        endpoint.timeout_seconds = form.timeout_seconds.data
        endpoint.retry_attempts = form.retry_attempts.data

        # First, remove all existing headers to start fresh
        EndpointHeader.query.filter_by(endpoint_id=endpoint.id).delete()
        # Then, add the new ones from the form
        if form.raw_headers.data:
            parsed_headers = parse_raw_headers(form.raw_headers.data)
            for key, value in parsed_headers.items():
                new_header = EndpointHeader(endpoint_id=endpoint.id, key=key, value=value)
                db.session.add(new_header)
        
        db.session.commit()
        flash(f'Endpoint "{endpoint.name}" updated successfully!', 'success')
        return redirect(url_for('endpoints_bp.edit_endpoint', endpoint_id=endpoint.id))
        
    # For a GET request, pre-populate the credentials field with a placeholder
    # so the encrypted value is not exposed in the HTML.
    if request.method == 'GET' and endpoint.credentials_encrypted:
        form.credentials_encrypted.data = "********"

    if request.method == 'GET':
        # ... (code to populate other fields) ...
        # --- ADD THIS LINE TO POPULATE HEADERS ---
        endpoint_headers = {h.key: h.value for h in endpoint.headers}
        form.raw_headers.data = "\n".join(f"{k}: {v}" for k, v in endpoint_headers.items())

    # Check for dependencies when showing the edit form
    from models.model_TestRun import TestRun
    from models.model_APIChain import APIChainStep
    
    dependent_test_runs = TestRun.query.filter_by(endpoint_id=endpoint_id).all()
    dependent_chain_steps = APIChainStep.query.filter_by(endpoint_id=endpoint_id).all()
    
    return render_template(
        'endpoints/edit_endpoint.html', 
        form=form, 
        endpoint=endpoint, 
        dependent_test_runs=dependent_test_runs,
        dependent_chain_steps=dependent_chain_steps,
        title="Edit Endpoint"
    )


@endpoints_bp.route('/<int:endpoint_id>/delete', methods=['POST'])
@login_required
def delete_endpoint(endpoint_id):
    """Deletes an endpoint after checking for dependencies."""
    endpoint = db.session.get(Endpoint, endpoint_id)
    if not endpoint or endpoint.user_id != current_user.id:
        flash('Endpoint not found or you do not have permission to delete it.', 'danger')
        return redirect(url_for('endpoints_bp.list_endpoints'))
    
    # Check for dependent test runs
    from models.model_TestRun import TestRun
    dependent_test_runs = TestRun.query.filter_by(endpoint_id=endpoint_id).count()
    
    # Check for dependent chain steps
    from models.model_APIChain import APIChainStep
    dependent_chain_steps = APIChainStep.query.filter_by(endpoint_id=endpoint_id).count()
    
    force_delete = request.form.get('force_delete') == 'true'
    
    if (dependent_test_runs > 0 or dependent_chain_steps > 0) and not force_delete:
        # Show warning instead of deleting
        dependencies = []
        if dependent_test_runs > 0:
            dependencies.append(f"{dependent_test_runs} test run(s)")
        if dependent_chain_steps > 0:
            dependencies.append(f"{dependent_chain_steps} chain step(s)")
        
        dependency_text = " and ".join(dependencies)
        flash(
            f'Cannot delete endpoint "{endpoint.name}" because it is used by {dependency_text}. '
            f'Please delete or update these dependencies first, or use force delete to remove the endpoint anyway '
            f'(this will leave orphaned records).', 
            'warning'
        )
        return redirect(url_for('endpoints_bp.edit_endpoint', endpoint_id=endpoint_id))
    
    try:
        if force_delete:
            # Set dependent test runs to NULL (orphan them but don't delete)
            TestRun.query.filter_by(endpoint_id=endpoint_id).update({'endpoint_id': None})
            
            # Set dependent chain steps to NULL (orphan them but don't delete)
            APIChainStep.query.filter_by(endpoint_id=endpoint_id).update({'endpoint_id': None})
        
        db.session.delete(endpoint)
        db.session.commit()
        
        if force_delete and (dependent_test_runs > 0 or dependent_chain_steps > 0):
            flash(
                f'Endpoint "{endpoint.name}" has been deleted. Note: {dependent_test_runs} test run(s) and '
                f'{dependent_chain_steps} chain step(s) are now orphaned and may need attention.', 
                'warning'
            )
        else:
            flash(f'Endpoint "{endpoint.name}" has been deleted.', 'success')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting endpoint: {str(e)}', 'danger')
    
    return redirect(url_for('endpoints_bp.list_endpoints'))