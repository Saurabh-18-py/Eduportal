from django.contrib import admin
from .models import Subject, Chapter, Note, PYQPaper


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 1


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'class_level', 'board')
    list_filter = ('class_level', 'board')
    inlines = [ChapterInline]


class NoteInline(admin.TabularInline):
    model = Note
    extra = 1


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'order')
    list_filter = ('subject',)
    inlines = [NoteInline]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'chapter', 'uploaded_at')


@admin.register(PYQPaper)
class PYQPaperAdmin(admin.ModelAdmin):
    list_display = ('subject', 'year', 'class_level', 'set_label', 'uploaded_at')
    list_filter = ('class_level', 'year', 'subject')
