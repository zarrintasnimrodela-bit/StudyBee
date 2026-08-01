from .authentication import student_is_verified
from .models import student_name_from_email


def student_session(request):
    verified = student_is_verified(request.user)
    email = (request.user.email or "") if verified else ""
    return {
        "student_verified": verified,
        "student_display_name": student_name_from_email(email),
    }
