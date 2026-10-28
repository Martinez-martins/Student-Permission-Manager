import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

class StaffRole(models.Model):
    ROLE_CHOICES = [
        ('security', 'Security'),
        ('patron', 'Patron'),
        ('matron', 'Matron'),
        ('nurse', 'Nurse'),
        ('dean', 'Dean'),
        ('dos', 'Director of Studies'),
        ('principal', 'Principal'),
    ]
    name = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()

class ActivationCode(models.Model):
    code = models.CharField(max_length=100, unique=True)
    role = models.ForeignKey(StaffRole, on_delete=models.CASCADE)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.role}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.ForeignKey(StaffRole, on_delete=models.CASCADE, null=True, blank=True)
    is_admin = models.BooleanField(default=False)
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.role or 'Admin'}"

class PermissionType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    allowed_roles = models.ManyToManyField(StaffRole, related_name='allowed_permission_types')

    def __str__(self):
        return self.name

class Permission(models.Model):
    student_name = models.CharField(max_length=100)
    student_class = models.CharField(max_length=50)
    description = models.TextField()
    time = models.DateTimeField(default=timezone.now)
    period = models.DurationField(help_text="Duration of the permission")
    issued_by = models.ForeignKey(User, on_delete=models.CASCADE)
    permission_type = models.ForeignKey(PermissionType, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    visible_to_roles = models.ManyToManyField(StaffRole, related_name='visible_permissions', blank=True)
    visible_to_security = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='revoked_permissions')
    revocation_reason = models.TextField(blank=True)

    def __str__(self):
        return f"Permission for {self.student_name} - {self.permission_type.name}"


class SharedStudentList(models.Model):
    SHARE_TYPE_CHOICES = [
        ('general', 'General'),
        ('nurse_room', "Nurse Room"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    names_text = models.TextField(help_text="One name per line.")
    share_type = models.CharField(max_length=20, choices=SHARE_TYPE_CHOICES, default='general')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_student_lists')
    shared_with_role = models.ForeignKey(StaffRole, on_delete=models.SET_NULL, null=True, blank=True, related_name='shared_student_lists')
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    allow_public_access = models.BooleanField(default=True)
    is_live = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    def individual_names(self):
        return [line.strip() for line in self.names_text.splitlines() if line.strip()]


class NurseRoomEntry(models.Model):
    LEVEL_CHOICES = [
        ('o_level', 'O LEVEL'),
        ('a_level', 'A LEVEL'),
    ]

    nurse = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nurse_room_entries')
    shared_list = models.ForeignKey(SharedStudentList, on_delete=models.CASCADE, related_name='nurse_room_entries')
    student_name = models.CharField(max_length=100)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    student_class = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student_name} - {self.get_level_display()} {self.student_class}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}"
