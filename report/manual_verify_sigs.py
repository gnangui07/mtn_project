import os
import django
import sys

# Setup Django environment
sys.path.append('c:/Users/Lenovo/CascadeProjects/msrn/report')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reports.settings')
django.setup()

from orders.models import NumeroBonCommande, MSRNReport, MSRNSignatureTracking
from decimal import Decimal

def verify():
    print("--- Verification started ---")
    bon = NumeroBonCommande.objects.first()
    if not bon:
        print("No PO found for test")
        return

    print(f"Testing with PO: {bon.numero}")
    
    # Simuler des snapshots pour s'assurer que les signatures seront créées
    report = MSRNReport(
        report_number='TEST_V_999',
        bon_commande=bon,
        user='test@mtn.com',
        retention_rate=Decimal('5.5'),
        project_manager_snapshot='Test PM',
        gm_epmo_snapshot='Test GM'
    )
    
    # On force is_new en ne sauvant pas encore
    report.save()
    
    print(f"MSRN Created: {report.report_number}")
    sigs = MSRNSignatureTracking.objects.filter(msrn_report=report).order_by('order')
    print(f"Signatures count: {sigs.count()}")
    
    for s in sigs:
        print(f" - Order {s.order} | {s.signatory_role}: {s.signatory_name} ({s.get_status_display()})")
    
    # Cleanup
    report.delete()
    print("--- Verification finished & cleaned up ---")

if __name__ == "__main__":
    verify()
