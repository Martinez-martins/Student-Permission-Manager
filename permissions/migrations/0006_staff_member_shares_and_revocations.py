import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0005_permission_parent_final_warning_sent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staffrole',
            name='name',
            field=models.CharField(
                choices=[
                    ('security', 'Security'),
                    ('teacher', 'Teacher'),
                    ('patron', 'Patron'),
                    ('matron', 'Matron'),
                    ('nurse', 'Nurse'),
                    ('staff_member', 'Staff Member'),
                    ('dean', 'Dean'),
                    ('dos', 'Director of Studies'),
                    ('principal', 'Principal'),
                    ('parent', 'Parent'),
                ],
                max_length=20,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='permission',
            name='revocation_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='permission',
            name='revoked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='permission',
            name='revoked_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revoked_permissions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='SharedStudentList',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('names_text', models.TextField(help_text='One name per line.')),
                ('share_type', models.CharField(choices=[('general', 'General'), ('nurse_room', "Nurse Room")], default='general', max_length=20)),
                ('share_token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('allow_public_access', models.BooleanField(default=True)),
                ('is_live', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shared_student_lists', to=settings.AUTH_USER_MODEL)),
                ('shared_with_role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shared_student_lists', to='permissions.staffrole')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
