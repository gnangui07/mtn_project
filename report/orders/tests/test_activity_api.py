# tests/test_activity_api.py
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
import os
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