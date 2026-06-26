from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from members.models import Member


class PhoneNumberBackend(ModelBackend):
    """
    Allows chama members to log in using their phone number.
    Tries multiple username formats that the portal account creation may have used.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        raw = (username or '').strip()
        chama = getattr(request, 'chama', None) if request else None

        # Build candidate usernames to try
        candidates = _phone_variants(raw)

        # Also try phone.chama_slug variants if chama is known
        if chama:
            for variant in list(candidates):
                candidates.add(f"{variant}.{chama.slug}")

        user = None

        # 1. Try to find User directly by username (handles all creation formats)
        for candidate in candidates:
            try:
                u = User.objects.get(username=candidate)
                profile = getattr(u, 'profile', None)
                if profile and profile.role == 'member':
                    # Verify the member belongs to the correct chama
                    if chama and profile.member and profile.member.chama != chama:
                        continue
                    user = u
                    break
            except User.DoesNotExist:
                continue

        # 2. Fall back: look up Member by phone, then get portal user
        if user is None:
            member = _find_member_by_phone(raw, chama)
            if member:
                try:
                    profile = member.portal_user  # UserProfile
                    user = profile.user
                except Exception:
                    user = None

        if user is None:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


def _phone_variants(phone: str) -> set:
    """Return a set of phone number formats to try as usernames."""
    phone = phone.strip().replace(' ', '').replace('-', '')
    variants = {phone}

    # 0712... → 254712... and +254712...
    if phone.startswith('0') and len(phone) == 10:
        intl = '254' + phone[1:]
        variants.add(intl)
        variants.add('+' + intl)

    # 254... → +254... and 0...
    if phone.startswith('254') and not phone.startswith('+'):
        variants.add('+' + phone)
        if len(phone) == 12:
            variants.add('0' + phone[3:])

    # +254... → 254... and 0...
    if phone.startswith('+254'):
        variants.add(phone[1:])   # 254...
        if len(phone) == 13:
            variants.add('0' + phone[4:])  # 0712...

    return variants


def _find_member_by_phone(phone: str, chama=None):
    """Search for a Member by any phone variant."""
    for variant in _phone_variants(phone):
        try:
            qs = Member.objects.filter(phone=variant)
            if chama:
                qs = qs.filter(chama=chama)
            return qs.get()
        except (Member.DoesNotExist, Member.MultipleObjectsReturned):
            continue
    return None
