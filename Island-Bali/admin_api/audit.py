from .models import AdminActivityLog


def log_admin_activity(
    request,
    action: str,
    entity_name: str,
    entity_id: str = "",
    summary: str = "",
    changes: dict = None,
    actor=None,
):
    """
    Утилита для сохранения записи в журнал действий администратора.
    """
    user = actor if actor is not None else getattr(request, 'user', None)
    if user and not user.is_authenticated:
        user = None

    ip_address = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')

    return AdminActivityLog.objects.create(
        user=user,
        action=action,
        entity_name=entity_name,
        entity_id=str(entity_id),
        summary=summary or f"{action} on {entity_name} #{entity_id}",
        changes=changes or {},
        ip_address=ip_address,
    )
