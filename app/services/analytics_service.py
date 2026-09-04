from datetime import datetime, timedelta
from sqlalchemy import func, extract
from app.extensions import db
from app.models import (
    User, Role, Student, Teacher, Parent, Class, Batch, Subject,
    FeePayment, StudentFee, Attendance, Exam, Mark, Homework,
    StudyMaterial, Announcement, Timetable, TeacherAssignment
)

class AnalyticsService:

    @staticmethod
    def get_super_admin_stats():
        now = datetime.utcnow()
        today = now.date()

        total_students = Student.query.count()
        active_students = Student.query.filter_by(status='active').count()

        total_teachers = Teacher.query.count()
        active_teachers = Teacher.query.filter_by(employment_status='active').count()

        total_classes = Class.query.count()
        active_batches = Batch.query.filter_by(status='active').count()

        # Monthly Fee Collection (current month)
        first_day_month = today.replace(day=1)
        monthly_collection = db.session.query(
            func.coalesce(func.sum(FeePayment.amount_paid), 0.0)
        ).filter(
            FeePayment.payment_date >= first_day_month,
            FeePayment.status == 'valid'
        ).scalar()

        # Total Pending Fees
        pending_fees = db.session.query(
            func.coalesce(func.sum(StudentFee.total_payable - StudentFee.total_paid), 0.0)
        ).scalar()

        # Today's Attendance
        today_attendance = Attendance.query.filter_by(date=today).all()
        if today_attendance:
            present_cnt = sum(1 for a in today_attendance if a.status in ['present', 'late'])
            today_att_percentage = round((present_cnt / len(today_attendance)) * 100, 1)
        else:
            today_att_percentage = 0.0

        # Monthly Fee Collection Chart Data (Last 6 months)
        fee_chart_labels = []
        fee_chart_data = []
        for i in range(5, -1, -1):
            target_date = today - timedelta(days=i*30)
            month_start = target_date.replace(day=1)
            # Find last day of target_date month
            if target_date.month == 12:
                month_end = target_date.replace(day=31)
            else:
                month_end = (target_date.replace(month=target_date.month+1, day=1) - timedelta(days=1))
            
            total_in_month = db.session.query(
                func.coalesce(func.sum(FeePayment.amount_paid), 0.0)
            ).filter(
                FeePayment.payment_date >= month_start,
                FeePayment.payment_date <= datetime.combine(month_end, datetime.max.time()),
                FeePayment.status == 'valid'
            ).scalar()

            fee_chart_labels.append(month_start.strftime('%b %Y'))
            fee_chart_data.append(round(total_in_month, 2))

        # Batch-wise student distribution
        batches = Batch.query.filter_by(status='active').all()
        batch_labels = [b.name for b in batches]
        batch_student_counts = [b.students.count() for b in batches]

        # Recent activities
        recent_admissions = Student.query.order_by(Student.admission_date.desc()).limit(5).all()
        recent_payments = FeePayment.query.filter_by(status='valid').order_by(FeePayment.payment_date.desc()).limit(5).all()
        upcoming_exams = Exam.query.filter(Exam.exam_date >= today).order_by(Exam.exam_date.asc()).limit(5).all()
        recent_announcements = Announcement.query.order_by(Announcement.publish_date.desc()).limit(5).all()

        return {
            'total_students': total_students,
            'active_students': active_students,
            'total_teachers': total_teachers,
            'active_teachers': active_teachers,
            'total_classes': total_classes,
            'active_batches': active_batches,
            'monthly_collection': monthly_collection,
            'pending_fees': pending_fees,
            'today_att_percentage': today_att_percentage,
            'fee_chart_labels': fee_chart_labels,
            'fee_chart_data': fee_chart_data,
            'batch_labels': batch_labels,
            'batch_student_counts': batch_student_counts,
            'recent_admissions': recent_admissions,
            'recent_payments': recent_payments,
            'upcoming_exams': upcoming_exams,
            'recent_announcements': recent_announcements
        }

    @staticmethod
    def get_teacher_stats(teacher_id):
        teacher = Teacher.query.get(teacher_id)
        if not teacher:
            return {}

        assignments = teacher.assignments.all()
        batch_ids = list(set(a.batch_id for a in assignments))
        
        # Calculate unique students assigned to this teacher
        total_students = Student.query.filter(Student.batch_id.in_(batch_ids)).count() if batch_ids else 0

        # Pending homework (homework assigned by teacher with due_date >= today)
        today = datetime.utcnow().date()
        pending_homework = Homework.query.filter(
            Homework.teacher_id == teacher.id,
            Homework.due_date >= today
        ).count()

        # Assigned batches detail
        assigned_batches = Batch.query.filter(Batch.id.in_(batch_ids)).all() if batch_ids else []

        # Today's classes from timetable
        day_name = today.strftime('%A')
        todays_classes = Timetable.query.filter_by(
            teacher_id=teacher.id,
            day_of_week=day_name
        ).order_by(Timetable.start_time).all()

        # Recent announcements
        announcements = Announcement.query.filter(
            Announcement.target_role.in_(['all', 'teacher'])
        ).order_by(Announcement.publish_date.desc()).limit(5).all()

        return {
            'teacher': teacher,
            'assigned_batches': assigned_batches,
            'total_students': total_students,
            'pending_homework_count': pending_homework,
            'todays_classes': todays_classes,
            'announcements': announcements
        }

    @staticmethod
    def get_student_stats(student_id):
        student = Student.query.get(student_id)
        if not student:
            return {}

        today = datetime.utcnow().date()

        # Fee status
        student_fee = StudentFee.query.filter_by(student_id=student.id).first()

        # Upcoming tests for student's batch
        upcoming_tests = Exam.query.filter(
            Exam.batch_id == student.batch_id,
            Exam.exam_date >= today
        ).order_by(Exam.exam_date.asc()).all() if student.batch_id else []

        # Active homework
        homework_list = Homework.query.filter(
            Homework.batch_id == student.batch_id
        ).order_by(Homework.due_date.desc()).limit(10).all() if student.batch_id else []

        # Study materials
        materials = StudyMaterial.query.filter(
            StudyMaterial.batch_id == student.batch_id
        ).order_by(StudyMaterial.upload_date.desc()).limit(10).all() if student.batch_id else []

        # Recent exam marks
        marks = Mark.query.filter_by(student_id=student.id).all()

        # Announcements
        announcements = Announcement.query.filter(
            (Announcement.target_role.in_(['all', 'student'])) |
            (Announcement.batch_id == student.batch_id)
        ).order_by(Announcement.publish_date.desc()).limit(5).all()

        return {
            'student': student,
            'attendance_percentage': student.attendance_percentage,
            'student_fee': student_fee,
            'upcoming_tests': upcoming_tests,
            'homework_list': homework_list,
            'materials': materials,
            'marks': marks,
            'announcements': announcements
        }

    @staticmethod
    def get_parent_stats(parent_id):
        parent = Parent.query.get(parent_id)
        if not parent:
            return {}

        linked_students = [link.student for link in parent.student_links.all()]

        # Collect summary data for all linked children
        children_data = []
        for child in linked_students:
            fee = StudentFee.query.filter_by(student_id=child.id).first()
            recent_marks = Mark.query.filter_by(student_id=child.id).limit(5).all()
            children_data.append({
                'student': child,
                'attendance_percentage': child.attendance_percentage,
                'fee': fee,
                'recent_marks': recent_marks
            })

        announcements = Announcement.query.filter(
            Announcement.target_role.in_(['all', 'parent'])
        ).order_by(Announcement.publish_date.desc()).limit(5).all()

        return {
            'parent': parent,
            'children_data': children_data,
            'announcements': announcements
        }
