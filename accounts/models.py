from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('treasurer', 'Treasurer'),
        ('readonly', 'Read Only'),
        ('member', 'Member Portal'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='readonly')
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='staff',
        null=True, blank=True
    )
    # Linked chama member (only set for role='member')
    member = models.OneToOneField(
        'members.Member', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='portal_user'
    )

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_treasurer(self):
        return self.role in ('admin', 'treasurer')

    @property
    def is_readonly(self):
        return self.role == 'readonly'

    @property
    def is_member_portal(self):
        """True only if the user's sole access is the member self-service portal."""
        return self.role == 'member'

    @property
    def has_management_access(self):
        """True if the user can access the management dashboard (including elevated members)."""
        return self.role in ('admin', 'treasurer', 'readonly')
