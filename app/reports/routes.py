import csv
import io
from flask import render_template, request, Response, make_response
from flask_login import login_required
from sqlalchemy import func
from app.reports import reports_bp
from app.extensions import db
from app.models import FeePayment, StudentFee, Student, Teacher, Batch, Attendance, Mark
from app.utils.decorators import admin_required

@reports_bp.route('/')
@login_required
@admin_required
def index():
    report_type = request.args.get('type', 'financial')
    export = request.args.get('export')

    if report_type == 'financial':
        payments = FeePayment.query.filter_by(status='valid').order_by(FeePayment.payment_date.desc()).all()
        total_collected = sum(p.amount_paid for p in payments)
        
        if export == 'csv':
            si = io.StringIO()
            cw = csv.writer(si)
            cw.writerow(['Receipt No', 'Student Code', 'Student Name', 'Amount Paid', 'Payment Method', 'Date'])
            for p in payments:
                student = p.student_fee.student if p.student_fee else None
                cw.writerow([
                    p.receipt_number,
                    student.student_code if student else '',
                    student.full_name if student else '',
                    p.amount_paid,
                    p.payment_method,
                    p.payment_date.strftime('%Y-%m-%d %H:%M')
                ])
            response = make_response(si.getvalue())
            response.headers['Content-Disposition'] = 'attachment; filename=financial_report.csv'
            response.headers['Content-type'] = 'text/csv'
            return response

        return render_template('reports/financial.html', payments=payments, total_collected=total_collected)

    elif report_type == 'attendance':
        batches = Batch.query.all()
        batch_stats = []
        for b in batches:
            total_students = b.students.count()
            att_records = Attendance.query.filter_by(batch_id=b.id).all()
            total_att = len(att_records)
            present_cnt = sum(1 for r in att_records if r.status in ['present', 'late'])
            pct = round((present_cnt / total_att * 100), 1) if total_att > 0 else 100.0
            batch_stats.append({
                'batch': b,
                'student_count': total_students,
                'attendance_percentage': pct
            })

        if export == 'csv':
            si = io.StringIO()
            cw = csv.writer(si)
            cw.writerow(['Batch Name', 'Class', 'Student Count', 'Attendance Percentage'])
            for stat in batch_stats:
                cw.writerow([
                    stat['batch'].name,
                    stat['batch'].academic_class.name if stat['batch'].academic_class else '',
                    stat['student_count'],
                    f"{stat['attendance_percentage']}%"
                ])
            response = make_response(si.getvalue())
            response.headers['Content-Disposition'] = 'attachment; filename=attendance_report.csv'
            response.headers['Content-type'] = 'text/csv'
            return response

        return render_template('reports/attendance.html', batch_stats=batch_stats)

    elif report_type == 'teacher_workload':
        teachers = Teacher.query.join(Teacher.user).all()
        workload = []
        for t in teachers:
            batches_count = len(set(a.batch_id for a in t.assignments))
            subjects_count = len(set(a.subject_id for a in t.assignments))
            workload.append({
                'teacher': t,
                'batches_count': batches_count,
                'subjects_count': subjects_count
            })

        return render_template('reports/teacher_workload.html', workload=workload)

    return render_template('reports/financial.html', payments=[], total_collected=0.0)
