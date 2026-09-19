from app.models.user import User, Role
from app.models.system import InstituteSettings, AuditLog
from app.models.academic import Class, Subject, Batch, TeacherAssignment
from app.models.profiles import Teacher, Student, Parent, StudentParent, StudentRequest
from app.models.fee import FeeStructure, StudentFee, FeePayment
from app.models.attendance import Attendance, AttendanceStatus
from app.models.teacher_attendance import TeacherAttendance
from app.models.timetable import Timetable, DayOfWeek
from app.models.exam import Exam, Mark
from app.models.academic_content import Homework, StudyMaterial
from app.models.communication import Announcement, Notification, TeacherRequest
from app.models.diary import DiaryEntry
from app.models.enquiry import Enquiry, EnquiryStatus
from app.models.email_log import EmailLog
from app.models.email_preference import EmailPreference, EmailCategory

__all__ = [
    'User', 'Role',
    'InstituteSettings', 'AuditLog',
    'Class', 'Subject', 'Batch', 'TeacherAssignment',
    'Teacher', 'Student', 'Parent', 'StudentParent', 'StudentRequest',
    'FeeStructure', 'StudentFee', 'FeePayment',
    'Attendance', 'AttendanceStatus', 'TeacherAttendance',
    'Timetable', 'DayOfWeek',
    'Exam', 'Mark',
    'Homework', 'StudyMaterial',
    'Announcement', 'Notification', 'TeacherRequest',
    'DiaryEntry',
    'Enquiry', 'EnquiryStatus',
    'EmailLog', 'EmailPreference', 'EmailCategory'
]
