from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'get_institution', 'is_staff', 'date_joined')
    list_select_related = ('profile',)

    def get_institution(self, instance):
        return instance.profile.institution if hasattr(instance, 'profile') else ''
    get_institution.short_description = 'Institution'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
