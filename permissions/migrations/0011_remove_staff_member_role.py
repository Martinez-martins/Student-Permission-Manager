from django.db import migrations, models
import django.db.models.deletion


def remove_staff_member_role_data(apps, schema_editor):
    StaffRole = apps.get_model('permissions', 'StaffRole')
    UserProfile = apps.get_model('permissions', 'UserProfile')
    ActivationCode = apps.get_model('permissions', 'ActivationCode')
    SharedStudentList = apps.get_model('permissions', 'SharedStudentList')

    staff_member_role = StaffRole.objects.filter(name='staff_member').first()
    if not staff_member_role:
        return

    UserProfile.objects.filter(role=staff_member_role).update(role=None)
    ActivationCode.objects.filter(role=staff_member_role).delete()
    SharedStudentList.objects.filter(shared_with_role=staff_member_role).update(shared_with_role=None)
    staff_member_role.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0010_remove_teacher_role_and_add_public_board'),
    ]

    operations = [
        migrations.RunPython(remove_staff_member_role_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='staffrole',
            name='name',
            field=models.CharField(
                choices=[
                    ('security', 'Security'),
                    ('patron', 'Patron'),
                    ('matron', 'Matron'),
                    ('nurse', 'Nurse'),
                    ('dean', 'Dean'),
                    ('dos', 'Director of Studies'),
                    ('principal', 'Principal'),
                ],
                max_length=20,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name='sharedstudentlist',
            name='shared_with_role',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shared_student_lists', to='permissions.staffrole'),
        ),
    ]
