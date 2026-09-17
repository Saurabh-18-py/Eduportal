from django.contrib import admin
from .models import DoubtMessage


@admin.register(DoubtMessage)
class DoubtMessageAdmin(admin.ModelAdmin):
    list_display = ('student', 'role', 'short_content', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('student__username', 'content')

    def short_content(self, obj):
        return obj.content[:80]
    short_content.short_description = 'Content'
