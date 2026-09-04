import pytest
from datetime import datetime
from app import create_app, db
from app.models import User, Role, Student, Teacher, Class, Batch, FeeStructure, StudentFee, FeePayment, Attendance
from app.services.fee_service import FeeService

@pytest.fixture
def app_instance():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app_instance):
    return app_instance.test_client()

def test_user_authentication_and_hashing(app_instance):
    with app_instance.app_context():
        user = User(username='testadmin', email='testadmin@eduflow.com', first_name='Test', last_name='Admin', role=Role.SUPER_ADMIN)
        user.set_password('SecretPassword123')
        db.session.add(user)
        db.session.commit()

        assert user.check_password('SecretPassword123') is True
        assert user.check_password('WrongPassword') is False
        assert user.is_super_admin() is True

def test_student_creation_and_code(app_instance):
    with app_instance.app_context():
        u = User(username='stu_test', email='stu@test.com', first_name='John', last_name='Doe', role=Role.STUDENT)
        u.set_password('Pass123')
        db.session.add(u)
        db.session.flush()

        student = Student(user_id=u.id, student_code='STU-2026-9999', admission_date=datetime.utcnow().date())
        db.session.add(student)
        db.session.commit()

        fetched = Student.query.filter_by(student_code='STU-2026-9999').first()
        assert fetched is not None
        assert fetched.full_name == 'John Doe'

def test_batch_capacity_constraint(app_instance):
    with app_instance.app_context():
        cls = Class(name='Class 10', code='C10')
        db.session.add(cls)
        db.session.flush()

        batch = Batch(name='Test Batch', code='B10', class_id=cls.id, max_capacity=1)
        db.session.add(batch)
        db.session.commit()

        assert batch.is_full is False

        # Add 1 student
        u1 = User(username='s1', email='s1@t.com', first_name='S1', last_name='T', role=Role.STUDENT)
        u1.set_password('Pass123')
        db.session.add(u1)
        db.session.flush()
        st1 = Student(user_id=u1.id, student_code='STU-001', batch_id=batch.id)
        db.session.add(st1)
        db.session.commit()

        assert batch.is_full is True

def test_fee_calculation_and_payment(app_instance):
    with app_instance.app_context():
        cls = Class(name='Class 11', code='C11')
        db.session.add(cls)
        db.session.flush()

        fs = FeeStructure(name='Pkg', class_id=cls.id, admission_fee=100.0, course_fee=500.0, monthly_fee=0.0, exam_fee=50.0, discount_amount=50.0)
        db.session.add(fs)
        db.session.flush()

        assert fs.total_calculated_amount == 600.0

        u = User(username='s2', email='s2@t.com', first_name='S2', last_name='T', role=Role.STUDENT)
        u.set_password('Pass123')
        db.session.add(u)
        db.session.flush()

        student = Student(user_id=u.id, student_code='STU-002')
        db.session.add(student)
        db.session.flush()

        sf = StudentFee(student_id=student.id, fee_structure_id=fs.id, total_payable=fs.total_calculated_amount, total_paid=0.0)
        db.session.add(sf)
        db.session.commit()

        payment = FeeService.record_payment(student_fee_id=sf.id, amount_paid=200.0, payment_method='cash')
        assert payment.amount_paid == 200.0
        assert sf.total_paid == 200.0
        assert sf.balance == 400.0
        assert sf.status == 'partial'

def test_teacher_request_and_super_admin_deletion(app_instance):
    from app.models import StudentRequest, Parent, StudentParent, Notification
    with app_instance.app_context():
        # Setup Super Admin
        sa = User(username='sa_user', email='sa@test.com', first_name='Super', last_name='Admin', role=Role.SUPER_ADMIN)
        sa.set_password('Pass123')

        # Setup Teacher
        tu = User(username='tech_user', email='tech@test.com', first_name='Teacher', last_name='One', role=Role.TEACHER)
        tu.set_password('Pass123')
        db.session.add_all([sa, tu])
        db.session.flush()

        teacher = Teacher(user_id=tu.id, teacher_code='TCH-001')
        db.session.add(teacher)
        db.session.flush()

        # Setup Student
        su = User(username='stu_user', email='stu2@test.com', first_name='Student', last_name='Two', role=Role.STUDENT)
        su.set_password('Pass123')
        db.session.add(su)
        db.session.flush()

        student = Student(user_id=su.id, student_code='STU-002')
        db.session.add(student)

        # Setup Parent
        pu = User(username='par_user', email='par@test.com', first_name='Parent', last_name='One', role=Role.PARENT)
        pu.set_password('Pass123')
        db.session.add(pu)
        db.session.flush()

        parent = Parent(user_id=pu.id, occupation='Engineer')
        db.session.add(parent)
        db.session.commit()

        # Test Parent linking and delinking
        link = StudentParent(parent_id=parent.id, student_id=student.id, relationship='father')
        db.session.add(link)
        db.session.commit()
        assert parent.student_links.count() == 1

        db.session.delete(link)
        db.session.commit()
        assert parent.student_links.count() == 0

        # Teacher directly suspends student with reason
        su.is_active = False
        student.status = 'suspended'
        notif = Notification(user_id=sa.id, title='Student Suspended by Teacher', message='Disciplinary issue')
        db.session.add(notif)
        db.session.commit()

        assert su.is_active is False
        assert student.status == 'suspended'
        assert sa.notifications.count() == 1

        # Super Admin permanently purges disabled student
        db.session.delete(su)
        db.session.commit()
        assert db.session.get(Student, student.id) is None

        # Super Admin disables teacher first, then permanently purges
        tu.is_active = False
        db.session.commit()
        db.session.delete(tu)
        db.session.commit()
        assert db.session.get(Teacher, teacher.id) is None

        # Super Admin disables parent first, then permanently purges
        pu.is_active = False
        db.session.commit()
        db.session.delete(pu)
        db.session.commit()
        assert db.session.get(Parent, parent.id) is None

def test_exam_performance_report_card(app_instance):
    from app.models import Exam, Mark, Class, Batch, Subject, InstituteSettings
    with app_instance.app_context():
        cls = Class(name='Class 12', code='C12')
        db.session.add(cls)
        db.session.flush()

        batch = Batch(name='Batch Alpha', code='B12A', class_id=cls.id)
        sub1 = Subject(name='Mathematics', code='MATH12', class_id=cls.id)
        sub2 = Subject(name='Physics', code='PHY12', class_id=cls.id)
        db.session.add_all([batch, sub1, sub2])
        db.session.flush()

        # Create exam
        exam = Exam(title='Midterm Exam 2026', exam_type='midterm', class_id=cls.id, batch_id=batch.id, exam_date=datetime.utcnow().date(), max_marks=100.0)
        db.session.add(exam)
        db.session.flush()

        # Create 2 students
        u1 = User(username='s_alpha', email='sa@test.com', first_name='Alpha', last_name='Student', role=Role.STUDENT)
        u1.set_password('Pass123')
        u2 = User(username='s_beta', email='sb@test.com', first_name='Beta', last_name='Student', role=Role.STUDENT)
        u2.set_password('Pass123')
        db.session.add_all([u1, u2])
        db.session.flush()

        st1 = Student(user_id=u1.id, student_code='STU-A', class_id=cls.id, batch_id=batch.id)
        st2 = Student(user_id=u2.id, student_code='STU-B', class_id=cls.id, batch_id=batch.id)
        db.session.add_all([st1, st2])
        db.session.flush()

        # Add marks: st1 gets 90 in MATH, 80 in PHY. st2 gets 70 in MATH, 60 in PHY.
        m11 = Mark(exam_id=exam.id, subject_id=sub1.id, student_id=st1.id, marks_obtained=90.0, max_marks=100.0, grade='A+')
        m12 = Mark(exam_id=exam.id, subject_id=sub2.id, student_id=st1.id, marks_obtained=80.0, max_marks=100.0, grade='A')
        m21 = Mark(exam_id=exam.id, subject_id=sub1.id, student_id=st2.id, marks_obtained=70.0, max_marks=100.0, grade='B')
        m22 = Mark(exam_id=exam.id, subject_id=sub2.id, student_id=st2.id, marks_obtained=60.0, max_marks=100.0, grade='C')
        db.session.add_all([m11, m12, m21, m22])
        db.session.commit()

        # Check benchmarks for sub1 (Math)
        math_marks = Mark.query.filter_by(exam_id=exam.id, subject_id=sub1.id).all()
        highest_math = max(m.marks_obtained for m in math_marks)
        avg_math = sum(m.marks_obtained for m in math_marks) / len(math_marks)

        assert highest_math == 90.0
        assert avg_math == 80.0

        # Check st1 total
        st1_total = sum(m.marks_obtained for m in Mark.query.filter_by(exam_id=exam.id, student_id=st1.id).all())
        st2_total = sum(m.marks_obtained for m in Mark.query.filter_by(exam_id=exam.id, student_id=st2.id).all())

        assert st1_total == 170.0
        assert st2_total == 130.0
        assert st1_total > st2_total

def test_student_fees_view_and_attendance_permissions(app_instance, client):
    from flask_login import login_user
    with app_instance.test_request_context():
        u = User(username='stu_fees_test', email='stu_fees@test.com', first_name='Fees', last_name='Test', role=Role.STUDENT)
        u.set_password('Pass123')
        db.session.add(u)
        db.session.flush()

        student = Student(user_id=u.id, student_code='STU-FEES-1')
        db.session.add(student)
        db.session.commit()

        login_user(u)

        # Access /fees/ route (should render student_view.html cleanly with status 200)
        res_fees = client.get('/fees/')
        assert res_fees.status_code == 200
        assert b'My Fee Summary' in res_fees.data

        # Attempt to access attendance marking route (should be denied for student)
        res_att_mark = client.get('/attendance/', follow_redirects=True)
        assert b'You do not have permission' in res_att_mark.data or b'Dashboard' in res_att_mark.data

def test_student_report_privacy_and_batch_isolation(app_instance, client):
    from flask_login import login_user
    from app.models import Exam, Mark, Class, Batch, Subject, StudyMaterial, Homework
    with app_instance.app_context():
        cls1 = Class(name='Class A', code='CA')
        cls2 = Class(name='Class B', code='CB')
        db.session.add_all([cls1, cls2])
        db.session.flush()

        batch1 = Batch(name='Batch A1', code='BA1', class_id=cls1.id)
        batch2 = Batch(name='Batch B1', code='BB1', class_id=cls2.id)
        sub1 = Subject(name='Math A', code='MA', class_id=cls1.id)
        sub2 = Subject(name='Math B', code='MB', class_id=cls2.id)
        db.session.add_all([batch1, batch2, sub1, sub2])
        db.session.flush()

        u_stu1 = User(username='stu_priv1', email='sp1@test.com', first_name='Priv1', last_name='Test', role=Role.STUDENT)
        u_stu1.set_password('Pass123')
        u_stu2 = User(username='stu_priv2', email='sp2@test.com', first_name='Priv2', last_name='Test', role=Role.STUDENT)
        u_stu2.set_password('Pass123')
        db.session.add_all([u_stu1, u_stu2])
        db.session.flush()

        st1 = Student(user_id=u_stu1.id, student_code='STU-P1', class_id=cls1.id, batch_id=batch1.id)
        st2 = Student(user_id=u_stu2.id, student_code='STU-P2', class_id=cls2.id, batch_id=batch2.id)
        db.session.add_all([st1, st2])
        db.session.flush()

        exam1 = Exam(title='Exam Batch 1', exam_type='unit_test', class_id=cls1.id, batch_id=batch1.id, exam_date=datetime.utcnow().date(), max_marks=100.0)
        db.session.add(exam1)
        db.session.flush()

        mat_b2 = StudyMaterial(title='Notes Batch B', class_id=cls2.id, batch_id=batch2.id, subject_id=sub2.id, teacher_id=1, file_path='dummy.pdf', file_type='pdf', upload_date=datetime.utcnow())
        hw_b2 = Homework(title='HW Batch B', class_id=cls2.id, batch_id=batch2.id, subject_id=sub2.id, teacher_id=1, issue_date=datetime.utcnow().date(), due_date=datetime.utcnow().date(), attachment_filename='hw_b2.pdf')
        db.session.add_all([mat_b2, hw_b2])
        db.session.commit()

        # Log in as Student 1 (in Batch 1)
        with app_instance.test_request_context():
            login_user(u_stu1)

            # 1. Accessing reports_list for Exam 1 (Batch 1) should REDIRECT student directly to their own report card
            res_reports_list = client.get(f'/exams/{exam1.id}/reports', follow_redirects=True)
            assert res_reports_list.status_code == 200
            assert b'ACADEMIC PERFORMANCE REPORT CARD' in res_reports_list.data or b'Student Performance Report Card' in res_reports_list.data

            # 2. Student 1 attempting to view Student 2's report card directly should be denied
            res_other_report = client.get(f'/exams/{exam1.id}/student/{st2.id}/report', follow_redirects=True)
            assert b'You can only view your own exam performance reports' in res_other_report.data

            # 3. Student 1 attempting to download study material from Batch 2 should be denied
            res_mat = client.get(f'/materials/download/{mat_b2.id}', follow_redirects=True)
            assert b'You do not have access to study materials from other batches' in res_mat.data

            # 4. Student 1 attempting to download homework attachment from Batch 2 should be denied
            res_hw = client.get(f'/assignments/download/{hw_b2.attachment_filename}', follow_redirects=True)
            assert b'You do not have access to homework attachments from other batches' in res_hw.data

def test_teacher_fee_restriction_and_announcements(app_instance, client):
    from flask_login import login_user
    from app.models import Announcement
    with app_instance.app_context():
        u_teacher = User(username='t_ann_test', email='t_ann@test.com', first_name='Teacher', last_name='Announcer', role=Role.TEACHER)
        u_teacher.set_password('Pass123')
        db.session.add(u_teacher)
        db.session.commit()

        with app_instance.test_request_context():
            login_user(u_teacher)

            # 1. Teachers MUST NOT have access to fees section
            res_fees = client.get('/fees/', follow_redirects=True)
            assert b'Teachers do not have access to fee and receipt management' in res_fees.data

            # 2. Teachers CAN publish announcements
            res_post_ann = client.post('/announcements/add', data={
                'title': 'Special Subject Workshop Notice',
                'content': 'Interactive Problem Solving Session for Physics Batch A',
                'target_role': 'student',
                'priority': 'high'
            }, follow_redirects=True)
            assert res_post_ann.status_code == 200
            assert b'published successfully' in res_post_ann.data or b'Special Subject Workshop Notice' in res_post_ann.data

            # Verify saved in database
            ann = Announcement.query.filter_by(title='Special Subject Workshop Notice').first()
            assert ann is not None
            assert ann.created_by_user_id == u_teacher.id

def test_country_currency_and_regional_settings(app_instance, client):
    from flask_login import login_user
    from app.models import InstituteSettings
    with app_instance.app_context():
        u_sadmin = User(username='sa_regional', email='sa_reg@test.com', first_name='Super', last_name='Admin', role=Role.SUPER_ADMIN)
        u_sadmin.set_password('Pass123')
        db.session.add(u_sadmin)
        db.session.commit()

        with app_instance.test_request_context():
            login_user(u_sadmin)

            # Update settings with India country preset (₹ currency, Asia/Kolkata timezone)
            res_update = client.post('/settings/', data={
                'name': 'EduFlow Academy India',
                'tagline': 'Empowering Indian Students',
                'phone': '+91 98765 43210',
                'email': 'contact@eduflow.in',
                'address': 'MG Road, Bengaluru, India',
                'academic_session': '2026-2027',
                'country': 'India',
                'currency': '₹',
                'timezone': 'Asia/Kolkata'
            }, follow_redirects=True)

            assert res_update.status_code == 200
            assert b'Institute settings updated successfully' in res_update.data

            settings = InstituteSettings.get_settings()
            assert settings.country == 'India'
            assert settings.currency == '₹'
            assert settings.timezone == 'Asia/Kolkata'



