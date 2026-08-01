from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


def student_is_verified(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True

    profile = getattr(user, "student_profile", None)
    user_email = (user.email or "").strip().lower()
    verified_email = (
        getattr(profile, "verified_email", "") or ""
    ).strip().lower()
    expected_domain = allowed_student_domain()
    verified_domain = (
        verified_email.rsplit("@", 1)[1]
        if "@" in verified_email
        else ""
    )

    return bool(
        profile
        and profile.email_verified_at
        and verified_email
        and verified_email == user_email
        and verified_domain == expected_domain
    )


def verified_student_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if student_is_verified(request.user):
            return view_func(request, *args, **kwargs)

        next_url = request.get_full_path()
        login_url = reverse("home")
        params = urlencode({"auth": "1", "next": next_url})
        return redirect(f"{login_url}?{params}")

    return wrapped


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def allowed_student_domain():
    return getattr(
        settings,
        "BRACU_ALLOWED_EMAIL_DOMAIN",
        "g.bracu.ac.bd",
    ).strip().lower()
