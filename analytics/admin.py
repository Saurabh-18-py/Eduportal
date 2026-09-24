from django.contrib import admin

from .models import PageVisit, IPLocationCache


@admin.register(PageVisit)
class PageVisitAdmin(admin.ModelAdmin):
    list_display = ('path', 'city', 'country', 'ip_address', 'user', 'timestamp')
    list_filter = ('country', 'timestamp')
    search_fields = ('path', 'ip_address', 'city', 'country', 'user__username')
    readonly_fields = [f.name for f in PageVisit._meta.fields]
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False


@admin.register(IPLocationCache)
class IPLocationCacheAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'city', 'country', 'looked_up_at')
    search_fields = ('ip_address', 'city', 'country')
    readonly_fields = [f.name for f in IPLocationCache._meta.fields]

    def has_add_permission(self, request):
        return False
