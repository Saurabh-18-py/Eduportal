from django.contrib import admin
from .models import StudentProfile, Avatar


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'class_level', 'avatar', 'created_at')
    list_filter = ('class_level',)


@admin.register(Avatar)
class AvatarAdmin(admin.ModelAdmin):
    list_display = ('name', 'image', 'emoji', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    ordering = ('order', 'id')
