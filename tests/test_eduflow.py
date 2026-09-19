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

def test_super_admin_email_login_and_username_rejection(app_instance, client):
    with app_instance.app_context():
        sa = User(username='admin', email='superadmin@eduflow.academy', first_name='Super', last_name='Admin', role=Role.SUPER_ADMIN)
        sa.set_password('AdminSecret123')
        db.session.add(sa)
        db.session.commit()

        # 1. Logging in with email + password succeeds
        res_email = client.post('/auth/login', data={
            'login_type': 'super_admin',
            'email': 'superadmin@eduflow.academy',
            'password': 'AdminSecret123'
        }, follow_redirects=True)
        assert res_email.status_code == 200
        assert b'Dashboard' in res_email.data or b'Overview' in res_email.data

        # Logout
        client.get('/auth/logout')

        # 2. Attempting login with username "admin" for Super Admin is rejected with warning
        res_username = client.post('/auth/login', data={
            'login_type': 'portal',
            'login_identifier': 'admin',
            'password': 'AdminSecret123'
        }, follow_redirects=True)
        assert b'Super Admin authentication requires logging in with your Email Address' in res_username.data

def test_email_verification_and_password_reset_flow(app_instance, client):
    from app.models import EmailLog
    with app_instance.app_context():
        u = User(username='new_student', email='new_student@test.com', first_name='New', last_name='Student', role=Role.STUDENT, is_verified=False)
        u.set_password('StudentPass123')
        db.session.add(u)
        db.session.commit()

        token = u.generate_verification_token()
        db.session.commit()

        # 1. Verify email using valid token
        res_verify = client.get(f'/auth/verify-email/{token}')
        assert res_verify.status_code == 200
        assert b'Email Verified!' in res_verify.data
        assert u.is_verified is True

        # 2. Reusing used token fails
        res_reuse = client.get(f'/auth/verify-email/{token}')
        assert b'Verification Link Invalid' in res_reuse.data

        # 3. Password reset request
        reset_token = u.generate_password_reset_token()
        db.session.commit()

        res_reset = client.post(f'/auth/reset-password/{reset_token}', data={
            'password': 'NewPassword123',
            'confirm_password': 'NewPassword123'
        }, follow_redirects=True)
        assert res_reset.status_code == 200
        assert u.check_password('NewPassword123') is True

def test_teacher_parent_email_authorization(app_instance, client):
    from flask_login import login_user
    from app.models import User, Role, Class, Batch, Student, Teacher, TeacherAssignment, StudentParent, Parent, EmailLog, Subject
    with app_instance.app_context():


        cls = Class(name='Class 10', code='C10')
        db.session.add(cls)
        db.session.flush()

        b1 = Batch(name='Batch Authorized', code='B10A', class_id=cls.id)
        b2 = Batch(name='Batch Unauthorized', code='B10U', class_id=cls.id)
        db.session.add_all([b1, b2])
        db.session.flush()

        # Teacher assigned ONLY to Batch 1
        tu = User(username='t_auth', email='tauth@test.com', first_name='Auth', last_name='Teacher', role=Role.TEACHER)
        tu.set_password('Pass123')
        db.session.add(tu)
        db.session.flush()
        t = Teacher(user_id=tu.id, teacher_code='TCH-A')
        db.session.add(t)
        db.session.flush()

        sub = Subject(name='Physics', code='PHY10', class_id=cls.id)
        db.session.add(sub)
        db.session.flush()

        assign = TeacherAssignment(teacher_id=t.id, class_id=cls.id, batch_id=b1.id, subject_id=sub.id)
        db.session.add(assign)


        # Student 1 in Batch 1 (Authorized)
        u_s1 = User(username='s_auth', email='s1@test.com', first_name='S1', last_name='Auth', role=Role.STUDENT)
        u_s1.set_password('Pass123')
        u_p1 = User(username='p_auth', email='p1@test.com', first_name='P1', last_name='Auth', role=Role.PARENT)
        u_p1.set_password('Pass123')
        db.session.add_all([u_s1, u_p1])
        db.session.flush()

        st1 = Student(user_id=u_s1.id, student_code='STU-A1', batch_id=b1.id)
        p1 = Parent(user_id=u_p1.id)
        db.session.add_all([st1, p1])
        db.session.flush()

        sp1 = StudentParent(student_id=st1.id, parent_id=p1.id, relationship='father')
        db.session.add(sp1)

        # Student 2 in Batch 2 (Unauthorized)
        u_s2 = User(username='s_unauth', email='s2@test.com', first_name='S2', last_name='Unauth', role=Role.STUDENT)
        u_s2.set_password('Pass123')
        u_p2 = User(username='p_unauth', email='p2@test.com', first_name='P2', last_name='Unauth', role=Role.PARENT)
        u_p2.set_password('Pass123')
        db.session.add_all([u_s2, u_p2])
        db.session.flush()

        st2 = Student(user_id=u_s2.id, student_code='STU-U2', batch_id=b2.id)
        p2 = Parent(user_id=u_p2.id)
        db.session.add_all([st2, p2])
        db.session.flush()

        sp2 = StudentParent(student_id=st2.id, parent_id=p2.id, relationship='mother')
        db.session.add(sp2)
        db.session.commit()

        # Log in as Teacher
        with app_instance.test_request_context():
            login_user(tu)

            # 1. Emailing authorized student's parent (Student 1 / Parent 1) succeeds
            res_auth = client.post('/teachers/email/compose', data={
                'action': 'send',
                'student_id': st1.id,
                'parent_id': p1.id,
                'template_key': 'academic_concern',
                'subject': 'Academic Notice for Student 1',
                'message': 'Good progress in class.'
            }, follow_redirects=True)
            assert res_auth.status_code == 200
            assert b'successfully sent' in res_auth.data

            # 2. Emailing unauthorized student's parent (Student 2 / Parent 2) is REJECTED
            res_unauth = client.post('/teachers/email/compose', data={
                'action': 'send',
                'student_id': st2.id,
                'parent_id': p2.id,
                'template_key': 'academic_concern',
                'subject': 'Unauthorized Notice Attempt',
                'message': 'Attempting unauthorized send.'
            }, follow_redirects=True)
            assert b'Permission Denied: You are not authorized to email parents of this student' in res_unauth.data


def test_diary_feature_comprehensive(app_instance):
    from datetime import date
    from app.models import User, Role, DiaryEntry
    from app.diary.encryption import decrypt_diary_content

    with app_instance.app_context():
        user_a = User(username='diaryusera', email='usera@test.com', first_name='Alice', last_name='User', role=Role.STUDENT, is_active=True, is_verified=True)
        user_a.set_password('Pass123')
        db.session.add(user_a)

        user_b = User(username='diaryuserb', email='userb@test.com', first_name='Bob', last_name='User', role=Role.STUDENT, is_active=True, is_verified=True)
        user_b.set_password('Pass123')
        db.session.add(user_b)

        admin = User(username='diaryadmin', email='diaryadmin@test.com', first_name='Super', last_name='Admin', role=Role.SUPER_ADMIN, is_active=True, is_verified=True)
        admin.set_password('Pass123')
        db.session.add(admin)
        db.session.commit()

        client_a = app_instance.test_client()
        client_a.post('/auth/login', data={'login_identifier': 'diaryusera', 'password': 'Pass123'}, follow_redirects=True)

        # 1. User A creates a diary entry for 2026-09-11
        res_save = client_a.post('/diary/api/entry', json={
            'diary_date': '2026-09-11',
            'content': 'Alice secret personal diary entry for September 11th.'
        })
        assert res_save.status_code == 200
        json_save = res_save.get_json()
        assert json_save['success'] is True
        assert json_save['entry']['content'] == 'Alice secret personal diary entry for September 11th.'

        # 2. Check Database Storage is Encrypted (Encryption At Rest)
        db.session.expire_all()
        entry_db = DiaryEntry.query.filter_by(owner_user_id=user_a.id, diary_date=date(2026, 9, 11)).first()
        assert entry_db is not None
        assert 'Alice secret' not in entry_db.encrypted_content
        assert len(entry_db.encrypted_content) > 20

        # 3. User A retrieves entry (READ MODE)
        res_get_a = client_a.get('/diary/api/entry/2026-09-11')
        assert res_get_a.status_code == 200
        json_get_a = res_get_a.get_json()
        assert json_get_a['has_entry'] is True
        assert json_get_a['entry']['content'] == 'Alice secret personal diary entry for September 11th.'
        
        # User A logs out
        client_a.get('/auth/logout', follow_redirects=True)

        # 4. User B attempts to access User A's entry (IDOR / PRIVACY ISOLATION TEST)
        client_b = app_instance.test_client()
        client_b.post('/auth/login', data={'login_identifier': 'diaryuserb', 'password': 'Pass123'}, follow_redirects=True)
        res_get_b = client_b.get('/diary/api/entry/2026-09-11')
        assert res_get_b.status_code == 200
        json_get_b = res_get_b.get_json()
        assert json_get_b['has_entry'] is False
        assert json_get_b['entry'] is None
        client_b.get('/auth/logout', follow_redirects=True)

        # 5. Admin attempts to access User A's entry via API (ADMIN PRIVACY TEST)
        client_admin = app_instance.test_client()
        res_admin_login = client_admin.post('/auth/login', data={'login_type': 'super_admin', 'email': 'diaryadmin@test.com', 'password': 'Pass123'}, follow_redirects=True)
        assert res_admin_login.status_code == 200
        res_get_admin = client_admin.get('/diary/api/entry/2026-09-11')
        assert res_get_admin.status_code == 200
        json_get_admin = res_get_admin.get_json()
        assert json_get_admin['has_entry'] is False
        assert json_get_admin['entry'] is None
        client_admin.get('/auth/logout', follow_redirects=True)

        # 6. IDOR parameter injection attempt: User B sends payload with owner_user_id = user_a.id
        client_b = app_instance.test_client()
        client_b.post('/auth/login', data={'login_identifier': 'diaryuserb', 'password': 'Pass123'}, follow_redirects=True)
        res_inject = client_b.post('/diary/api/entry', json={
            'owner_user_id': user_a.id,
            'diary_date': '2026-09-11',
            'content': 'Hacked entry by Bob'
        })
        assert res_inject.status_code == 200
        # Check DB that User A's entry was NOT overwritten
        db.session.expire_all()
        entry_a_check = DiaryEntry.query.filter_by(owner_user_id=user_a.id, diary_date=date(2026, 9, 11)).first()
        decrypted_a = decrypt_diary_content(entry_a_check.encrypted_content, user_a.id)
        assert decrypted_a == 'Alice secret personal diary entry for September 11th.'

        # Verify Bob's entry was created under Bob's ID
        entry_b_check = DiaryEntry.query.filter_by(owner_user_id=user_b.id, diary_date=date(2026, 9, 11)).first()
        assert entry_b_check is not None
        assert entry_b_check.owner_user_id == user_b.id
        client_b.get('/auth/logout', follow_redirects=True)

        # 7. User A updates existing entry for 2026-09-11 (One entry per user per date constraint)
        client_a = app_instance.test_client()
        client_a.post('/auth/login', data={'login_identifier': 'diaryusera', 'password': 'Pass123'}, follow_redirects=True)
        res_update = client_a.post('/diary/api/entry/2026-09-11', json={
            'content': 'Alice updated diary entry content.'
        })
        assert res_update.status_code == 200
        assert DiaryEntry.query.filter_by(owner_user_id=user_a.id, diary_date=date(2026, 9, 11)).count() == 1

        # 8. Test Summary API endpoints (Year, Month, Range)
        res_summary = client_a.get('/diary/api/entries?year=2026&month=9')
        assert res_summary.status_code == 200
        json_sum = res_summary.get_json()
        assert json_sum['count'] >= 1
        for item in json_sum['entries']:
            assert 'content' not in item  # Plaintext content NOT in summary

        # 9. Delete entry
        res_del = client_a.delete('/diary/api/entry/2026-09-11')
        assert res_del.status_code == 200
        assert DiaryEntry.query.filter_by(owner_user_id=user_a.id, diary_date=date(2026, 9, 11)).first() is None

        # 10. Access UI page
        res_ui = client_a.get('/diary/')
        assert res_ui.status_code == 200
        assert b'My Personal Diary' in res_ui.data


def test_notification_system_comprehensive(app_instance):
    from app.models import User, Role, Notification

    with app_instance.app_context():
        user_1 = User(username='notifuser1', email='notif1@test.com', first_name='Notif', last_name='User1', role=Role.STUDENT, is_active=True, is_verified=True)
        user_1.set_password('Pass123')
        db.session.add(user_1)

        user_2 = User(username='notifuser2', email='notif2@test.com', first_name='Notif', last_name='User2', role=Role.STUDENT, is_active=True, is_verified=True)
        user_2.set_password('Pass123')
        db.session.add(user_2)
        db.session.commit()

        # Create notifications for User 1
        n1 = Notification(user_id=user_1.id, title='Notif 1', message='Message 1')
        n2 = Notification(user_id=user_1.id, title='Notif 2', message='Message 2')
        n3 = Notification(user_id=user_1.id, title='Notif 3', message='Message 3')
        # Create notification for User 2
        n_other = Notification(user_id=user_2.id, title='Other Notif', message='Other Message')
        db.session.add_all([n1, n2, n3, n_other])
        db.session.commit()

        client_1 = app_instance.test_client()
        client_1.post('/auth/login', data={'login_identifier': 'notifuser1', 'password': 'Pass123'}, follow_redirects=True)

        # 1. Fetch notification list -> unread count is 3
        res_list = client_1.get('/notifications/api/list')
        assert res_list.status_code == 200
        json_list = res_list.get_json()
        assert json_list['unread_count'] == 3
        assert len(json_list['notifications']) == 3

        # 2. Mark n1 as read
        res_read = client_1.post(f'/notifications/api/{n1.id}/read')
        assert res_read.status_code == 200
        assert res_read.get_json()['unread_count'] == 2

        db.session.expire_all()
        n1_db = db.session.get(Notification, n1.id)
        assert n1_db.is_read is True
        assert n1_db.read_at is not None
        assert n1_db.is_deleted is False  # Notification remains VISIBLE!

        # 3. Soft-delete n2
        res_del = client_1.post(f'/notifications/api/{n2.id}/delete')
        assert res_del.status_code == 200
        assert res_del.get_json()['unread_count'] == 1

        db.session.expire_all()
        n2_db = db.session.get(Notification, n2.id)
        assert n2_db.is_deleted is True
        assert n2_db.deleted_at is not None

        client_1.get('/auth/logout', follow_redirects=True)

        # 4. User 2 attempts to mark/delete User 1's notification (Authorization Check)
        client_2 = app_instance.test_client()
        client_2.post('/auth/login', data={'login_identifier': 'notifuser2', 'password': 'Pass123'}, follow_redirects=True)
        res_unauth_read = client_2.post(f'/notifications/api/{n3.id}/read')
        assert res_unauth_read.status_code == 404

        res_unauth_del = client_2.post(f'/notifications/api/{n3.id}/delete')
        assert res_unauth_del.status_code == 404

        client_2.get('/auth/logout', follow_redirects=True)

        # 5. User 1 marks all as read
        client_1 = app_instance.test_client()
        client_1.post('/auth/login', data={'login_identifier': 'notifuser1', 'password': 'Pass123'}, follow_redirects=True)
        res_all_read = client_1.post('/notifications/api/mark-all-read')
        assert res_all_read.status_code == 200
        assert res_all_read.get_json()['unread_count'] == 0

        # 6. User 1 clears all notifications
        res_clear = client_1.post('/notifications/api/clear-all')
        assert res_clear.status_code == 200

        # Check list is empty
        res_empty = client_1.get('/notifications/api/list')
        assert len(res_empty.get_json()['notifications']) == 0

        # Check User 2's notification remains untouched
        db.session.expire_all()
        n_other_db = db.session.get(Notification, n_other.id)
        assert n_other_db.is_deleted is False
        assert n_other_db.is_read is False





