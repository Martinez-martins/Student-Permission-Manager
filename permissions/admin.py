from django.contrib import admin

from .models import (
    ActivationCode,
    Notification,
    NurseRoomEntry,
    Permission,
    PermissionType,
    SharedStudentList,
    StaffRole,
    UserProfile,
)

admin.site.register(StaffRole)
admin.site.register(ActivationCode)
admin.site.register(UserProfile)
admin.site.register(PermissionType)
admin.site.register(Permission)
admin.site.register(SharedStudentList)
admin.site.register(NurseRoomEntry)
admin.site.register(Notification)
