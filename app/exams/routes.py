from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.exams import exams_bp
from app.extensions import db
from app.models import Exam, Mark, Class, Batch, Subject, Student, InstituteSettings
from app.utils.decorators import teacher_required
from app.services.audit_service import log_action

@exams_bp.route('/')
@login_required
def index():
    exams = Exam.query.order_by(Exam.exam_date.desc()).all()
    return render_template('exams/index.html', exams=exams)

@exams_bp.route('/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add():
    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        exam_type = request.form.get('exam_type', 'unit_test')
        class_id = request.form.get('class_id', type=int)
        batch_id = request.form.get('batch_id', type=int)
        exam_date_str = request.form.get('exam_date')
        max_marks = request.form.get('max_marks', type=float, default=100.0)

        exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()

        exam = Exam(
            title=title,
            exam_type=exam_type,
            class_id=class_id,
            batch_id=batch_id,
            exam_date=exam_date,
            max_marks=max_marks
        )
        db.session.add(exam)
        db.session.commit()

        log_action('EXAM_CREATED', target_type='Exam', target_id=exam.id, details=f"Created exam '{exam.title}'")
        flash(f'Examination "{exam.title}" created successfully.', 'success')
        return redirect(url_for('exams.marks_entry', exam_id=exam.id))

    return render_template('exams/form.html', classes=classes, batches=batches)

@exams_bp.route('/<int:exam_id>/marks', methods=['GET', 'POST'])
@login_required
@teacher_required
def marks_entry(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    subjects = Subject.query.filter_by(class_id=exam.class_id).all()
    subject_id = request.args.get('subject_id', type=int) or (subjects[0].id if subjects else None)

    selected_subject = Subject.query.get(subject_id) if subject_id else None
    students = Student.query.filter_by(batch_id=exam.batch_id, status='active').all()

    existing_records = {}
    if selected_subject:
        records = Mark.query.filter_by(exam_id=exam.id, subject_id=selected_subject.id).all()
        existing_records = {r.student_id: r for r in records}

    if request.method == 'POST':
        for student in students:
            marks_val = request.form.get(f'marks_{student.id}', type=float, default=0.0)
            remarks = request.form.get(f'remarks_{student.id}', '').strip()

            record = existing_records.get(student.id)
            if record:
                record.marks_obtained = marks_val
                record.remarks = remarks
                record.entered_by_user_id = current_user.id
                record.calculate_grade()
            else:
                record = Mark(
                    exam_id=exam.id,
                    subject_id=selected_subject.id,
                    student_id=student.id,
                    marks_obtained=marks_val,
                    max_marks=exam.max_marks,
                    remarks=remarks,
                    entered_by_user_id=current_user.id
                )
                record.calculate_grade()
                db.session.add(record)

        db.session.commit()
        log_action('MARKS_UPDATED', target_type='Exam', target_id=exam.id, details=f"Updated marks for Exam '{exam.title}' - Subject '{selected_subject.name}'")
        flash(f'Marks recorded successfully for subject "{selected_subject.name}".', 'success')
        return redirect(url_for('exams.marks_entry', exam_id=exam.id, subject_id=subject_id))

    return render_template('exams/marks_entry.html',
                           exam=exam,
                           subjects=subjects,
                           selected_subject=selected_subject,
                           students=students,
                           existing_marks=existing_records)

@exams_bp.route('/<int:exam_id>/reports')
@login_required
def reports_list(exam_id):
    exam = Exam.query.get_or_404(exam_id)

    # Security check: Students MUST NOT see batch-wide report lists of all students
    if current_user.is_student() and current_user.student_profile:
        if exam.batch_id != current_user.student_profile.batch_id:
            flash('You do not have access to examinations for other batches.', 'danger')
            return redirect(url_for('exams.index'))
        return redirect(url_for('exams.student_report', exam_id=exam.id, student_id=current_user.student_profile.id))

    # Security check: Parents should only see reports of their linked children
    if current_user.is_parent() and current_user.parent_profile:
        linked_students = [st for st in current_user.parent_profile.linked_students if st.batch_id == exam.batch_id]
        if not linked_students:
            flash('None of your linked children are enrolled in this examination batch.', 'danger')
            return redirect(url_for('exams.index'))
        if len(linked_students) == 1:
            return redirect(url_for('exams.student_report', exam_id=exam.id, student_id=linked_students[0].id))
        students = linked_students
    else:
        students = Student.query.filter_by(batch_id=exam.batch_id).all()

    all_marks = Mark.query.filter_by(exam_id=exam.id).all()

    student_scores = {}
    for student in students:
        s_marks = [m for m in all_marks if m.student_id == student.id]
        total_obtained = sum(m.marks_obtained for m in s_marks)
        total_max = sum(m.max_marks for m in s_marks) if s_marks else (exam.max_marks or 100.0)
        pct = round((total_obtained / total_max) * 100, 1) if total_max > 0 else 0.0
        
        if pct >= 90: grade = 'A+'
        elif pct >= 80: grade = 'A'
        elif pct >= 70: grade = 'B'
        elif pct >= 60: grade = 'C'
        elif pct >= 50: grade = 'D'
        else: grade = 'F'

        student_scores[student.id] = {
            'total_obtained': total_obtained,
            'total_max': total_max,
            'percentage': pct,
            'grade': grade,
            'subject_count': len(s_marks)
        }

    sorted_students = sorted(students, key=lambda s: student_scores[s.id]['total_obtained'], reverse=True)
    rank_map = {s.id: idx + 1 for idx, s in enumerate(sorted_students)}

    for s in students:
        student_scores[s.id]['rank'] = rank_map.get(s.id, 1)

    return render_template('exams/reports_list.html',
                           exam=exam,
                           students=students,
                           student_scores=student_scores)

@exams_bp.route('/<int:exam_id>/student/<int:student_id>/report')
@login_required
def student_report(exam_id, student_id):
    from app.models import User
    exam = Exam.query.get_or_404(exam_id)
    student = Student.query.get_or_404(student_id)
    settings = InstituteSettings.get_settings()

    if current_user.is_student() and (not current_user.student_profile or current_user.student_profile.id != student.id):
        flash('You can only view your own exam performance reports.', 'danger')
        return redirect(url_for('dashboard.index'))

    if current_user.is_parent():
        parent_profile = current_user.parent_profile
        linked_ids = [link.student_id for link in parent_profile.student_links.all()] if parent_profile else []
        if student.id not in linked_ids:
            flash('You can only view reports for your linked children.', 'danger')
            return redirect(url_for('dashboard.index'))

    subjects = Subject.query.filter_by(class_id=exam.class_id).order_by(Subject.name).all()
    all_batch_marks = Mark.query.filter_by(exam_id=exam.id).all()

    subject_reports = []
    total_obtained = 0.0
    total_max = 0.0

    for sub in subjects:
        sub_marks = [m for m in all_batch_marks if m.subject_id == sub.id]
        student_mark = next((m for m in sub_marks if m.student_id == student.id), None)
        
        marks_obtained = student_mark.marks_obtained if student_mark else 0.0
        max_marks = student_mark.max_marks if student_mark else (exam.max_marks or 100.0)
        grade = student_mark.grade if student_mark else 'N/A'
        remarks = student_mark.remarks if student_mark and student_mark.remarks else 'Consistent effort required.'

        obtained_list = [m.marks_obtained for m in sub_marks] if sub_marks else [0.0]
        class_highest = round(max(obtained_list), 1) if obtained_list else 0.0
        class_average = round(sum(obtained_list) / len(obtained_list), 1) if obtained_list else 0.0

        pct = round((marks_obtained / max_marks) * 100, 1) if max_marks > 0 else 0.0

        subject_reports.append({
            'subject_id': sub.id,
            'subject_name': sub.name,
            'subject_code': sub.code,
            'marks_obtained': marks_obtained,
            'max_marks': max_marks,
            'percentage': pct,
            'grade': grade,
            'class_highest': class_highest,
            'class_average': class_average,
            'remarks': remarks
        })

        total_obtained += marks_obtained
        total_max += max_marks

    overall_pct = round((total_obtained / total_max) * 100, 1) if total_max > 0 else 0.0

    if overall_pct >= 90: overall_grade = 'A+'
    elif overall_pct >= 80: overall_grade = 'A'
    elif overall_pct >= 70: overall_grade = 'B'
    elif overall_pct >= 60: overall_grade = 'C'
    elif overall_pct >= 50: overall_grade = 'D'
    else: overall_grade = 'F'

    batch_students = Student.query.filter_by(batch_id=exam.batch_id).all()
    batch_totals = {}
    for st in batch_students:
        s_obtained = sum(m.marks_obtained for m in all_batch_marks if m.student_id == st.id)
        batch_totals[st.id] = s_obtained

    sorted_batch = sorted(batch_students, key=lambda st: batch_totals.get(st.id, 0.0), reverse=True)
    class_rank = next((idx + 1 for idx, st in enumerate(sorted_batch) if st.id == student.id), 1)
    total_students = len(batch_students)

    teacher_notes = []
    if overall_pct >= 85:
        teacher_notes.append(f"Outstanding academic performance! {student.user.first_name} has demonstrated excellent conceptual clarity and dedication.")
    elif overall_pct >= 70:
        teacher_notes.append(f"Good academic progress. {student.user.first_name} performs well and shows consistent participation in class.")
    else:
        teacher_notes.append(f"Needs focused improvement in core subjects. Additional revision and faculty guidance are recommended.")

    top_subs = [sr['subject_name'] for sr in subject_reports if sr['marks_obtained'] >= sr['class_highest'] and sr['marks_obtained'] > 0]
    if top_subs:
        teacher_notes.append(f"Special Achievement: Highest score achieved in batch for {', '.join(top_subs)}.")

    return render_template('exams/student_report.html',
                           settings=settings,
                           exam=exam,
                           student=student,
                           subject_reports=subject_reports,
                           total_obtained=total_obtained,
                           total_max=total_max,
                           overall_pct=overall_pct,
                           overall_grade=overall_grade,
                           class_rank=class_rank,
                           total_students=total_students,
                           teacher_notes=' '.join(teacher_notes))
