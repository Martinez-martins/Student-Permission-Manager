from datetime import timedelta
import uuid

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

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

def welcome(request):
    return render(request,'welcome.html')

def developer(request):
    return render(request,'developer.html')

def index(request):
    return render(request,'index.html')


@never_cache
def public_student_board(request):
    # Security personnel must not view the student board.
    if request.user.is_authenticated:
        role = getattr(getattr(request.user, 'userprofile', None), 'role', None)
        role_name = str(getattr(role, 'name', '') or '').strip().lower()
        role_display = str(getattr(role, 'get_name_display', lambda: '')() or '').strip().lower()
        if role_name == 'security' or role_display == 'security':
            return redirect('security_dashboard')

    sickbay_entries = list(
        NurseRoomEntry.objects.filter(
            shared_list__share_type='nurse_room',
            shared_list__is_live=True
        )
        .select_related('nurse')
        .order_by('-created_at')
    )
    shared_lists = list(
        SharedStudentList.objects.filter(allow_public_access=True)
        .exclude(share_type='nurse_room')
        .select_related('created_by', 'shared_with_role')
        .order_by('-updated_at')
    )
    for shared_list in shared_lists:
        shared_list.names = shared_list.individual_names()
    return render(request, 'permissions/public_student_board.html', {
        'sickbay_entries': sickbay_entries,
        'shared_lists': shared_lists,
    })

@never_cache
def home(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'userprofile'):
            profile = request.user.userprofile
            if profile.is_admin:
                return redirect('admin_dashboard')
            elif profile.role and profile.role.name == 'security':
                return redirect('security_dashboard')
            elif not profile.role:
                return redirect('public_student_board')
            else:
                return redirect('staff_dashboard')
        else:
            return redirect('public_student_board')
    else:
        # Show landing page for non-authenticated users
        return render(request, 'permissions/home.html')

def is_admin(user):
    return user.userprofile.is_admin if hasattr(user, 'userprofile') else False

def is_super_admin(user):
    return bool(user and user.is_authenticated and user.is_superuser)

def is_staff(user):
    return (
        hasattr(user, 'userprofile')
        and not user.userprofile.is_admin
        and user.userprofile.role is not None
    )

def is_security(user):
    return (
        hasattr(user, 'userprofile')
        and user.userprofile.role
        and (str(user.userprofile.role.name or '').strip().lower() == 'security')
    )


def is_nurse(user):
    return hasattr(user, 'userprofile') and user.userprofile.role and user.userprofile.role.name == 'nurse'


def is_dean(user):
    return hasattr(user, 'userprofile') and user.userprofile.role and user.userprofile.role.name == 'dean'


def can_share_with_staff_members(user):
    if not user or not user.is_authenticated or not hasattr(user, 'userprofile'):
        return False
    profile = user.userprofile
    if profile.is_admin:
        return True
    if not profile.role:
        return False
    return profile.role.name != 'security'


def attach_permission_state(permission, now):
    try:
        permission.end_time = permission.time + permission.period
        permission.is_revoked = bool(permission.revoked_at)
        permission.is_active = permission.end_time > now and not permission.is_revoked

        # Countdown support (used by admin dashboard)
        if permission.end_time and permission.end_time > now and not permission.is_revoked:
            permission.remaining_seconds = int((permission.end_time - now).total_seconds())
        else:
            permission.remaining_seconds = 0
    except Exception:
        permission.end_time = None
        permission.is_revoked = False
        permission.is_active = False
        permission.remaining_seconds = 0
    return permission


def can_access_permissions_overview(user):
    if not user or not user.is_authenticated or not hasattr(user, 'userprofile'):
        return False
    profile = user.userprofile
    if profile.is_admin:
        return True
    if not profile.role:
        return False
    return profile.role.name != 'security'


def can_view_internal_pages(user):
    if not user or not user.is_authenticated or not hasattr(user, 'userprofile'):
        return False
    profile = user.userprofile
    if profile.is_admin:
        return True
    return bool(profile.role)


@login_required
@user_passes_test(can_access_permissions_overview)
@never_cache
def all_permissions(request):
    permissions = list(Permission.objects.select_related('permission_type', 'issued_by').order_by('-created_at'))
    now = timezone.now()
    for p in permissions:
        attach_permission_state(p, now)
    return render(request, 'permissions/all_permissions.html', {
        'permissions': permissions,
        'now': now,
    })

@login_required
@user_passes_test(is_admin)
@never_cache
def admin_dashboard(request):
    roles = StaffRole.objects.all()
    codes = ActivationCode.objects.filter(is_used=False)
    permission_types = PermissionType.objects.all()
    permissions = list(Permission.objects.all().order_by('-created_at'))
    now = timezone.now()

    for p in permissions:
        attach_permission_state(p, now)

    return render(request, 'permissions/admin_dashboard.html', {
        'roles': roles,
        'codes': codes,
        'permission_types' : permission_types,
        'permissions': permissions,
        'now': now,
        'can_generate_codes': request.user.is_superuser,
    })

@login_required
@user_passes_test(is_admin)
def create_staff_role(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name and name not in [choice[0] for choice in StaffRole.ROLE_CHOICES]:
            messages.error(request, 'Invalid role name.')
            return redirect('admin_dashboard')
        role, created = StaffRole.objects.get_or_create(name=name)
        if created:
            messages.success(request, f'Role {role.get_name_display()} created successfully.')
        else:
            messages.info(request, f'Role {role.get_name_display()} already exists.')
        return redirect('admin_dashboard')
    return redirect('admin_dashboard')

@login_required
@user_passes_test(is_super_admin)
def generate_activation_code(request):
    if request.method == 'POST':
        role_id = request.POST.get('role')
        role = get_object_or_404(StaffRole, id=role_id)
        code = str(uuid.uuid4())
        ActivationCode.objects.create(code=code, role=role)
        messages.success(request, f'Activation code generated for {role.get_name_display()}: {code}')
        return redirect('admin_dashboard')
    return redirect('admin_dashboard')

@login_required
@user_passes_test(is_admin)
def create_permission_type(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        allowed_roles_ids = request.POST.getlist('allowed_roles')
        if name:
            permission_type, created = PermissionType.objects.get_or_create(name=name, defaults={'description': description})
            if created:
                permission_type.allowed_roles.set(allowed_roles_ids)
                messages.success(request, f'Permission type "{name}" created successfully.')
            else:
                messages.info(request, f'Permission type "{name}" already exists.')
        return redirect('admin_dashboard')
    return redirect('admin_dashboard')

@login_required
@user_passes_test(is_staff)
@never_cache
def staff_dashboard(request):
    user_profile = request.user.userprofile
    if user_profile.is_admin:
        return redirect('admin_dashboard')
    if user_profile.role and user_profile.role.name == 'security':
        return redirect('security_dashboard')

    # Get permission types the user can issue
    allowed_permission_types = PermissionType.objects.filter(allowed_roles=user_profile.role)
    
    # Get permissions issued by this user
    issued_permissions = list(Permission.objects.filter(issued_by=request.user).order_by('-created_at'))
    notifications = list(request.user.notifications.all()[:5])
    shared_lists = list(
        SharedStudentList.objects.filter(created_by=request.user)
        .select_related('shared_with_role')
        .order_by('-updated_at')
    )
    nurse_room_share = None
    nurse_room_entries = []
    now = timezone.now()
    # attach computed fields for template use
    for p in issued_permissions:
        attach_permission_state(p, now)
    for shared_list in shared_lists:
        shared_list.names = shared_list.individual_names()
        if shared_list.share_type == 'nurse_room' and shared_list.is_live and nurse_room_share is None:
            nurse_room_share = shared_list
            nurse_room_entries = list(shared_list.nurse_room_entries.all())
        else:
            shared_list.share_url = request.build_absolute_uri(
                reverse('shared_list_public', kwargs={'share_token': shared_list.share_token})
            )

    return render(request, 'permissions/staff_dashboard.html', {
        'allowed_permission_types': allowed_permission_types,
        'issued_permissions': issued_permissions,
        'notifications': notifications,
        'unread_notifications_count': request.user.notifications.filter(is_read=False).count(),
        'shared_lists': shared_lists,
        'nurse_room_share': nurse_room_share,
        'nurse_room_entries': nurse_room_entries,
        'now': now,
    })


@login_required
@user_passes_test(can_view_internal_pages)
@never_cache
def nurse_room_list(request):
    nurse_room_lists = SharedStudentList.objects.filter(share_type='nurse_room', is_live=True)
    entries = list(
        NurseRoomEntry.objects.filter(shared_list__in=nurse_room_lists)
        .select_related('nurse', 'shared_list')
        .order_by('-created_at')
    )
    return render(request, 'permissions/nurse_room_list.html', {
        'entries': entries,
        'now': timezone.now(),
    })


@login_required
@user_passes_test(is_dean)
@never_cache
def dean_notifications(request):
    notifications = list(request.user.notifications.all())
    return render(request, 'permissions/dean_notifications.html', {
        'notifications': notifications,
        'unread_notifications_count': request.user.notifications.filter(is_read=False).count(),
    })

@login_required
@user_passes_test(is_staff)
@never_cache
def issue_permission(request):
    user_profile = request.user.userprofile
    if user_profile.is_admin:
        return redirect('admin_dashboard')

    if user_profile.role and user_profile.role.name == 'security':
        messages.error(request, 'Security personnel cannot issue permissions.')
        return redirect('staff_dashboard')

    allowed_permission_types = PermissionType.objects.filter(allowed_roles=user_profile.role)

    if request.method == 'POST':
        student_name = request.POST.get('student_name')
        student_class = request.POST.get('student_class')
        description = request.POST.get('description')
        permission_type_id = request.POST.get('permission_type')
        try:
            hours = int(request.POST.get('hours', 1))
        except (TypeError, ValueError):
            hours = 1
        if hours < 1:
            hours = 1

        # Only dean can decide visibility to security
        visible_to_security = False
        try:
            if user_profile.role and user_profile.role.name == 'dean':
                visible_to_security = True if request.POST.get('visible_to_security') == 'on' else False
        except Exception:
            visible_to_security = False

        permission_type = get_object_or_404(PermissionType, id=permission_type_id)

        if permission_type not in allowed_permission_types:
            messages.error(request, 'You are not authorized to issue this type of permission.')
            return redirect('issue_permission')

        period = timedelta(hours=hours)
        Permission.objects.create(
            student_name=student_name,
            student_class=student_class,
            description=description,
            period=period,
            issued_by=request.user,
            permission_type=permission_type,
            visible_to_security=visible_to_security,
        )
        messages.success(request, 'Permission issued successfully.')
        return redirect('staff_dashboard')

    return render(request, 'permissions/issue_permission.html', {
        'allowed_permission_types': allowed_permission_types,
        'user_profile': user_profile,
    })

@login_required
@user_passes_test(is_staff)
@never_cache
def edit_permission(request, permission_id):
    user_profile = request.user.userprofile
    if user_profile.is_admin:
        return redirect('admin_dashboard')

    # Get the permission and ensure it belongs to the current user
    permission = get_object_or_404(Permission, id=permission_id, issued_by=request.user)

    # Check if permission is still editable (not expired)
    if permission.revoked_at:
        messages.error(request, 'Cannot edit a revoked permission.')
        return redirect('staff_dashboard')
    if permission.time + permission.period <= timezone.now():
        messages.error(request, 'Cannot edit expired permissions.')
        return redirect('staff_dashboard')

    allowed_permission_types = PermissionType.objects.filter(allowed_roles=user_profile.role)
    if request.method == 'POST':
        student_name = request.POST.get('student_name')
        student_class = request.POST.get('student_class')
        description = request.POST.get('description')
        permission_type_id = request.POST.get('permission_type')
        try:
            hours = int(request.POST.get('hours', 1))
        except (TypeError, ValueError):
            hours = 1
        if hours < 1:
            hours = 1

        permission_type = get_object_or_404(PermissionType, id=permission_type_id)

        if permission_type not in allowed_permission_types:
            messages.error(request, 'You are not authorized to use this type of permission.')
            return redirect('edit_permission', permission_id=permission.id)

        # Update the permission
        permission.student_name = student_name
        permission.student_class = student_class
        permission.description = description
        permission.period = timedelta(hours=hours)
        permission.permission_type = permission_type
        # Allow dean to toggle visibility to security
        try:
            if user_profile.role and user_profile.role.name == 'dean':
                permission.visible_to_security = True if request.POST.get('visible_to_security') == 'on' else False
        except Exception:
            pass
        permission.save()

        messages.success(request, 'Permission updated successfully.')
        return redirect('staff_dashboard')

    return render(request, 'permissions/edit_permission.html', {
        'permission': permission,
        'allowed_permission_types': allowed_permission_types,
        'user_profile': user_profile,
        'duration_hours': max(1, int(permission.period.total_seconds() // 3600)),
    })

@login_required
@user_passes_test(is_staff)
@never_cache
def delete_permission(request, permission_id):
    user_profile = request.user.userprofile
    if user_profile.is_admin:
        return redirect('admin_dashboard')

    # Get the permission and ensure it belongs to the current user
    permission = get_object_or_404(Permission, id=permission_id, issued_by=request.user)

    if permission.revoked_at:
        messages.info(request, 'This permission has already been revoked.')
        return redirect('staff_dashboard')

    now = timezone.now()
    is_expired = permission.time + permission.period <= now

    if request.method == 'POST':
        if is_expired:
            permission.delete()
            messages.success(request, 'Expired permission deleted permanently.')
        else:
            permission.revoked_at = now
            permission.revoked_by = request.user
            permission.revocation_reason = request.POST.get('revocation_reason', '').strip()
            permission.save(update_fields=['revoked_at', 'revoked_by', 'revocation_reason'])
            messages.success(request, 'Permission revoked successfully.')
        return redirect('staff_dashboard')

    return render(request, 'permissions/delete_permission.html', {
        'permission': permission,
        'is_expired': is_expired,
    })

@login_required
@user_passes_test(is_security)
@never_cache
def security_dashboard(request):
    # Security can only view permissions explicitly made visible by the Dean
    dean_role = StaffRole.objects.filter(name='dean').first()
    if not dean_role:
        return render(request, 'permissions/security_dashboard.html', {'permissions': [], 'now': timezone.now()})

    dean_users = UserProfile.objects.filter(role=dean_role).values_list('user', flat=True)

    permissions = list(
        Permission.objects.filter(
            issued_by__in=dean_users,
            visible_to_security=True,
        ).order_by('-created_at')
    )

    now = timezone.now()
    for p in permissions:
        attach_permission_state(p, now)

    return render(request, 'permissions/security_dashboard.html', {
        'permissions': permissions,
        'now': now,
    })


@login_required
@user_passes_test(can_share_with_staff_members)
@never_cache
def create_shared_list(request):
    if request.method != 'POST':
        return redirect('staff_dashboard')

    title = (request.POST.get('title') or '').strip()
    description = (request.POST.get('description') or '').strip()
    names_text = (request.POST.get('names_text') or '').strip()
    allow_public_access = request.POST.get('allow_public_access') == 'on'

    if not title or not names_text:
        messages.error(request, 'Title and at least one individual name are required to create a shared list.')
        return redirect('staff_dashboard')

    shared_list = SharedStudentList.objects.create(
        title=title,
        description=description,
        names_text=names_text,
        share_type='general',
        created_by=request.user,
        shared_with_role=request.user.userprofile.role,
        allow_public_access=allow_public_access,
    )
    share_url = request.build_absolute_uri(reverse('shared_list_public', kwargs={'share_token': shared_list.share_token}))
    messages.success(request, f'Shared list created. Read-only link: {share_url}')
    return redirect('staff_dashboard')


from django.http import HttpResponse
import csv

@login_required
def download_shared_list(request, pk):
    """Download shared list as CSV"""
    shared_list = get_object_or_404(SharedStudentList, pk=pk, created_by=request.user)
    names = shared_list.individual_names()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{shared_list.title.replace(" ", "_")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student Names'])
    writer.writerows([[name] for name in names])
    
    return response


@login_required
@user_passes_test(is_nurse)
@never_cache
def manage_nurse_room_share(request):
    if request.method != 'POST':
        return redirect('staff_dashboard')

    description = (request.POST.get('description') or '').strip()
    allow_public_access = request.POST.get('allow_public_access') == 'on'
    student_name = (request.POST.get('student_name') or '').strip()
    level = (request.POST.get('level') or '').strip()
    student_class = (request.POST.get('student_class') or '').strip()
    shared_list, created = SharedStudentList.objects.get_or_create(
        created_by=request.user,
        share_type='nurse_room',
        is_live=True,
        defaults={
            'title': "Students currently in the nurse's room",
            'description': description,
            'names_text': '',
            'allow_public_access': allow_public_access,
        },
    )

    if not created:
        shared_list.description = description
        shared_list.allow_public_access = allow_public_access
        shared_list.save(update_fields=['description', 'allow_public_access', 'updated_at'])

    if student_name and level and student_class:
        if level not in dict(NurseRoomEntry.LEVEL_CHOICES):
            messages.error(request, 'Select a valid level for the sick room entry.')
            return redirect('staff_dashboard')
        NurseRoomEntry.objects.create(
            nurse=request.user,
            shared_list=shared_list,
            student_name=student_name,
            level=level,
            student_class=student_class,
        )
    elif any([student_name, level, student_class]):
        messages.error(request, 'Student name, level, and class are all required for a sick room entry.')
        return redirect('staff_dashboard')

    sync_nurse_room_share(shared_list)

    messages.success(request, 'Nurse room list updated.')
    return redirect('staff_dashboard')


def sync_nurse_room_share(shared_list):
    entries = shared_list.nurse_room_entries.all()
    shared_list.names_text = '\n'.join(
        f"{entry.student_name} - {entry.get_level_display()} - {entry.student_class}" for entry in entries
    )
    shared_list.save(update_fields=['names_text', 'updated_at'])


@login_required
@user_passes_test(is_nurse)
@never_cache
def remove_nurse_room_entry(request, entry_id):
    entry = get_object_or_404(NurseRoomEntry, id=entry_id, nurse=request.user)
    shared_list = entry.shared_list
    if request.method == 'POST':
        entry.delete()
        sync_nurse_room_share(shared_list)
        messages.success(request, 'Student removed from the sick room list.')
    return redirect('staff_dashboard')


@login_required
@user_passes_test(is_nurse)
@never_cache
def notify_dean_about_student(request):
    if request.method != 'POST':
        return redirect('staff_dashboard')

    student_name = (request.POST.get('student_name') or '').strip()
    student_class = (request.POST.get('student_class') or '').strip()
    notes = (request.POST.get('notes') or '').strip()

    if not student_name or not student_class:
        messages.error(request, 'Student name and class are required before notifying the Dean.')
        return redirect('staff_dashboard')

    dean_profiles = UserProfile.objects.filter(role__name='dean').select_related('user')
    if not dean_profiles.exists():
        messages.error(request, 'No Dean account is currently available to receive this notification.')
        return redirect('staff_dashboard')

    sender_name = request.user.get_full_name() or request.user.username
    message = (
        f"Nurse alert from {sender_name}: {student_name} ({student_class}) is sick."
        f"{' Notes: ' + notes if notes else ''}"
    )
    for profile in dean_profiles:
        Notification.objects.create(user=profile.user, message=message)

    messages.success(request, 'The Dean has been notified about the sick student.')
    return redirect('staff_dashboard')


@login_required
@never_cache
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    if request.method == 'POST':
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    next_page = request.POST.get('next_page') or 'staff_dashboard'
    return redirect(next_page)


@never_cache
def shared_list_public_view(request, share_token):
    shared_list = get_object_or_404(
        SharedStudentList.objects.select_related('created_by', 'shared_with_role'),
        share_token=share_token,
        allow_public_access=True,
    )
    return render(request, 'permissions/shared_list_public.html', {
        'shared_list': shared_list,
        'names': shared_list.individual_names(),
        'nurse_room_entries': list(shared_list.nurse_room_entries.all()) if shared_list.share_type == 'nurse_room' else [],
    })

@login_required
def logout_view(request):
    """Custom logout view with success message"""
    auth_logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('home')

@ensure_csrf_cookie
@never_cache
def register_staff(request):
    if request.method == 'POST':
        selected_role = request.POST.get('staff_role')
        username = request.POST.get('username')
        password = request.POST.get('password')
        activation_code = request.POST.get('activation_code')

        try:
            code = ActivationCode.objects.get(code=activation_code, is_used=False)
            if selected_role and code.role.name != selected_role.lower():
                messages.error(request, 'Activation code does not match the selected role.')
                return redirect('register_staff')
            if code.role.name == 'teacher':
                messages.error(request, 'Teacher accounts are no longer supported in this system.')
                return redirect('register_staff')
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
                return redirect('register_staff')

            user = User.objects.create_user(username=username, password=password)
            # Update the UserProfile that was created by the signal
            user_profile = user.userprofile
            user_profile.role = code.role
            user_profile.is_admin = False  # Ensure it's not an admin
            user_profile.save()

            code.is_used = True
            code.save()
            messages.success(request, 'Account created successfully. Please login.')
            return redirect('login')
        except ActivationCode.DoesNotExist:
            messages.error(request, 'Invalid or used activation code.')
            return redirect('register_staff')

    return render(request, 'permissions/register_staff.html')

@ensure_csrf_cookie
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        identifier = (request.POST.get('username') or '').strip()
        password = request.POST.get('password')
        user = authenticate(request, username=identifier, password=password)

        if user:
            auth_login(request, user)
            return redirect('home')

        messages.error(request, 'Invalid login credentials.')
        return redirect('login')

    return render(request, 'permissions/login.html')
