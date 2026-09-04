from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.services.analytics_service import AnalyticsService

@dashboard_bp.route('/')
@login_required
def index():
    if current_user.is_super_admin() or current_user.is_admin():
        stats = AnalyticsService.get_super_admin_stats()
        return render_template('dashboard/super_admin.html', stats=stats)
    elif current_user.is_teacher():
        teacher_profile = current_user.teacher_profile
        stats = AnalyticsService.get_teacher_stats(teacher_profile.id if teacher_profile else 0)
        return render_template('dashboard/teacher.html', stats=stats)
    elif current_user.is_student():
        student_profile = current_user.student_profile
        stats = AnalyticsService.get_student_stats(student_profile.id if student_profile else 0)
        return render_template('dashboard/student.html', stats=stats)
    elif current_user.is_parent():
        parent_profile = current_user.parent_profile
        stats = AnalyticsService.get_parent_stats(parent_profile.id if parent_profile else 0)
        return render_template('dashboard/parent.html', stats=stats)

    return render_template('dashboard/super_admin.html', stats={})
