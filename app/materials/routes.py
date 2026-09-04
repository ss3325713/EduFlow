import os
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.materials import materials_bp
from app.extensions import db
from app.models import StudyMaterial, Class, Batch, Subject, Teacher
from app.utils.decorators import teacher_required

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@materials_bp.route('/')
@login_required
def index():
    if current_user.is_student() and current_user.student_profile:
        materials = StudyMaterial.query.filter_by(batch_id=current_user.student_profile.batch_id).order_by(StudyMaterial.upload_date.desc()).all()
    elif current_user.is_parent() and current_user.parent_profile:
        linked_batch_ids = [st.batch_id for st in current_user.parent_profile.linked_students if st.batch_id]
        materials = StudyMaterial.query.filter(StudyMaterial.batch_id.in_(linked_batch_ids)).order_by(StudyMaterial.upload_date.desc()).all()
    else:
        materials = StudyMaterial.query.order_by(StudyMaterial.upload_date.desc()).all()

    return render_template('materials/index.html', materials=materials)

@materials_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@teacher_required
def upload():
    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()
    subjects = Subject.query.order_by(Subject.name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        class_id = request.form.get('class_id', type=int)
        batch_id = request.form.get('batch_id', type=int)
        subject_id = request.form.get('subject_id', type=int)

        batch = Batch.query.get(batch_id)
        subject = Subject.query.get(subject_id)

        if batch and batch.class_id != class_id:
            flash('Selected batch does not belong to the selected class.', 'danger')
            return render_template('materials/upload.html', classes=classes, batches=batches, subjects=subjects)

        if subject and subject.class_id != class_id:
            flash('Selected subject does not belong to the selected class.', 'danger')
            return render_template('materials/upload.html', classes=classes, batches=batches, subjects=subjects)

        if 'file' not in request.files:
            flash('No file selected.', 'danger')
            return render_template('materials/upload.html', classes=classes, batches=batches, subjects=subjects)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return render_template('materials/upload.html', classes=classes, batches=batches, subjects=subjects)

        if not allowed_file(file.filename):
            flash('File type not allowed. Please upload PDF, Word document, or image file.', 'danger')
            return render_template('materials/upload.html', classes=classes, batches=batches, subjects=subjects)

        sec_name = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        save_filename = f"mat_{timestamp}_{sec_name}"
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], save_filename)
        
        file.save(upload_path)
        file_size = os.path.getsize(upload_path)
        ext = sec_name.rsplit('.', 1)[1].lower() if '.' in sec_name else 'file'

        teacher = current_user.teacher_profile
        teacher_id = teacher.id if teacher else 1

        material = StudyMaterial(
            title=title,
            description=description,
            class_id=class_id,
            batch_id=batch_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            file_path=save_filename,
            file_type=ext,
            file_size=file_size,
            upload_date=datetime.utcnow()
        )
        db.session.add(material)
        db.session.commit()

        flash(f'Study Material "{material.title}" uploaded successfully.', 'success')
        return redirect(url_for('materials.index'))

    return render_template('materials/upload.html', classes=classes, batches=batches, subjects=subjects)

@materials_bp.route('/download/<int:material_id>')
@login_required
def download(material_id):
    material = StudyMaterial.query.get_or_404(material_id)

    if current_user.is_student() and current_user.student_profile:
        if material.batch_id != current_user.student_profile.batch_id:
            flash('You do not have access to study materials from other batches.', 'danger')
            return redirect(url_for('materials.index'))

    if current_user.is_parent() and current_user.parent_profile:
        linked_batch_ids = [st.batch_id for st in current_user.parent_profile.linked_students if st.batch_id]
        if material.batch_id not in linked_batch_ids:
            flash('Access denied.', 'danger')
            return redirect(url_for('materials.index'))

    return send_from_directory(current_app.config['UPLOAD_FOLDER'], material.file_path, as_attachment=True)
