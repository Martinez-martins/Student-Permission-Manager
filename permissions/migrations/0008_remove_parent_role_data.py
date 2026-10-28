from django.db import migrations


def remove_parent_role_data(apps, schema_editor):
    StaffRole = apps.get_model('permissions', 'StaffRole')
    UserProfile = apps.get_model('permissions', 'UserProfile')
    ActivationCode = apps.get_model('permissions', 'ActivationCode')

    parent_role = StaffRole.objects.filter(name='parent').first()
    if not parent_role:
        return

    UserProfile.objects.filter(role=parent_role).update(role=None)
    ActivationCode.objects.filter(role=parent_role).delete()
    parent_role.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0007_remove_permission_parent_account_and_more'),
    ]

    operations = [
        migrations.RunPython(remove_parent_role_data, migrations.RunPython.noop),
    ]
