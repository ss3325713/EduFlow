import os
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.assignments import assignments_bp
from app.extensions import db
from app.models import Homework, Class, Batch, Subject, Teacher
from app.utils.decorators import teacher_required

@assignments_bp.route('/')
@login_required
def index():
    if current_user.is_student() and current_user.student_profile:
        homework_list = Homework.query.filter_by(batch_id=current_user.student_profile.batch_id).order_by(Homework.due_date.desc()).all()
    elif current_user.is_parent() and current_user.parent_profile:
        linked_batch_ids = [st.batch_id for st in current_user.parent_profile.linked_students if st.batch_id]
        homework_list = Homework.query.filter(Homework.batch_id.in_(linked_batch_ids)).order_by(Homework.due_date.desc()).all()
    else:
        homework_list = Homework.query.order_by(Homework.due_date.desc()).all()

    return render_template('assignments/index.html', homework_list=homework_list)

@assignments_bp.route('/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add():
    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()
    subjects = Subject.query.order_by(Subject.name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        class_id = request.form.get('class_id', type=int)
        batch_id = request.form.get('batch_id', type=int)
        subject_id = request.form.get('subject_id', type=int)
        due_date_str = request.form.get('due_date')

        batch = Batch.query.get(batch_id)
        subject = Subject.query.get(subject_id)

        if batch and batch.class_id != class_id:
            flash('Selected batch does not belong to the selected class.', 'danger')
            return render_template('assignments/form.html', classes=classes, batches=batches, subjects=subjects)

        if subject and subject.class_id != class_id:
            flash('Selected subject does not belong to the selected class.', 'danger')
            return render_template('assignments/form.html', classes=classes, batches=batches, subjects=subjects)

        teacher = current_user.teacher_profile
        teacher_id = teacher.id if teacher else 1

        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()

        filename = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename != '':
                sec_name = secure_filename(file.filename)
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                filename = f"hw_{timestamp}_{sec_name}"
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(upload_path)

        hw = Homework(
            title=title,
            description=description,
            class_id=class_id,
            batch_id=batch_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            issue_date=datetime.utcnow().date(),
            due_date=due_date,
            attachment_filename=filename
        )
        db.session.add(hw)
        db.session.commit()

        flash(f'Homework assignment "{hw.title}" issued successfully.', 'success')
        return redirect(url_for('assignments.index'))

    return render_template('assignments/form.html', classes=classes, batches=batches, subjects=subjects)

@assignments_bp.route('/download/<filename>')
@login_required
def download(filename):
    hw = Homework.query.filter_by(attachment_filename=filename).first_or_404()

    if current_user.is_student() and current_user.student_profile:
        if hw.batch_id != current_user.student_profile.batch_id:
            flash('You do not have access to homework attachments from other batches.', 'danger')
            return redirect(url_for('assignments.index'))

    if current_user.is_parent() and current_user.parent_profile:
        linked_batch_ids = [st.batch_id for st in current_user.parent_profile.linked_students if st.batch_id]
        if hw.batch_id not in linked_batch_ids:
            flash('Access denied.', 'danger')
            return redirect(url_for('assignments.index'))

    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
