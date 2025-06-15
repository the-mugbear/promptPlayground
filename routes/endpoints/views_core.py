import json
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from extensions import db
from models import Endpoint, EndpointHeader, PayloadTemplate # Import the new model
from forms import EndpointForm # Import our new, powerful form

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
        # Create a new Endpoint object from the validated form data
        new_endpoint = Endpoint(
            user_id=current_user.id,
            name=form.name.data,
            description=form.description.data,
            base_url=form.base_url.data,
            path=form.path.data,
            method=form.method.data,
            payload_template=form.payload_template.data, # The form gives us the full object
            auth_method=form.auth_method.data,
            # NOTE: In a production app, you would encrypt this value before saving.
            credentials_encrypted=form.credentials_encrypted.data,
            timeout_seconds=form.timeout_seconds.data,
            retry_attempts=form.retry_attempts.data,
            purpose=form.purpose.data
        )
        db.session.add(new_endpoint)
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
        endpoint.purpose = form.purpose.data
        
        db.session.commit()
        flash(f'Endpoint "{endpoint.name}" updated successfully!', 'success')
        return redirect(url_for('endpoints_bp.edit_endpoint', endpoint_id=endpoint.id))
        
    # For a GET request, pre-populate the credentials field with a placeholder
    # so the encrypted value is not exposed in the HTML.
    if request.method == 'GET' and endpoint.credentials_encrypted:
        form.credentials_encrypted.data = "********"

    return render_template('endpoints/edit_endpoint.html', form=form, endpoint=endpoint, title="Edit Endpoint")


@endpoints_bp.route('/<int:endpoint_id>/delete', methods=['POST'])
@login_required
def delete_endpoint(endpoint_id):
    """Deletes an endpoint."""
    endpoint = db.session.get(Endpoint, endpoint_id)
    if endpoint and endpoint.user_id == current_user.id:
        db.session.delete(endpoint)
        db.session.commit()
        flash(f'Endpoint "{endpoint.name}" has been deleted.', 'success')
    else:
        flash('Endpoint not found or you do not have permission to delete it.', 'danger')
    return redirect(url_for('endpoints_bp.list_endpoints'))