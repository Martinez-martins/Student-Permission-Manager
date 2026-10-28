from django.db import migrations, models


def remove_teacher_role_data(apps, schema_editor):
    StaffRole = apps.get_model('permissions', 'StaffRole')
    UserProfile = apps.get_model('permissions', 'UserProfile')
    ActivationCode = apps.get_model('permissions', 'ActivationCode')

    teacher_role = StaffRole.objects.filter(name='teacher').first()
    if not teacher_role:
        return

    UserProfile.objects.filter(role=teacher_role).update(role=None)
    ActivationCode.objects.filter(role=teacher_role).delete()
    teacher_role.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0009_nurseroomentry'),
    ]

    operations = [
        migrations.RunPython(remove_teacher_role_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='staffrole',
            name='name',
            field=models.CharField(
                choices=[
                    ('security', 'Security'),
                    ('patron', 'Patron'),
                    ('matron', 'Matron'),
                    ('nurse', 'Nurse'),
                    ('staff_member', 'Staff Member'),
                    ('dean', 'Dean'),
                    ('dos', 'Director of Studies'),
                    ('principal', 'Principal'),
                ],
                max_length=20,
                unique=True,
            ),
        ),
    ]
