from app.models.timetable import Timetable

class TimetableService:

    @staticmethod
    def validate_schedule(day_of_week, start_time, end_time, teacher_id, batch_id, exclude_id=None):
        """
        Validates whether creating or updating a timetable entry causes:
        1. Teacher double-booking conflict
        2. Batch double-booking conflict
        """
        # Teacher conflict check
        teacher_query = Timetable.query.filter(
            Timetable.day_of_week == day_of_week,
            Timetable.teacher_id == teacher_id,
            Timetable.start_time < end_time,
            Timetable.end_time > start_time
        )
        if exclude_id:
            teacher_query = teacher_query.filter(Timetable.id != exclude_id)
            
        teacher_conflict = teacher_query.first()
        if teacher_conflict:
            return False, f"Teacher is already assigned to Batch '{teacher_conflict.batch.name}' between {teacher_conflict.start_time.strftime('%H:%M')} and {teacher_conflict.end_time.strftime('%H:%M')} on {day_of_week}."

        # Batch conflict check
        batch_query = Timetable.query.filter(
            Timetable.day_of_week == day_of_week,
            Timetable.batch_id == batch_id,
            Timetable.start_time < end_time,
            Timetable.end_time > start_time
        )
        if exclude_id:
            batch_query = batch_query.filter(Timetable.id != exclude_id)

        batch_conflict = batch_query.first()
        if batch_conflict:
            return False, f"Batch '{batch_conflict.batch.name}' already has '{batch_conflict.subject.name}' scheduled between {batch_conflict.start_time.strftime('%H:%M')} and {batch_conflict.end_time.strftime('%H:%M')} on {day_of_week}."

        return True, None
