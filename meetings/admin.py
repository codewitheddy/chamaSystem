from django.contrib import admin
from .models import Meeting, Attendance, MeetingPenalty


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0


class PenaltyInline(admin.TabularInline):
    model = MeetingPenalty
    extra = 0


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'venue', 'status', 'attendance_count']
    list_filter = ['status']
    inlines = [AttendanceInline, PenaltyInline]


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'member', 'present', 'notes']
    list_filter = ['present', 'meeting']


@admin.register(MeetingPenalty)
class MeetingPenaltyAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'member', 'reason', 'amount', 'paid']
    list_filter = ['reason', 'paid']
