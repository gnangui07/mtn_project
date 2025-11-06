# tests/test_reception_api.py
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


class TestReceptionAPI(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        # Assurer un compte actif et une session authentifiée
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        # Préparer un fichier CSV minimal dans MEDIA_ROOT pour éviter FileNotFoundError
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        csv_path = os.path.join(settings.MEDIA_ROOT, 'test.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write('Order,Price,Supplier,Ordered Quantity\n')
            f.write('TEST123,10.50,Test Supplier,100\n')

        # Créer des données de test
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        # Nettoyer les réceptions auto-créées par l'extraction
        Reception.objects.filter(fichier=self.fichier).delete()
        
        # Créer une ligne de fichier
        self.ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Order': 'TEST123',
                'Price': '10.50',
                'Supplier': 'Test Supplier'
            },
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1"
        )
        
        # Créer une réception existante
        self.reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('50'),
            quantity_not_delivered=Decimal('50'),
            unit_price=Decimal('10.50'),
            user=self.user.email
        )

    def test_update_quantity_delivered_get_success(self):
        """Test la récupération des données de réception (GET)"""
        response = self.client.get(
            reverse('orders:update_quantity_delivered', args=[self.fichier.id]),
            {'bon_number': 'TEST123'}
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertIn('ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1', data['receptions'])

    def test_update_quantity_delivered_get_bon_not_found(self):
        """Test la récupération avec un bon de commande inexistant"""
        response = self.client.get(
            reverse('orders:update_quantity_delivered', args=[self.fichier.id]),
            {'bon_number': 'NONEXISTENT'}
        )
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Bon de commande non trouvé')

    def test_update_quantity_delivered_post_success(self):
        """Test la mise à jour d'une quantité livrée (POST)"""
        data = {
            'bon_number': 'TEST123',
            'business_id': 'ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1',
            'quantity_delivered': '20',
            'original_quantity': '100'
        }
        
        response = self.client.post(
            reverse('orders:update_quantity_delivered', args=[self.fichier.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['quantity_delivered'], 70.0)  # 50 existant + 20 nouveau

        # Vérifier que l'objet a été mis à jour
        self.reception.refresh_from_db()
        self.assertEqual(self.reception.quantity_delivered, Decimal('70'))

        # Vérifier qu'un log d'activité a été créé
        activity_log = ActivityLog.objects.filter(
            bon_commande='TEST123',
            business_id='ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1'
        ).last()
        self.assertIsNotNone(activity_log)
        self.assertEqual(activity_log.quantity_delivered, Decimal('20'))

    def test_update_quantity_delivered_post_new_reception(self):
        """Test la création d'une nouvelle réception"""
        data = {
            'bon_number': 'TEST123',
            'business_id': 'ORDER:TEST123|LINE:2|ITEM:1|SCHEDULE:1',
            'quantity_delivered': '30',
            'original_quantity': '100'
        }
        
        response = self.client.post(
            reverse('orders:update_quantity_delivered', args=[self.fichier.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['quantity_delivered'], 30.0)

        # Vérifier que la nouvelle réception a été créée
        new_reception = Reception.objects.filter(
            business_id='ORDER:TEST123|LINE:2|ITEM:1|SCHEDULE:1'
        ).first()
        self.assertIsNotNone(new_reception)
        self.assertEqual(new_reception.quantity_delivered, Decimal('30'))

    def test_update_quantity_delivered_post_exceeds_ordered(self):
        """Test la mise à jour avec une quantité supérieure à la quantité commandée"""
        data = {
            'bon_number': 'TEST123',
            'business_id': 'ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1',
            'quantity_delivered': '60',  # Dépasserait 100 (50 existant + 60 = 110)
            'original_quantity': '100'
        }
        
        response = self.client.post(
            reverse('orders:update_quantity_delivered', args=[self.fichier.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertIn('dépasse la quantité commandée', data['message'])

    def test_update_quantity_delivered_post_negative_correction(self):
        """Test la correction négative d'une quantité"""
        data = {
            'bon_number': 'TEST123',
            'business_id': 'ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1',
            'quantity_delivered': '-10',  # Correction négative
            'original_quantity': '100'
        }
        
        response = self.client.post(
            reverse('orders:update_quantity_delivered', args=[self.fichier.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['quantity_delivered'], 40.0)  # 50 - 10

    def test_update_quantity_delivered_post_negative_without_existing(self):
        """Test la correction négative sans réception existante"""
        data = {
            'bon_number': 'TEST123',
            'business_id': 'ORDER:TEST123|LINE:3|ITEM:1|SCHEDULE:1',
            'quantity_delivered': '-10',
            'original_quantity': '100'
        }
        
        response = self.client.post(
            reverse('orders:update_quantity_delivered', args=[self.fichier.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertIn('sans réception existante', data['message'])

    def test_bulk_update_receptions_success(self):
        """Test la mise à jour groupée des réceptions"""
        data = {
            'bon_number': 'TEST123',
            'updates': [
                {
                    'business_id': 'ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1',
                    'quantity_delivered': '10',
                    'ordered_quantity': '100'
                }
            ]
        }
        
        response = self.client.post(
            reverse('orders:bulk_update_receptions', args=[self.fichier.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(len(response_data['updated_receptions']), 1)

    def test_bulk_update_receptions_invalid_data(self):
        """Test la mise à jour groupée avec des données invalides"""
        data = {
            'bon_number': 'TEST123',
            'updates': [
                {
                    'business_id': 'ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1',
                    'quantity_delivered': '150',  # Dépassement
                    'ordered_quantity': '100'
                }
            ]
        }
        
        response = self.client.post(
            reverse('orders:bulk_update_receptions', args=[self.fichier.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'error')

    def test_reset_quantity_delivered_success(self):
        """Test la réinitialisation des quantités livrées"""
        data = {
            'bon_number': 'TEST123'
        }
        
        response = self.client.post(
            reverse('orders:reset_quantity_delivered', args=[self.fichier.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')

        # Vérifier que les réceptions ont été supprimées
        receptions_count = Reception.objects.filter(
            bon_commande=self.bon_commande,
            fichier=self.fichier
        ).count()
        self.assertEqual(receptions_count, 0)

        # Vérifier qu'un log d'activité a été créé
        activity_log = ActivityLog.objects.filter(
            bon_commande='TEST123',
            business_id='RESET_ALL'
        ).first()
        self.assertIsNotNone(activity_log)

    def test_update_retention_success(self):
        """Test la mise à jour du taux de rétention"""
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Test retention cause'
        }
        
        response = self.client.post(
            reverse('orders:update_retention', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['retention_rate'], 7.5)

        # Vérifier que le bon de commande a été mis à jour
        self.bon_commande.refresh_from_db()
        self.assertEqual(self.bon_commande.retention_rate, Decimal('7.5'))

    def test_update_retention_invalid_rate(self):
        """Test la mise à jour avec un taux de rétention invalide"""
        data = {
            'retention_rate': '15.0',  # Trop élevé
            'retention_cause': 'Test cause'
        }
        
        response = self.client.post(
            reverse('orders:update_retention', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'error')

    def test_get_receptions_success(self):
        """Test la récupération des réceptions d'un bon"""
        response = self.client.get(reverse('orders:get_receptions', args=[self.bon_commande.id]))
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(len(response_data['receptions']), 1)

    def test_get_reception_history_success(self):
        """Test la récupération de l'historique des réceptions"""
        # Créer un log d'activité pour l'historique
        ActivityLog.objects.create(
            bon_commande='TEST123',
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('30'),
            quantity_not_delivered=Decimal('70'),
            user=self.user.email
        )
        
        response = self.client.get(
            reverse('orders:get_reception_history', args=[self.fichier.id]),
            {
                'bon_number': 'TEST123',
                'business_ids': 'ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertIn('ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1', response_data['history'])

    def test_bulk_correction_quantity_delivered_success(self):
        """Test les corrections groupées des quantités livrées"""
        data = {
            'bon_number': 'TEST123',
            'corrections': [
                {
                    'business_id': 'ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1',
                    'correction_value': '5',
                    'original_quantity': '100'
                }
            ]
        }
        
        response = self.client.post(
            reverse('orders:bulk_correction_quantity_delivered', args=[self.fichier.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(len(response_data['results']), 1)

    def test_update_quantity_delivered_file_not_found(self):
        """Test avec un fichier inexistant"""
        response = self.client.get(reverse('orders:update_quantity_delivered', args=[999]))
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Fichier non trouvé')

    def test_update_quantity_delivered_invalid_json(self):
        """Test avec un JSON invalide"""
        response = self.client.post(
            reverse('orders:update_quantity_delivered', args=[self.fichier.id]),
            data='invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Format JSON invalide')