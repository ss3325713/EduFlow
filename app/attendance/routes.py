from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.attendance import attendance_bp
from app.extensions import db
from app.models import Attendance, AttendanceStatus, Batch, Student, Class, Teacher
from app.utils.decorators import teacher_required
from app.services.audit_service import log_action

@attendance_bp.route('/', methods=['GET', 'POST'])
@login_required
@teacher_required
def mark():
    batches = Batch.query.filter_by(status='active').all()
    
    batch_id = request.args.get('batch_id', type=int) or (batches[0].id if batches else None)
    date_str = request.args.get('date') or datetime.utcnow().strftime('%Y-%m-%d')
    att_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    selected_batch = Batch.query.get(batch_id) if batch_id else None
    students = Student.query.filter_by(batch_id=batch_id, status='active').all() if selected_batch else []

    # Check existing attendance records for selected batch & date
    existing_records = {}
    if selected_batch:
        records = Attendance.query.filter_by(batch_id=batch_id, date=att_date).all()
        existing_records = {r.student_id: r for r in records}

    if request.method == 'POST':
        teacher_id = current_user.teacher_profile.id if current_user.teacher_profile else None
        count_marked = 0

        for student in students:
            status_val = request.form.get(f'status_{student.id}', AttendanceStatus.PRESENT)
            remarks = request.form.get(f'remarks_{student.id}', '').strip()

            record = existing_records.get(student.id)
            if record:
                record.status = status_val
                record.remarks = remarks
                record.marked_by_teacher_id = teacher_id
            else:
                record = Attendance(
                    student_id=student.id,
                    batch_id=selected_batch.id,
                    date=att_date,
                    status=status_val,
                    marked_by_teacher_id=teacher_id,
                    remarks=remarks
                )
                db.session.add(record)
            count_marked += 1

        db.session.commit()
        log_action('ATTENDANCE_MARKED', target_type='Batch', target_id=selected_batch.id, details=f"Marked attendance for {count_marked} students in Batch '{selected_batch.name}' on {att_date}")
        flash(f'Attendance recorded successfully for Batch "{selected_batch.name}" ({att_date}).', 'success')
        return redirect(url_for('attendance.mark', batch_id=batch_id, date=date_str))

    return render_template('attendance/mark.html',
                           batches=batches,
                           selected_batch=selected_batch,
                           att_date=att_date,
                           date_str=date_str,
                           students=students,
                           existing_records=existing_records,
                           statuses=AttendanceStatus.CHOICES)

@attendance_bp.route('/report')
@login_required
def report():
    batches = Batch.query.filter_by(status='active').all()
    batch_id = request.args.get('batch_id', type=int)

    selected_batch = Batch.query.get(batch_id) if batch_id else (batches[0] if batches else None)

    if current_user.is_student():
        students = [current_user.student_profile] if current_user.student_profile else []
    elif current_user.is_parent():
        parent = current_user.parent_profile
        students = [link.student for link in parent.student_links.all()] if parent else []
    else:
        students = Student.query.filter_by(batch_id=selected_batch.id).all() if selected_batch else []

    student_stats = []
    for s in students:
        if not s:
            continue
        total = Attendance.query.filter_by(student_id=s.id).count()
        present = Attendance.query.filter_by(student_id=s.id, status='present').count()
        absent = Attendance.query.filter_by(student_id=s.id, status='absent').count()
        late = Attendance.query.filter_by(student_id=s.id, status='late').count()
        excused = Attendance.query.filter_by(student_id=s.id, status='excused').count()
        pct = round(((present + late) / total * 100), 1) if total > 0 else 100.0

        student_stats.append({
            'student': s,
            'total': total,
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'percentage': pct
        })

    return render_template('attendance/report.html',
                           batches=batches,
                           selected_batch=selected_batch,
                           student_stats=student_stats)
