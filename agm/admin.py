from django.contrib import admin
from .models import AGM, AgendaItem, Resolution, Vote, AGMAttendance


class AgendaItemInline(admin.TabularInline):
    model = AgendaItem
    extra = 0


class ResolutionInline(admin.TabularInline):
    model = Resolution
    extra = 0


@admin.register(AGM)
class AGMAdmin(admin.ModelAdmin):
    list_display = ['title', 'year', 'date', 'status', 'attendance_count']
    list_filter = ['status', 'year']
    inlines = [AgendaItemInline, ResolutionInline]


@admin.register(Resolution)
class ResolutionAdmin(admin.ModelAdmin):
    list_display = ['title', 'agm', 'status', 'votes_yes', 'votes_no', 'votes_abstain']
    list_filter = ['status', 'agm']


admin.site.register(Vote)
admin.site.register(AGMAttendance)
