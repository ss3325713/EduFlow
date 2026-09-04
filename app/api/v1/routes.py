from datetime import datetime, timedelta
import jwt
from flask import request, jsonify, current_app
from app.api.v1 import api_v1_bp
from app.extensions import db
from app.models import User, Student, Teacher, Batch, Attendance, StudentFee, FeePayment, Announcement

def generate_token(user):
    payload = {
        'sub': user.id,
        'username': user.username,
        'role': user.role,
        'exp': datetime.utcnow() + timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS'])
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

def verify_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, jsonify({'error': 'Authorization header missing or invalid format'}), 401
    
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        user = User.query.get(payload['sub'])
        return user, None, 200
    except jwt.ExpiredSignatureError:
        return None, jsonify({'error': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return None, jsonify({'error': 'Invalid token'}), 401

@api_v1_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    identifier = data.get('username') or data.get('email')
    password = data.get('password')

    if not identifier or not password:
        return jsonify({'error': 'Username/email and password are required'}), 400

    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account deactivated'}), 403

    token = generate_token(user)
    return jsonify({
        'token': token,
        'user': user.to_dict()
    }), 200

@api_v1_bp.route('/students', methods=['GET'])
def get_students():
    user, err_resp, code = verify_token()
    if err_resp: return err_resp, code

    students = Student.query.filter_by(status='active').all()
    return jsonify({'students': [s.to_dict() for s in students]}), 200

@api_v1_bp.route('/teachers', methods=['GET'])
def get_teachers():
    user, err_resp, code = verify_token()
    if err_resp: return err_resp, code

    teachers = Teacher.query.filter_by(employment_status='active').all()
    return jsonify({'teachers': [t.to_dict() for t in teachers]}), 200

@api_v1_bp.route('/batches', methods=['GET'])
def get_batches():
    user, err_resp, code = verify_token()
    if err_resp: return err_resp, code

    batches = Batch.query.filter_by(status='active').all()
    return jsonify({'batches': [b.to_dict() for b in batches]}), 200

@api_v1_bp.route('/attendance', methods=['GET', 'POST'])
def attendance():
    user, err_resp, code = verify_token()
    if err_resp: return err_resp, code

    if request.method == 'POST':
        data = request.get_json() or {}
        batch_id = data.get('batch_id')
        records = data.get('records', [])  # list of {student_id, status, remarks}

        if not batch_id or not records:
            return jsonify({'error': 'batch_id and records array are required'}), 400

        teacher = user.teacher_profile
        teacher_id = teacher.id if teacher else None
        today = datetime.utcnow().date()

        for item in records:
            student_id = item.get('student_id')
            status_val = item.get('status', 'present')
            remarks = item.get('remarks', '')

            att = Attendance.query.filter_by(student_id=student_id, batch_id=batch_id, date=today).first()
            if att:
                att.status = status_val
                att.remarks = remarks
                att.marked_by_teacher_id = teacher_id
            else:
                att = Attendance(
                    student_id=student_id,
                    batch_id=batch_id,
                    date=today,
                    status=status_val,
                    marked_by_teacher_id=teacher_id,
                    remarks=remarks
                )
                db.session.add(att)

        db.session.commit()
        return jsonify({'message': f'Attendance submitted for {len(records)} students'}), 200

    # GET
    batch_id = request.args.get('batch_id', type=int)
    query = Attendance.query
    if batch_id: query = query.filter_by(batch_id=batch_id)
    records = query.order_by(Attendance.date.desc()).limit(50).all()
    return jsonify({'attendance': [r.to_dict() for r in records]}), 200

@api_v1_bp.route('/announcements', methods=['GET'])
def get_announcements():
    user, err_resp, code = verify_token()
    if err_resp: return err_resp, code

    announcements = Announcement.query.order_by(Announcement.publish_date.desc()).limit(20).all()
    return jsonify({'announcements': [a.to_dict() for a in announcements]}), 200
