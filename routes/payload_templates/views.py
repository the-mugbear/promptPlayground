from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from forms import PayloadTemplateForm
from models import db, PayloadTemplate
from . import payload_templates_bp

@payload_templates_bp.route('/')
@login_required
def list_templates():
    """Renders the page that lists all Payload Templates."""
    templates = PayloadTemplate.query.filter_by(user_id=current_user.id).order_by(PayloadTemplate.name).all()
    return render_template('payload_templates/list_templates.html', templates=templates, title="Payload Templates")

@payload_templates_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_template():
    """Handles the creation of a new Payload Template."""
    form = PayloadTemplateForm()
    if form.validate_on_submit():
        new_template = PayloadTemplate(
            name=form.name.data,
            description=form.description.data,
            template=form.template.data,
            user_id=current_user.id
        )
        db.session.add(new_template)
        db.session.commit()
        flash(f'Successfully created new template: "{new_template.name}"', 'success')
        return redirect(url_for('payload_templates_bp.list_templates'))
        
    return render_template('payload_templates/create_template.html', form=form, title="Create New Payload Template")

@payload_templates_bp.route('/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    """Handles editing an existing Payload Template."""
    template = db.session.get(PayloadTemplate, template_id)
    if not template or template.user_id != current_user.id:
        flash("Payload Template not found or you don't have permission to edit it.", "danger")
        return redirect(url_for('payload_templates_bp.list_templates'))

    form = PayloadTemplateForm(obj=template)
    if form.validate_on_submit():
        template.name = form.name.data
        template.description = form.description.data
        template.template = form.template.data
        db.session.commit()
        flash(f'Template "{template.name}" updated successfully!', 'success')
        return redirect(url_for('payload_templates_bp.list_templates'))

    return render_template('payload_templates/edit_template.html', form=form, template=template, title="Edit Payload Template")