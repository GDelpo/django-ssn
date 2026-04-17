"""
First migration for accounts app.

This migration creates the User model and related tables.

Run with:
    python manage.py migrate accounts
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0001_initial'),  # Django's auth framework
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(blank=True, help_text='Optional field. Email is the primary identifier.', max_length=150, null=True, verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(error_messages={'unique': 'A user with that email already exists.'}, max_length=254, unique=True, verbose_name='email address')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Inactive users cannot log in', verbose_name='active')),
                ('date_joined', models.DateTimeField(auto_now_add=True, verbose_name='date joined')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('external_id', models.CharField(blank=True, help_text='ID from external identity service (if using identity service)', max_length=255, null=True, unique=True)),
                ('is_external_user', models.BooleanField(default=False, help_text='True if user is managed by identity service')),
                ('identity_service_token', models.TextField(blank=True, help_text='JWT token from identity service for API calls', null=True)),
                ('identity_service_token_obtained_at', models.DateTimeField(blank=True, help_text='When the identity service token was obtained', null=True)),
                ('last_login_via', models.CharField(choices=[('local', 'Local Database'), ('identity_service', 'Identity Service'), ('ldap', 'LDAP')], default='local', help_text='Last authentication method used', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to.', related_name='user_set', related_query_name='user', to='auth.Group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.Permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'User',
                'verbose_name_plural': 'Users',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['email'], name='accounts_user_email_idx'),
        ),
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['uuid'], name='accounts_user_uuid_idx'),
        ),
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['external_id'], name='accounts_user_ext_id_idx'),
        ),
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['is_active'], name='accounts_user_active_idx'),
        ),
    ]
