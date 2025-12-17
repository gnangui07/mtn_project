import logging

from celery.result import AsyncResult
from django.http import JsonResponse
from django.core.cache import cache

logger = logging.getLogger(__name__)


def _user_tasks_cache_key(user_id: int) -> str:
    return f"user_tasks_{user_id}"


def register_user_task(user_id: int, task_id: str, task_type: str, ttl_seconds: int = 3600) -> None:
    """Enregistre une tâche Celery lancée par un utilisateur pour permettre le polling côté UI."""
    try:
        key = _user_tasks_cache_key(user_id)
        tasks = cache.get(key) or []

        tasks.append(
            {
                "task_id": task_id,
                "task_type": task_type,
            }
        )

        # Dédupliquer par task_id en gardant le dernier
        seen = set()
        deduped = []
        for item in reversed(tasks):
            tid = item.get("task_id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            deduped.append(item)
        tasks = list(reversed(deduped))

        cache.set(key, tasks, timeout=ttl_seconds)
    except Exception as exc:
        logger.warning("Failed to register user task: %s", exc)


def check_task_status(request, task_id: str):
    """Retourne l'état d'une tâche Celery via son task_id."""
    try:
        result = AsyncResult(task_id)
        payload = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "result": result.result if result.ready() else None,
        }
        return JsonResponse(payload)
    except Exception as exc:
        logger.exception("Error while checking task status")
        return JsonResponse({"task_id": task_id, "status": "ERROR", "error": str(exc)}, status=500)


def get_pending_tasks(request):
    """Retourne les tâches récemment lancées par l'utilisateur connecté (stockées en cache)."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return JsonResponse({"tasks": []})

    tasks = cache.get(_user_tasks_cache_key(user.id)) or []
    return JsonResponse({"tasks": tasks})
