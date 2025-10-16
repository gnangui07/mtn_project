# Generated manually - Migration de données pour calculer amount_not_delivered

from django.db import migrations
from decimal import Decimal


def calculate_amount_not_delivered(apps, schema_editor):
    """Calculer amount_not_delivered pour tous les enregistrements existants"""
    Reception = apps.get_model('orders', 'Reception')
    
    # Récupérer toutes les réceptions
    receptions = Reception.objects.all()
    
    updated_count = 0
    for reception in receptions:
        # Calculer amount_not_delivered
        quantity_not_delivered = reception.quantity_not_delivered or Decimal('0')
        unit_price = reception.unit_price or Decimal('0')
        
        # Calculer et arrondir à 2 décimales
        amount_not_delivered = (Decimal(str(quantity_not_delivered)) * Decimal(str(unit_price))).quantize(Decimal('0.01'))
        
        # Mettre à jour seulement si la valeur a changé
        if reception.amount_not_delivered != amount_not_delivered:
            reception.amount_not_delivered = amount_not_delivered
            reception.save(update_fields=['amount_not_delivered'])
            updated_count += 1
    
    print(f"✅ {updated_count} réceptions mises à jour avec amount_not_delivered")


def reverse_calculation(apps, schema_editor):
    """Remettre amount_not_delivered à 0 (rollback)"""
    Reception = apps.get_model('orders', 'Reception')
    Reception.objects.all().update(amount_not_delivered=0)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_add_amount_not_delivered'),
    ]

    operations = [
        migrations.RunPython(calculate_amount_not_delivered, reverse_calculation),
    ]
