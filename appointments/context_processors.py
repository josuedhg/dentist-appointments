def roles(request):
    """Expose role flags to every template (used by the navigation bar)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"is_doctor": False, "is_patient": False}
    return {
        "is_doctor": user.groups.filter(name="doctor").exists(),
        "is_patient": user.groups.filter(name="patient").exists(),
    }
