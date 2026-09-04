import os
from datetime import datetime, timedelta
from app import create_app, db
from app.models import (
    User, Role, InstituteSettings, Class, Subject, Batch,
    Teacher, Student, Parent, StudentParent, FeeStructure, StudentFee,
    FeePayment, Attendance, AttendanceStatus, Timetable, DayOfWeek,
    Exam, Mark, Homework, StudyMaterial, Announcement, Enquiry, EnquiryStatus
)

app = create_app('development')

def seed_database():
    with app.app_context():
        print("Recreating database tables...")
        db.drop_all()
        db.create_all()

        print("Seeding Institute Settings...")
        settings = InstituteSettings(
            name='EduFlow Academy',
            tagline='Empowering Minds & Inspiring Academic Excellence',
            phone='+1 (800) 555-EDU1',
            email='contact@eduflow.academy',
            address='100 Learning Way, Innovation Tech Park, Suite 500',
            academic_session='2026-2027',
            currency='$',
            timezone='UTC'
        )
        db.session.add(settings)

        print("Creating Core User Accounts...")

        # 1. Super Admin Account
        admin_user = User(
            username='admin',
            email='admin@eduflow.academy',
            first_name='Super',
            last_name='Admin',
            role=Role.SUPER_ADMIN,
            is_active=True
        )
        admin_user.set_password('Admin@123')
        db.session.add(admin_user)

        # 2. Staff Administrator
        staff_user = User(
            username='staff1',
            email='staff@eduflow.academy',
            first_name='Sarah',
            last_name='Jenkins',
            role=Role.ADMIN,
            is_active=True
        )
        staff_user.set_password('Staff@123')
        db.session.add(staff_user)

        # 3. Faculty Teachers
        t1_user = User(username='dr_smith', email='smith@eduflow.academy', first_name='Dr. Richard', last_name='Smith', role=Role.TEACHER, is_active=True)
        t1_user.set_password('Teacher@123')
        t2_user = User(username='prof_davis', email='davis@eduflow.academy', first_name='Prof. Elena', last_name='Davis', role=Role.TEACHER, is_active=True)
        t2_user.set_password('Teacher@123')
        db.session.add_all([t1_user, t2_user])
        db.session.flush()

        t1 = Teacher(user_id=t1_user.id, teacher_code='TCH-001', mobile='+1 555-0101', qualification='Ph.D. Physics', specialization='Quantum & Theoretical Physics', joining_date=datetime(2023, 1, 15).date())
        t2 = Teacher(user_id=t2_user.id, teacher_code='TCH-002', mobile='+1 555-0102', qualification='M.Sc Pure Mathematics', specialization='Advanced Calculus & Algebra', joining_date=datetime(2023, 3, 20).date())
        db.session.add_all([t1, t2])

        # 4. Classes
        c10 = Class(name='Class 10 Foundation', code='C10', description='Grade 10 Secondary Board & Olympiad Foundation')
        c11 = Class(name='Class 11 Science', code='C11-SCI', description='Grade 11 Senior Secondary Science (PCM/PCB)')
        c12 = Class(name='Class 12 Science', code='C12-SCI', description='Grade 12 Senior Secondary Science & Entrance Prep')
        db.session.add_all([c10, c11, c12])
        db.session.flush()

        # 5. Subjects
        sub_phy = Subject(name='Physics', code='PHY-11', class_id=c11.id, description='Mechanics, Electromagnetism, Modern Physics')
        sub_math = Subject(name='Mathematics', code='MTH-11', class_id=c11.id, description='Calculus, Trigonometry, Coordinate Geometry')
        sub_chem = Subject(name='Chemistry', code='CHM-11', class_id=c11.id, description='Organic, Inorganic & Physical Chemistry')
        db.session.add_all([sub_phy, sub_math, sub_chem])
        db.session.flush()

        # 6. Batches
        b1 = Batch(name='Class 11 PCM Morning', code='B11-PCM-AM', class_id=c11.id, max_capacity=30, start_date=datetime(2026, 4, 1).date(), schedule_description='Mon-Fri 08:00 AM - 11:30 AM', status='active')
        b2 = Batch(name='Class 11 PCM Evening', code='B11-PCM-PM', class_id=c11.id, max_capacity=25, start_date=datetime(2026, 4, 1).date(), schedule_description='Mon-Fri 04:00 PM - 07:30 PM', status='active')
        db.session.add_all([b1, b2])
        db.session.flush()

        # 7. Fee Structures
        fs1 = FeeStructure(name='Class 11 Standard Science Package', class_id=c11.id, admission_fee=200.0, course_fee=1200.0, monthly_fee=100.0, exam_fee=100.0, discount_amount=100.0)
        db.session.add(fs1)
        db.session.flush()

        # 8. Students & Parents
        s1_user = User(username='student1', email='john@gmail.com', first_name='John', last_name='Doe', role=Role.STUDENT, is_active=True)
        s1_user.set_password('Student@123')
        s2_user = User(username='student2', email='alice@gmail.com', first_name='Alice', last_name='Walker', role=Role.STUDENT, is_active=True)
        s2_user.set_password('Student@123')
        db.session.add_all([s1_user, s2_user])
        db.session.flush()

        st1 = Student(user_id=s1_user.id, student_code='STU-2026-0001', dob=datetime(2009, 5, 14).date(), gender='Male', mobile='+1 555-0201', address='45 Oak Street, Springfield', parent_name='Robert Doe', parent_mobile='+1 555-0301', admission_date=datetime(2026, 4, 2).date(), class_id=c11.id, batch_id=b1.id, roll_number='101', status='active')
        st2 = Student(user_id=s2_user.id, student_code='STU-2026-0002', dob=datetime(2009, 8, 22).date(), gender='Female', mobile='+1 555-0202', address='88 Pine Avenue, Springfield', parent_name='Mary Walker', parent_mobile='+1 555-0302', admission_date=datetime(2026, 4, 5).date(), class_id=c11.id, batch_id=b1.id, roll_number='102', status='active')
        db.session.add_all([st1, st2])
        db.session.flush()

        # Student Fee Accounts
        sf1 = StudentFee(student_id=st1.id, fee_structure_id=fs1.id, total_payable=fs1.total_calculated_amount, total_paid=800.0, due_date=datetime(2026, 10, 1).date(), status='partial')
        sf2 = StudentFee(student_id=st2.id, fee_structure_id=fs1.id, total_payable=fs1.total_calculated_amount, total_paid=fs1.total_calculated_amount, due_date=datetime(2026, 10, 1).date(), status='paid')
        db.session.add_all([sf1, sf2])
        db.session.flush()

        # Fee Payment Receipts
        fp1 = FeePayment(student_fee_id=sf1.id, receipt_number='REC-20260402-A1B2', amount_paid=800.0, payment_method='upi', payment_date=datetime(2026, 4, 2, 10, 30), transaction_notes='Initial installment payment', recorded_by_user_id=admin_user.id, status='valid')
        fp2 = FeePayment(student_fee_id=sf2.id, receipt_number='REC-20260405-C3D4', amount_paid=sf2.total_payable, payment_method='bank_transfer', payment_date=datetime(2026, 4, 5, 14, 15), transaction_notes='Paid in full with 10% lump-sum waiver', recorded_by_user_id=admin_user.id, status='valid')
        db.session.add_all([fp1, fp2])

        # Parent Account
        p_user = User(username='parent1', email='robert.doe@gmail.com', first_name='Robert', last_name='Doe', role=Role.PARENT, is_active=True)
        p_user.set_password('Parent@123')
        db.session.add(p_user)
        db.session.flush()

        p1 = Parent(user_id=p_user.id, mobile='+1 555-0301', occupation='Software Architect', address='45 Oak Street, Springfield')
        db.session.add(p1)
        db.session.flush()

        sp1 = StudentParent(student_id=st1.id, parent_id=p1.id, relationship='father')
        db.session.add(sp1)

        # 9. Attendance
        today = datetime.utcnow().date()
        for i in range(5):
            d = today - timedelta(days=i)
            att1 = Attendance(student_id=st1.id, batch_id=b1.id, date=d, status=AttendanceStatus.PRESENT, marked_by_teacher_id=t1.id)
            att2 = Attendance(student_id=st2.id, batch_id=b1.id, date=d, status=AttendanceStatus.PRESENT if i != 2 else AttendanceStatus.ABSENT, marked_by_teacher_id=t1.id)
            db.session.add_all([att1, att2])

        # 10. Timetable
        tt1 = Timetable(day_of_week=DayOfWeek.MONDAY, start_time=datetime.strptime('08:00', '%H:%M').time(), end_time=datetime.strptime('09:30', '%H:%M').time(), class_id=c11.id, batch_id=b1.id, subject_id=sub_phy.id, teacher_id=t1.id, room_number='Room 201')
        tt2 = Timetable(day_of_week=DayOfWeek.MONDAY, start_time=datetime.strptime('09:45', '%H:%M').time(), end_time=datetime.strptime('11:15', '%H:%M').time(), class_id=c11.id, batch_id=b1.id, subject_id=sub_math.id, teacher_id=t2.id, room_number='Room 201')
        db.session.add_all([tt1, tt2])

        # 11. Examinations & Marks
        ex1 = Exam(title='Physics Mid-Term Evaluation', exam_type='midterm', class_id=c11.id, batch_id=b1.id, exam_date=datetime(2026, 8, 20).date(), max_marks=100.0)
        db.session.add(ex1)
        db.session.flush()

        m1 = Mark(exam_id=ex1.id, subject_id=sub_phy.id, student_id=st1.id, marks_obtained=92.0, max_marks=100.0, grade='A+', remarks='Outstanding conceptual clarity', entered_by_user_id=t1_user.id)
        m2 = Mark(exam_id=ex1.id, subject_id=sub_phy.id, student_id=st2.id, marks_obtained=84.5, max_marks=100.0, grade='A', remarks='Great performance', entered_by_user_id=t1_user.id)
        db.session.add_all([m1, m2])

        # 12. Announcements
        ann1 = Announcement(title='Welcome to EduFlow Academy Academic Year 2026-27', content='We are thrilled to welcome all new students and faculty members. Orientation sessions start this Monday.', target_role='all', priority='normal', publish_date=datetime.utcnow(), created_by_user_id=admin_user.id)
        db.session.add(ann1)

        # 13. Admissions CRM Enquiry
        enq1 = Enquiry(student_name='David Miller', parent_name='Susan Miller', mobile='+1 555-0999', email='susan@miller.com', interested_class_id=c11.id, enquiry_date=datetime(2026, 8, 28).date(), status=EnquiryStatus.NEW, notes='Interested in Class 11 PCM Evening Batch.')
        db.session.add(enq1)

        db.session.commit()
        print("\nSeed data generated successfully!")
        print("--------------------------------------------------")
        print("Super Admin: username='admin', password='Admin@123'")
        print("Teacher:     username='dr_smith', password='Teacher@123'")
        print("Student:     username='student1', password='Student@123'")
        print("Parent:      username='parent1', password='Parent@123'")
        print("--------------------------------------------------")

if __name__ == '__main__':
    seed_database()
