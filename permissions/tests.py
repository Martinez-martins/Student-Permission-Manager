from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    ActivationCode,
    Notification,
    NurseRoomEntry,
    Permission,
    PermissionType,
    SharedStudentList,
    StaffRole,
)


class SharingWorkflowTests(TestCase):
    def create_user_with_role(self, username, role_name):
        role, _ = StaffRole.objects.get_or_create(name=role_name)
        user = User.objects.create_user(username=username, password='pass1234')
        user.userprofile.is_admin = False
        user.userprofile.role = role
        user.userprofile.save()
        return user

    def test_nurse_can_notify_dean_about_sick_student(self):
        nurse = self.create_user_with_role('nurse1', 'nurse')
        dean = self.create_user_with_role('dean1', 'dean')

        self.client.login(username='nurse1', password='pass1234')
        response = self.client.post(reverse('notify_dean_about_student'), {
            'student_name': 'Jane Doe',
            'student_class': 'S4A',
            'notes': 'Fever and dizziness',
        })

        self.assertRedirects(response, reverse('staff_dashboard'))
        self.assertTrue(
            Notification.objects.filter(user=dean, message__icontains='Jane Doe').exists()
        )

    def test_dean_dashboard_shows_nurse_notifications(self):
        dean = self.create_user_with_role('dean2', 'dean')
        Notification.objects.create(user=dean, message='Nurse alert for Test Student')

        self.client.login(username='dean2', password='pass1234')
        response = self.client.get(reverse('staff_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nurse alert for Test Student')

    def test_dean_notifications_page_shows_alerts(self):
        dean = self.create_user_with_role('dean_page', 'dean')
        Notification.objects.create(user=dean, message='Separate dean page alert')

        self.client.login(username='dean_page', password='pass1234')
        response = self.client.get(reverse('dean_notifications'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Separate dean page alert')

    def test_nurse_room_page_shows_entries(self):
        nurse = self.create_user_with_role('nurse_page', 'nurse')
        self.client.login(username='nurse_page', password='pass1234')
        self.client.post(reverse('manage_nurse_room_share'), {
            'student_name': 'Room Student',
            'level': 'a_level',
            'student_class': 'S6',
            'description': 'Observation',
        })

        response = self.client.get(reverse('nurse_room_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Room Student')
        self.assertContains(response, 'A LEVEL')

    def test_nurse_can_add_structured_sick_room_entry(self):
        nurse = self.create_user_with_role('nurse3', 'nurse')

        self.client.login(username='nurse3', password='pass1234')
        response = self.client.post(reverse('manage_nurse_room_share'), {
            'student_name': 'Alice Doe',
            'level': 'o_level',
            'student_class': 'S3',
            'description': 'Observation',
            'allow_public_access': 'on',
        })

        self.assertRedirects(response, reverse('staff_dashboard'))
        entry = NurseRoomEntry.objects.get(student_name='Alice Doe')
        self.assertEqual(entry.level, 'o_level')
        self.assertEqual(entry.student_class, 'S3')
        self.assertEqual(entry.shared_list.share_type, 'nurse_room')

    def test_dean_can_create_public_shared_list(self):
        self.create_user_with_role('dean_share', 'dean')
        self.client.login(username='dean_share', password='pass1234')
        response = self.client.post(reverse('create_shared_list'), {
            'title': 'Pickup List',
            'description': 'Students ready for pickup',
            'names_text': 'Jane Doe\nJohn Doe',
            'allow_public_access': 'on',
        })

        self.assertRedirects(response, reverse('staff_dashboard'))
        shared_list = SharedStudentList.objects.get(title='Pickup List')
        self.client.logout()
        public_response = self.client.get(reverse('shared_list_public', kwargs={'share_token': shared_list.share_token}))

        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, 'Jane Doe')
        self.assertContains(public_response, 'John Doe')

    def test_public_student_board_shows_sickbay_and_shared_lists(self):
        nurse = self.create_user_with_role('nurse_board', 'nurse')
        dean = self.create_user_with_role('dean_board', 'dean')
        nurse_shared_list = SharedStudentList.objects.create(
            title="Students currently in the nurse's room",
            description='Live sickbay list',
            names_text='',
            share_type='nurse_room',
            created_by=nurse,
            shared_with_role=None,
            allow_public_access=True,
            is_live=True,
        )
        NurseRoomEntry.objects.create(
            nurse=nurse,
            shared_list=nurse_shared_list,
            student_name='Sick Student',
            level='o_level',
            student_class='S2',
        )
        SharedStudentList.objects.create(
            title='Dean Shared Students',
            description='Shared by dean',
            names_text='Shared Student One\nShared Student Two',
            share_type='general',
            created_by=dean,
            shared_with_role=None,
            allow_public_access=True,
        )

        response = self.client.get(reverse('public_student_board'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sick Student')
        self.assertContains(response, 'Dean Shared Students')
        self.assertContains(response, 'Shared Student One')

    def test_user_without_role_home_redirects_to_public_student_board(self):
        user = User.objects.create_user(username='no_role_user', password='pass1234')
        user.userprofile.is_admin = False
        user.userprofile.role = None
        user.userprofile.save()

        self.client.login(username='no_role_user', password='pass1234')
        response = self.client.get(reverse('home'))

        self.assertRedirects(response, reverse('public_student_board'))

    def test_revoking_permission_keeps_audit_record(self):
        nurse = self.create_user_with_role('nurse2', 'nurse')
        permission_type = PermissionType.objects.create(name='Medical Visit', description='Medical movement')
        permission_type.allowed_roles.add(nurse.userprofile.role)
        permission = Permission.objects.create(
            student_name='Patient Zero',
            student_class='S2',
            description='Visit the clinic',
            time=timezone.now(),
            period=timedelta(hours=2),
            issued_by=nurse,
            permission_type=permission_type,
        )

        self.client.login(username='nurse2', password='pass1234')
        response = self.client.post(reverse('delete_permission', kwargs={'permission_id': permission.id}), {
            'revocation_reason': 'Student returned to class',
        })

        self.assertRedirects(response, reverse('staff_dashboard'))
        permission.refresh_from_db()
        self.assertIsNotNone(permission.revoked_at)
        self.assertEqual(permission.revoked_by, nurse)
        self.assertEqual(permission.revocation_reason, 'Student returned to class')

    def test_expired_permission_can_be_deleted_permanently(self):
        nurse = self.create_user_with_role('nurse_expired', 'nurse')
        permission_type = PermissionType.objects.create(name='Expired Visit', description='Expired movement')
        permission_type.allowed_roles.add(nurse.userprofile.role)
        permission = Permission.objects.create(
            student_name='Old Student',
            student_class='S1',
            description='Expired permission',
            time=timezone.now() - timedelta(hours=5),
            period=timedelta(hours=1),
            issued_by=nurse,
            permission_type=permission_type,
        )

        self.client.login(username='nurse_expired', password='pass1234')
        response = self.client.post(reverse('delete_permission', kwargs={'permission_id': permission.id}))

        self.assertRedirects(response, reverse('staff_dashboard'))
        self.assertFalse(Permission.objects.filter(id=permission.id).exists())


class SecurityVisibilityTests(TestCase):
    def create_user_with_role(self, username, role_name):
        role, _ = StaffRole.objects.get_or_create(name=role_name)
        user = User.objects.create_user(username=username, password='pass1234')
        user.userprofile.is_admin = False
        user.userprofile.role = role
        user.userprofile.save()
        return user

    def test_security_sees_only_dean_visible_permissions(self):
        dean = self.create_user_with_role('dean_sec', 'dean')
        security = self.create_user_with_role('security_sec', 'security')
        nurse = self.create_user_with_role('nurse_sec', 'nurse')

        permission_type = PermissionType.objects.create(name='General Movement', description='Move')
        permission_type.allowed_roles.add(dean.userprofile.role, nurse.userprofile.role)

        visible_permission = Permission.objects.create(
            student_name='Dean Visible Student',
            student_class='S2',
            description='Visible to security',
            time=timezone.now(),
            period=timedelta(hours=2),
            issued_by=dean,
            permission_type=permission_type,
            visible_to_security=True,
        )
        hidden_permission = Permission.objects.create(
            student_name='Dean Hidden Student',
            student_class='S3',
            description='Hidden to security',
            time=timezone.now(),
            period=timedelta(hours=2),
            issued_by=dean,
            permission_type=permission_type,
            visible_to_security=False,
        )
        non_dean_permission = Permission.objects.create(
            student_name='Nurse Student',
            student_class='S1',
            description='Not dean-issued',
            time=timezone.now(),
            period=timedelta(hours=2),
            issued_by=nurse,
            permission_type=permission_type,
            visible_to_security=True,  # even if true, security should still not see it
        )

        self.client.login(username='security_sec', password='pass1234')
        response = self.client.get(reverse('security_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, visible_permission.student_name)

        self.assertNotContains(response, hidden_permission.student_name)
        self.assertNotContains(response, non_dean_permission.student_name)

    def test_security_cannot_view_student_board(self):
        self.create_user_with_role('dean_sec_2', 'dean')
        self.create_user_with_role('security_only', 'security')

        self.client.login(username='security_only', password='pass1234')
        response = self.client.get(reverse('public_student_board'))

        # public_student_board redirects security users back to security_dashboard
        self.assertRedirects(response, reverse('security_dashboard'))
