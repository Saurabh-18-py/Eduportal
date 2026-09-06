from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from .models import StudentProfile, Avatar, UploaderAccount, Message

UPLOADER_GROUP_NAME = 'Uploaders'


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'class_level', 'avatar', 'created_at')
    list_filter = ('class_level',)


@admin.register(Avatar)
class AvatarAdmin(admin.ModelAdmin):
    list_display = ('preview', 'name', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    ordering = ('order', 'id')

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;width:40px;border-radius:50%;object-fit:cover;">', obj.image.url)
        if obj.emoji:
            return format_html('<span style="font-size:1.4rem;">{}</span>', obj.emoji)
        return '(no image/emoji)'
    preview.short_description = 'Preview'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'text', 'created_at', 'is_read')
    list_filter = ('is_read',)


@admin.register(UploaderAccount)
class UploaderAccountAdmin(UserAdmin):
    """
    Simplified "Add Uploader" form in the admin. Only asks for username,
    password and (optional) email - no staff/superuser/permission
    checkboxes are ever shown, so there's no way to accidentally grant
    admin access from here. Every user created or edited through this
    screen is forced to is_staff=False, is_superuser=False and placed in
    (only) the 'Uploaders' group.
    """
    list_display = ('username', 'email', 'is_active', 'date_joined')
    list_filter = ('is_active',)
    search_fields = ('username', 'email')
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('email',)}),
        ('Status', {'fields': ('is_active',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email'),
        }),
    )

    def get_queryset(self, request):
        # Only ever list users who are actually Uploaders here - keeps
        # this screen from turning into a general user list.
        return super().get_queryset(request).filter(groups__name=UPLOADER_GROUP_NAME)

    def save_model(self, request, obj, form, change):
        obj.is_staff = False
        obj.is_superuser = False
        super().save_model(request, obj, form, change)
        group, _ = Group.objects.get_or_create(name=UPLOADER_GROUP_NAME)
        obj.groups.set([group])  # only this group - nothing else
