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


def check_user_tasks_notifications(request):
    """
    Vérifie toutes les tâches de l'utilisateur et retourne celles qui sont terminées.
    Les tâches terminées sont retirées de la liste pour ne être notifiées qu'une seule fois.
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return JsonResponse({"notifications": []})

    key = _user_tasks_cache_key(user.id)
    tasks = cache.get(key) or []
    
    if not tasks:
        return JsonResponse({"notifications": []})

    notifications = []
    remaining_tasks = []
    modified = False

    for task_info in tasks:
        task_id = task_info.get("task_id")
        if not task_id:
            continue

        try:
            result = AsyncResult(task_id)
            if result.ready():
                # La tâche est terminée (SUCCESS ou FAILURE)
                modified = True
                status = result.status
                
                # Récupérer le résultat ou l'erreur
                task_result = None
                error_msg = None
                
                if result.successful():
                    task_result = result.result
                else:
                    error_msg = str(result.result) if result.result else "Task failed"

                notifications.append({
                    "task_id": task_id,
                    "task_type": task_info.get("task_type", "unknown"),
                    "status": status,
                    "result": task_result,
                    "error": error_msg
                })
            else:
                # La tâche est toujours en cours, on la garde
                remaining_tasks.append(task_info)
        except Exception as e:
            logger.error(f"Error checking task {task_id}: {e}")
            # En cas d'erreur technique sur une tâche, on la garde pour réessayer plus tard
            remaining_tasks.append(task_info)

    # Mettre à jour le cache seulement si des tâches ont été retirées (terminées)
    if modified:
        if remaining_tasks:
            cache.set(key, remaining_tasks, timeout=3600)
        else:
            cache.delete(key)

    return JsonResponse({"notifications": notifications})
