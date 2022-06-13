"""Models for Authentication Service."""

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)

from django.db import models
from django.utils import timezone
from django.core.validators import MinLengthValidator
from django.utils.translation import gettext_lazy as _

from api.choices import ACTION_CHOICES


class UserManager(BaseUserManager):
    """Class Representing create operations for User."""

    def create_user(self, email, password=None, **kwargs):
        """Create an user."""

        user = self.model(email=email, **kwargs)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **kwargs):
        """Create a superuser."""

        user = self.model(email=email, is_staff=True, is_active=True, is_superuser=True, **kwargs)
        user.set_password(password)
        user.save()
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Class representing an user."""

    first_name = models.CharField(_('first name'), max_length=30, blank=False)
    last_name = models.CharField(_('last name'), max_length=150, blank=False)
    email = models.EmailField(_('email address'), blank=False, unique=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_(
            'Designates whether the user can log into this admin'
            ' site.',
        ),
    )
    is_active = models.BooleanField(
        _('active'),
        default=False,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Un Select this instead of deleting accounts.',
        ),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    profile_pic = models.ImageField(blank=True, null=True)
    address = models.TextField(null=True, blank=True)
    _favourite_projects = models.TextField(null=True, blank=True)
    _favourite_boards = models.TextField(null=True, blank=True, unique=True)
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        """Meta class for database table name."""

        db_table = 'users'

    @property
    def favourite_projects(self):
        if self._favourite_projects:
            return self._favourite_projects.split(',')
        else:
            return []

    @favourite_projects.setter
    def favourite_projects(self, value):
        if value:
            value = ",".join(value)
        else:
            value = ""
        self._favourite_projects = value

    @property
    def favourite_boards(self):
        if self._favourite_boards:
            return self._favourite_boards.split(',')
        else:
            return []

    @favourite_boards.setter
    def favourite_boards(self, value):
        if value:
            value = ",".join(value)
        else:
            value = ""
        self._favourite_boards = value

    def __str__(self):
        """Format the user email."""

        return "@{}".format(self.email)

    @property
    def full_name(self):
        """Format full name of an user."""

        return "{} {}".format(self.first_name, self.last_name)


class Permission(models.Model):
    """Class representing a permission."""

    name = models.CharField(max_length=48, null=False, blank=False, unique=True)
    code = models.CharField(max_length=48, null=False, blank=False, unique=True)

    def __str__(self):
        """Format the permission name."""

        return self.name


class ProjectType(models.Model):
    """Class representing a project type."""

    name = models.CharField(max_length=65, null=False, blank=False, unique=True)
    created_by = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)


class Country(models.Model):
    """Class representing a project country"""

    name = models.CharField(max_length=128, null=False, blank=False, unique=True)
    country_code = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name',)


class State(models.Model):
    """Class representing state of the project"""
    name = models.CharField(max_length=128, null=False, blank=False)
    country = models.ForeignKey(Country, related_name='states',
                                on_delete=models.CASCADE, null=False, blank=False)

    def __str__(self):
        return self.name


class City(models.Model):
    """Class representing a project State and City"""

    name = models.CharField(max_length=128, null=True, blank=True)
    zip_code = models.IntegerField(null=True, blank=True)
    state = models.ForeignKey(State, related_name='cities',
                                on_delete=models.CASCADE, null=False, blank=False)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name',)


class Project(models.Model):
    """Class representing a project."""

    name = models.CharField(max_length=128, null=False, blank=False, unique=False)
    address = models.TextField(null=True, blank=True)
    city = models.ForeignKey(City, related_name='projects',
                             on_delete=models.CASCADE, blank=False, unique=False)
    type = models.ForeignKey(ProjectType, related_name='projects', on_delete=models.CASCADE)
    year = models.IntegerField(null=True)
    cover_image = models.FileField(null=False, blank=False)
    members = models.ManyToManyField(User, through='ProjectMember')
    start_date = models.DateField(null=False, blank=False)
    estimated_completion_date = models.DateField(null=False, blank=False)
    created_at = models.DateTimeField(null=False, blank=False, auto_now_add=True)

    def __str__(self):
        """Format Project name."""

        return self.name

    def has_permission(self, user, permission_code):
        try:
            project_member = self.project_members.all().get(user=user)
            if project_member.is_admin:
                return True
            else:
                return permission_code in list(project_member.permissions.all().values_list('code', flat=True))
        except ProjectMember.DoesNotExist:
            return False

    def is_admin(self, user):
        try:
            project_member = self.project_members.all().get(user=user)
            return project_member.is_admin
        except ProjectMember.DoesNotExist:
            return False


class ProjectMember(models.Model):
    """Mapping between project and a user."""

    project = models.ForeignKey(Project, related_name='project_members', on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, related_name='user_projects', on_delete=models.CASCADE)
    role = models.CharField(max_length=48, null=False, blank=False)
    invited_on = models.DateTimeField(null=False, blank=False, auto_now_add=True,)
    permissions = models.ManyToManyField(Permission)
    is_admin = models.BooleanField(default=False)

    class Meta(object):
        """Meta class for Project Member."""

        unique_together = (('project', 'user'),)

    def __str__(self):
        """Format project, user and role."""

        return "{}-{}-{}".format(self.project, self.user, self.role)


class Token(models.Model):
    """Class representing a token. Used for reset password, signup."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tokens')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    expires_at = models.DateTimeField(_('expires at'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    token = models.TextField(_('token'), validators=[MinLengthValidator(64)], unique=True)

    def __str__(self):
        """Format user, action and token."""

        return "{}-{}-{}".format(self.user, self.action, self.token)


class Page(models.Model):
    """For static pages"""

    name = models.CharField(max_length=100, blank=False, null=False, unique=True)
    content = models.TextField(blank=True, null=True)


from api.signal_receivers import *
