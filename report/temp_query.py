import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reports.settings')
django.setup()

from orders.models import NumeroBonCommande
from django.utils import timezone
from datetime import datetime

# Bons de commande créés en 2026
bons_2026 = NumeroBonCommande.objects.filter(
    date_creation__year=2026
).order_by('date_creation')

print(f'Nombre de bons créés en 2026: {bons_2026.count()}')
print('Liste des bons créés en 2026:')
for bon in bons_2026:
    print(f'ID: {bon.id} | Numero: {bon.numero} | CPU: {bon.cpu or "N/A"} | Date: {bon.date_creation.strftime("%d/%m/%Y %H:%M")}')
