
from orders.models import MSRNReport, NumeroBonCommande
from django.db import transaction

print("--- Testing Snapshot Population ---")

try:
    with transaction.atomic():
        # Find a PO that has files and potentially some data to scrape
        # We need a PO where get_supplier() etc would return something other than N/A if possible
        # But even if it returns N/A, we want to ensure the snapshot field is populated with *something* (not None/empty string)
        
        # Let's try to find one with a supplier
        bon = None
        for b in NumeroBonCommande.objects.all().order_by('-date_creation')[:20]:
            if b.get_supplier() != "N/A":
                bon = b
                break
        
        if not bon:
            print("Could not find a PO with explicit supplier, using latest PO.")
            bon = NumeroBonCommande.objects.last()
            
        print(f"Using PO: {bon.numero}")
        print(f"PO Supplier (live): {bon.get_supplier()}")
        print(f"PO Project Manager (live): {bon.get_project_manager()}")
        
        # Create dummy report
        report = MSRNReport(bon_commande=bon, user="test_snapshot")
        report.save()
        
        print(f"\nGenerared Report: {report.report_number}")
        print(f"Snapshot Supplier: '{report.supplier_snapshot}'")
        print(f"Snapshot PM: '{report.project_manager_snapshot}'")
        print(f"Snapshot Senior PM: '{report.senior_pm_snapshot}'")
        
        # Verify
        if report.supplier_snapshot == bon.get_supplier():
            print("SUCCESS: Supplier snapshot matches.")
        else:
            print(f"FAILURE: Supplier snapshot '{report.supplier_snapshot}' != '{bon.get_supplier()}'")
            
        if report.project_manager_snapshot == bon.get_project_manager():
            print("SUCCESS: PM snapshot matches.")
        else:
            print(f"FAILURE: PM snapshot '{report.project_manager_snapshot}' != '{bon.get_project_manager()}'")

        raise Exception("Rolling back test transaction")

except Exception as e:
    if "Rolling back" in str(e):
        print("\nTransaction rolled back.")
    else:
        print(f"Error: {e}")
