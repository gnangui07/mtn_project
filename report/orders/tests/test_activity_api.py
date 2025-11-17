# tests/test_activity_api.py
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
import os
from unittest.mock import patch
from orders.models import FichierImporte, ActivityLog, NumeroBonCommande, Reception, LigneFichier

User = get_user_model()


class TestActivityAPI(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        # Assurer que l'utilisateur est actif pour l'authentification
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        # Préparer un fichier CSV minimal dans MEDIA_ROOT pour éviter FileNotFoundError
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        csv_path = os.path.join(settings.MEDIA_ROOT, 'test.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write('Order,Line Description,Ordered Quantity,Price\n')
            f.write('TEST123,Sample desc,100,10\n')

        # Créer des données de test
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer des logs d'activité
        self.activity_log = ActivityLog.objects.create(
            bon_commande='TEST123',
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            user=self.user.email,
            progress_rate=Decimal('80.0')
        )

    def test_get_activity_logs_success(self):
        """Test la récupération des logs d'activité sans filtres"""
        response = self.client.get(reverse('orders:get_activity_logs'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['data']), 1)
        
        log_data = data['data'][0]
        self.assertEqual(log_data['bon_commande'], 'TEST123')
        self.assertEqual(log_data['user'], self.user.email)

    def test_get_activity_logs_with_filters(self):
        """Test la récupération des logs d'activité avec filtres"""
        # Test avec filtre par bon de commande
        response = self.client.get(f"{reverse('orders:get_activity_logs')}?bon_number=TEST123")
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(data['data']), 1)

        # Test avec filtre par utilisateur
        response = self.client.get(f"{reverse('orders:get_activity_logs')}?user=test@example.com")
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(data['data']), 1)

    def test_get_activity_logs_pagination(self):
        """Test la pagination des logs d'activité"""
        # Créer plus de logs pour tester la pagination
        for i in range(15):
            ActivityLog.objects.create(
                bon_commande=f'TEST{i}',
                fichier=self.fichier,
                business_id=f"ORDER:TEST{i}|LINE:1|ITEM:1|SCHEDULE:1",
                ordered_quantity=Decimal('100'),
                quantity_delivered=Decimal('50'),
                quantity_not_delivered=Decimal('50'),
                user=self.user.email
            )

        response = self.client.get(f"{reverse('orders:get_activity_logs')}?page=1&page_size=10")
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['page_size'], 10)
        self.assertTrue(data['has_next'])

    def test_get_activity_logs_no_data(self):
        """Test la récupération des logs quand il n'y a pas de données"""
        ActivityLog.objects.all().delete()
        
        response = self.client.get(reverse('orders:get_activity_logs'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['count'], 0)
        self.assertEqual(len(data['data']), 0)

    def test_get_all_bons_success(self):
        """Test la récupération de tous les bons de commande"""
        response = self.client.get(reverse('orders:get_all_bons'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertIn('TEST123', data['data'])

    def test_get_activity_logs_unauthenticated(self):
        """Test l'accès non authentifié aux logs d'activité"""
        self.client.logout()
        response = self.client.get(reverse('orders:get_activity_logs'))
        # Redirection vers la page de login pour les utilisateurs non authentifiés
        self.assertEqual(response.status_code, 302)

    def test_get_additional_data_for_reception(self):
        """Test la fonction get_additional_data_for_reception"""
        from orders.activity_api import get_additional_data_for_reception
        
        # Créer une réception pour tester
        reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('10.50')
        )
        
        # Créer une ligne de fichier
        ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Order': 'TEST123',
                'Supplier': 'Test Supplier',
                'Project Number': 'PROJ001',
                'Line Description': 'Test Item'
            },
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1"
        )
        
        # Tester la fonction
        additional_data = get_additional_data_for_reception(self.activity_log)
        
        self.assertEqual(additional_data['price'], 10.50)
        self.assertEqual(additional_data['supplier'], 'Test Supplier')
        self.assertEqual(additional_data['project_number'], 'PROJ001')

    def test_get_activity_logs_with_line_description(self):
        """Test la récupération des logs avec description de ligne"""
        # Créer une ligne de fichier avec description
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Order': 'TEST123',
                'Line Description': 'Test Item Description'
            },
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1"
        )
        
        response = self.client.get(reverse('orders:get_activity_logs'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        log_data = data['data'][0]
        self.assertEqual(log_data['line_description'], 'Test Item Description')

    def test_get_activity_logs_with_invalid_pagination(self):
        """Test la pagination avec des valeurs invalides"""
        response = self.client.get(f"{reverse('orders:get_activity_logs')}?page=invalid&page_size=abc")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_get_activity_logs_with_date_filters(self):
        """Test les filtres par date"""
        from datetime import timedelta, timezone as dt_timezone
        # Utiliser des datetimes conscients du fuseau horaire pour éviter les warnings
        start_dt = timezone.now() - timedelta(days=30)
        end_dt = timezone.now() + timedelta(days=1)
        # Formater en ISO 8601 avec 'Z' pour UTC
        start_str = start_dt.astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = end_dt.astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.get(
            f"{reverse('orders:get_activity_logs')}?start_date={start_str}&end_date={end_str}"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_get_activity_logs_with_empty_filters(self):
        """Test avec des filtres vides"""
        response = self.client.get(
            f"{reverse('orders:get_activity_logs')}?bon_number=&start_date=&end_date=&user="
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_get_activity_logs_line_description_error_handling(self):
        """Test la gestion des erreurs lors de la récupération de line_description"""
        with patch.object(FichierImporte, 'get_raw_data', return_value="invalid_data"):
            response = self.client.get(reverse('orders:get_activity_logs'))
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertEqual(data['status'], 'success')

    def test_get_activity_logs_progress_rate_handling(self):
        """Test la gestion des différents cas de progress_rate (None)"""
        ActivityLog.objects.create(
            bon_commande='TEST124',
            fichier=self.fichier,
            business_id="ORDER:TEST124|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('50'),
            quantity_not_delivered=Decimal('50'),
            user=self.user.email,
            progress_rate=None
        )
        response = self.client.get(reverse('orders:get_activity_logs'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_get_activity_logs_previous_receptions_logic(self):
        """Test la logique des réceptions précédentes"""
        for i in range(3):
            ActivityLog.objects.create(
                bon_commande='TEST123',
                fichier=self.fichier,
                business_id=f"ORDER:TEST123|LINE:{i+1}|ITEM:1|SCHEDULE:1",
                ordered_quantity=Decimal('100'),
                quantity_delivered=Decimal(str(20 * (i+1))),
                quantity_not_delivered=Decimal(str(100 - (20 * (i+1)))),
                user=self.user.email,
                progress_rate=Decimal(str(20 * (i+1)))
            )
        response = self.client.get(reverse('orders:get_activity_logs'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        if data['data']:
            log_data = data['data'][0]
            self.assertIn('previous_receptions', log_data)

    def test_get_additional_data_for_reception_no_ligne(self):
        """Test get_additional_data_for_reception sans ligne de fichier"""
        from orders.activity_api import get_additional_data_for_reception
        log = ActivityLog.objects.create(
            bon_commande='TEST125',
            fichier=self.fichier,
            business_id="ORDER:TEST125|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('50'),
            quantity_not_delivered=Decimal('50'),
            user=self.user.email
        )
        additional_data = get_additional_data_for_reception(log)
        self.assertEqual(additional_data['price'], 0.0)
        self.assertEqual(additional_data['supplier'], "N/A")

    def test_get_additional_data_for_reception_with_bon_commande_supplier(self):
        """Test get_additional_data_for_reception en utilisant le fournisseur du bon de commande"""
        from orders.activity_api import get_additional_data_for_reception
        NumeroBonCommande.objects.create(numero='TEST126')
        log = ActivityLog.objects.create(
            bon_commande='TEST126',
            fichier=self.fichier,
            business_id="ORDER:TEST126|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('50'),
            quantity_not_delivered=Decimal('50'),
            user=self.user.email
        )
        with patch.object(NumeroBonCommande, 'get_supplier', return_value="Mock Supplier"):
            additional_data = get_additional_data_for_reception(log)
            self.assertEqual(additional_data['supplier'], 'Mock Supplier')

    def test_get_additional_data_for_reception_exception_handling(self):
        """Test la gestion des exceptions dans get_additional_data_for_reception"""
        from orders.activity_api import get_additional_data_for_reception
        with patch('orders.activity_api.LigneFichier.objects.filter') as mock_filter:
            mock_filter.side_effect = Exception("Test error")
            additional_data = get_additional_data_for_reception(self.activity_log)
            self.assertEqual(additional_data['price'], 0.0)
            self.assertEqual(additional_data['supplier'], "N/A")

    def test_get_all_bons_empty(self):
        """Test get_all_bons quand il n'y a pas de bons"""
        NumeroBonCommande.objects.all().delete()
        ActivityLog.objects.all().delete()
        response = self.client.get(reverse('orders:get_all_bons'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(data['data']), 0)
        self.assertEqual(len(data['bons_with_reception']), 0)

    def test_get_activity_logs_currency_handling(self):
        """Test la gestion de la devise par défaut"""
        NumeroBonCommande.objects.create(numero='TEST127')
        ActivityLog.objects.create(
            bon_commande='TEST127',
            fichier=self.fichier,
            business_id="ORDER:TEST127|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('50'),
            quantity_not_delivered=Decimal('50'),
            user=self.user.email
        )
        response = self.client.get(reverse('orders:get_activity_logs'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_get_activity_logs_error_case(self):
        """Test le cas d'erreur dans get_activity_logs (exception interne)"""
        with patch('orders.activity_api.ActivityLog.objects.select_related') as mock_select:
            mock_select.side_effect = Exception("Database error")
            response = self.client.get(reverse('orders:get_activity_logs'))
            self.assertEqual(response.status_code, 500)
            data = json.loads(response.content)
            self.assertEqual(data['status'], 'error')