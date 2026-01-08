import pytest
import json
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache
from celery.result import AsyncResult

from orders.task_status_api import (
    register_user_task,
    check_task_status,
    get_pending_tasks,
    check_user_tasks_notifications,
    _user_tasks_cache_key
)

User = get_user_model()


class TestTaskStatusAPI(TestCase):
    """Test l'API de statut des tâches"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        cache.clear()
    
    def test_user_tasks_cache_key(self):
        """Test génération clé cache"""
        key = _user_tasks_cache_key(self.user.id)
        self.assertEqual(key, f'user_tasks_{self.user.id}')
    
    @patch('orders.task_status_api.cache')
    def test_register_user_task(self, mock_cache):
        """Test enregistrement tâche utilisateur"""
        mock_cache.get.return_value = []
        
        register_user_task(self.user.id, 'task-123', 'export')
        
        mock_cache.set.assert_called_once()
        args, kwargs = mock_cache.set.call_args
        self.assertEqual(args[0], f'user_tasks_{self.user.id}')
        self.assertEqual(len(args[1]), 1)
        self.assertEqual(args[1][0]['task_id'], 'task-123')
        self.assertEqual(args[1][0]['task_type'], 'export')
    
    @patch('orders.task_status_api.cache')
    def test_register_user_task_deduplication(self, mock_cache):
        """Test déduplication des tâches"""
        # Simule des tâches existantes avec duplication
        existing_tasks = [
            {'task_id': 'task-1', 'task_type': 'export'},
            {'task_id': 'task-2', 'task_type': 'import'},
            {'task_id': 'task-1', 'task_type': 'export'},  # Dupliqué
        ]
        mock_cache.get.return_value = existing_tasks
        
        register_user_task(self.user.id, 'task-3', 'pdf')
        
        # Vérifie que la déduplication a fonctionné
        args, kwargs = mock_cache.set.call_args
        tasks = args[1]
        self.assertEqual(len(tasks), 3)  # [task-2, task-1, task-3]
        task_ids = [t['task_id'] for t in tasks]
        self.assertIn('task-1', task_ids)
        self.assertIn('task-2', task_ids)
        self.assertIn('task-3', task_ids)
    
    @patch('orders.task_status_api.cache')
    def test_register_user_task_exception(self, mock_cache):
        """Test gestion exception lors enregistrement"""
        mock_cache.get.side_effect = Exception('Cache error')
        
        # Ne doit pas lever d'exception
        register_user_task(self.user.id, 'task-123', 'export')
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_task_status_success(self, mock_async_result):
        """Test vérification statut tâche succès"""
        mock_result = Mock()
        mock_result.status = 'SUCCESS'
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {'file': 'generated.pdf'}
        mock_async_result.return_value = mock_result
        
        request = self.factory.get('/check-task/')
        response = check_task_status(request, 'task-123')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['task_id'], 'task-123')
        self.assertEqual(data['status'], 'SUCCESS')
        self.assertTrue(data['ready'])
        self.assertTrue(data['successful'])
        self.assertEqual(data['result'], {'file': 'generated.pdf'})
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_task_status_pending(self, mock_async_result):
        """Test vérification statut tâche en cours"""
        mock_result = Mock()
        mock_result.status = 'PENDING'
        mock_result.ready.return_value = False
        mock_async_result.return_value = mock_result
        
        request = self.factory.get('/check-task/')
        response = check_task_status(request, 'task-123')
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'PENDING')
        self.assertFalse(data['ready'])
        self.assertIsNone(data['successful'])
        self.assertIsNone(data['result'])
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_task_status_failure(self, mock_async_result):
        """Test vérification statut tâche échec"""
        mock_result = Mock()
        mock_result.status = 'FAILURE'
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.result = 'Something went wrong'
        mock_async_result.return_value = mock_result
        
        request = self.factory.get('/check-task/')
        response = check_task_status(request, 'task-123')
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'FAILURE')
        self.assertTrue(data['ready'])
        self.assertFalse(data['successful'])
        self.assertEqual(data['result'], 'Something went wrong')
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_task_status_exception(self, mock_async_result):
        """Test exception lors vérification statut"""
        mock_async_result.side_effect = Exception('Task error')
        
        request = self.factory.get('/check-task/')
        response = check_task_status(request, 'task-123')
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ERROR')
        self.assertIn('error', data)
    
    def test_get_pending_tasks_authenticated(self):
        """Test récupération tâches en cours (authentifié)"""
        # Simule des tâches en cache
        cache.set(f'user_tasks_{self.user.id}', [
            {'task_id': 'task-1', 'task_type': 'export'},
            {'task_id': 'task-2', 'task_type': 'import'}
        ])
        
        request = self.factory.get('/pending-tasks/')
        request.user = self.user
        
        response = get_pending_tasks(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['tasks']), 2)
        self.assertEqual(data['tasks'][0]['task_id'], 'task-1')
        self.assertEqual(data['tasks'][1]['task_type'], 'import')
    
    def test_get_pending_tasks_no_tasks(self):
        """Test récupération tâches en cours (aucune tâche)"""
        request = self.factory.get('/pending-tasks/')
        request.user = self.user
        
        response = get_pending_tasks(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['tasks']), 0)
    
    def test_get_pending_tasks_not_authenticated(self):
        """Test récupération tâches en cours (non authentifié)"""
        request = self.factory.get('/pending-tasks/')
        request.user = Mock()
        request.user.is_authenticated = False
        
        response = get_pending_tasks(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['tasks']), 0)
    
    def test_get_pending_tasks_no_user(self):
        """Test récupération tâches en cours (pas d'utilisateur)"""
        request = self.factory.get('/pending-tasks/')
        # Pas d'attribut user
        
        response = get_pending_tasks(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['tasks']), 0)
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_user_tasks_notifications(self, mock_async_result):
        """Test vérification notifications tâches terminées"""
        # Simule des tâches en cache
        cache.set(f'user_tasks_{self.user.id}', [
            {'task_id': 'task-1', 'task_type': 'export'},
            {'task_id': 'task-2', 'task_type': 'import'},
            {'task_id': 'task-3', 'task_type': 'pdf'}
        ])
        
        # Configure les résultats
        def side_effect(task_id):
            if task_id == 'task-1':
                result = Mock()
                result.status = 'SUCCESS'
                result.ready.return_value = True
                result.successful.return_value = True
                result.result = {'file': 'export.xlsx'}
                return result
            elif task_id == 'task-2':
                result = Mock()
                result.status = 'FAILURE'
                result.ready.return_value = True
                result.successful.return_value = False
                result.result = 'Import failed'
                return result
            else:
                result = Mock()
                result.status = 'PENDING'
                result.ready.return_value = False
                return result
        
        mock_async_result.side_effect = side_effect
        
        request = self.factory.get('/notifications/')
        request.user = self.user
        
        response = check_user_tasks_notifications(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['notifications']), 2)  # 2 terminées
        
        # Vérifie notification succès
        notif1 = data['notifications'][0]
        self.assertEqual(notif1['task_id'], 'task-1')
        self.assertEqual(notif1['status'], 'SUCCESS')
        self.assertEqual(notif1['result'], {'file': 'export.xlsx'})
        self.assertIsNone(notif1['error'])
        
        # Vérifie notification échec
        notif2 = data['notifications'][1]
        self.assertEqual(notif2['task_id'], 'task-2')
        self.assertEqual(notif2['status'], 'FAILURE')
        self.assertIsNone(notif2['result'])
        self.assertEqual(notif2['error'], 'Import failed')
        
        # Vérifie que les tâches terminées ont été retirées du cache
        remaining_tasks = cache.get(f'user_tasks_{self.user.id}')
        self.assertEqual(len(remaining_tasks), 1)
        self.assertEqual(remaining_tasks[0]['task_id'], 'task-3')
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_user_tasks_notifications_all_pending(self, mock_async_result):
        """Test notifications avec toutes les tâches en cours"""
        cache.set(f'user_tasks_{self.user.id}', [
            {'task_id': 'task-1', 'task_type': 'export'}
        ])
        
        mock_result = Mock()
        mock_result.status = 'PENDING'
        mock_result.ready.return_value = False
        mock_async_result.return_value = mock_result
        
        request = self.factory.get('/notifications/')
        request.user = self.user
        
        response = check_user_tasks_notifications(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['notifications']), 0)
        
        # Vérifie que la tâche est toujours en cache
        remaining_tasks = cache.get(f'user_tasks_{self.user.id}')
        self.assertEqual(len(remaining_tasks), 1)
    
    def test_check_user_tasks_notifications_no_tasks(self):
        """Test notifications sans tâches"""
        request = self.factory.get('/notifications/')
        request.user = self.user
        
        response = check_user_tasks_notifications(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['notifications']), 0)
    
    def test_check_user_tasks_notifications_not_authenticated(self):
        """Test notifications non authentifié"""
        request = self.factory.get('/notifications/')
        request.user = Mock()
        request.user.is_authenticated = False
        
        response = check_user_tasks_notifications(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['notifications']), 0)
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_user_tasks_notifications_task_error(self, mock_async_result):
        """Test gestion erreur lors vérification tâche"""
        cache.set(f'user_tasks_{self.user.id}', [
            {'task_id': 'task-1', 'task_type': 'export'},
            {'task_id': 'task-2', 'task_type': 'import'}
        ])
        
        # task-1 réussit, task-2 lève une exception
        def side_effect(task_id):
            if task_id == 'task-1':
                result = Mock()
                result.status = 'SUCCESS'
                result.ready.return_value = True
                result.successful.return_value = True
                result.result = {'file': 'export.xlsx'}
                return result
            elif task_id == 'task-2':
                raise Exception('Task check error')
        
        mock_async_result.side_effect = side_effect
        
        request = self.factory.get('/notifications/')
        request.user = self.user
        
        response = check_user_tasks_notifications(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['notifications']), 1)  # Seulement task-1 terminée
        
        # Vérifie que task-2 est toujours en cache (erreur technique)
        remaining_tasks = cache.get(f'user_tasks_{self.user.id}')
        self.assertEqual(len(remaining_tasks), 1)
        self.assertEqual(remaining_tasks[0]['task_id'], 'task-2')
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_user_tasks_notifications_failure_without_result(self, mock_async_result):
        """Test notification échec sans message d'erreur"""
        cache.set(f'user_tasks_{self.user.id}', [
            {'task_id': 'task-1', 'task_type': 'export'}
        ])
        
        mock_result = Mock()
        mock_result.status = 'FAILURE'
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.result = None  # Pas de message d'erreur
        mock_async_result.return_value = mock_result
        
        request = self.factory.get('/notifications/')
        request.user = self.user
        
        response = check_user_tasks_notifications(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['notifications']), 1)
        self.assertEqual(data['notifications'][0]['error'], 'Task failed')
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_user_tasks_notifications_cache_cleanup(self, mock_async_result):
        """Test nettoyage complet du cache quand toutes les tâches sont terminées"""
        cache.set(f'user_tasks_{self.user.id}', [
            {'task_id': 'task-1', 'task_type': 'export'}
        ])
        
        mock_result = Mock()
        mock_result.status = 'SUCCESS'
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {'file': 'export.xlsx'}
        mock_async_result.return_value = mock_result
        
        request = self.factory.get('/notifications/')
        request.user = self.user
        
        response = check_user_tasks_notifications(request)
        
        # Vérifie que le cache a été supprimé
        self.assertIsNone(cache.get(f'user_tasks_{self.user.id}'))
    
    @patch('orders.task_status_api.AsyncResult')
    def test_check_user_tasks_notifications_task_without_id(self, mock_async_result):
        """Test notification avec tâche sans ID"""
        cache.set(f'user_tasks_{self.user.id}', [
            {'task_type': 'export'},  # Pas de task_id
            {'task_id': 'task-2', 'task_type': 'import'}
        ])
        
        mock_result = Mock()
        mock_result.status = 'SUCCESS'
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {'file': 'import.xlsx'}
        mock_async_result.return_value = mock_result
        
        request = self.factory.get('/notifications/')
        request.user = self.user
        
        response = check_user_tasks_notifications(request)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['notifications']), 1)  # Seulement task-2
