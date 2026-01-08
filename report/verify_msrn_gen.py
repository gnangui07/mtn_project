
from orders.models import MSRNReport
from django.db import transaction

print("--- Current State ---")
reports = list(MSRNReport.objects.values_list('report_number', flat=True).order_by('-report_number')[:5])
print(f"Latest reports: {reports}")

print("\n--- Dry Run Simulation ---")
# Simulate what the next number would be based on the code I just wrote
latest_report = MSRNReport.objects.filter(report_number__startswith="MSRN25").order_by('-report_number').first()

sequence_part = "0"
if latest_report:
    sequence_part = latest_report.report_number[6:]
    next_sequence = int(sequence_part) + 1
    if next_sequence < 6501:
        print(f"Logic applied: {next_sequence} < 6501, enforcing 6501")
        next_sequence = 6501
    else:
        print(f"Logic applied: {next_sequence} >= 6501, continuing sequence")
else:
    print("No latest report, starting at 6501")
    next_sequence = 6501

print(f"Next generated number will be: MSRN25{next_sequence:05d}")

print("\n--- Test Creation (Rollback) ---")
try:
    with transaction.atomic():
        # Create a dummy report to test the save() method
        # We need a valid bon_commande, let's pick one referenced in a recent report if possible, or just the first one
        # To strictly test the generation logic provided we satisfy foreign keys
        
        # Checking for a valid bon_commande
        latest = MSRNReport.objects.last()
        if latest:
            bon = latest.bon_commande
            
            # Creating dummy report
            # We don't save to avoid polluting DB permanently, but we want to see the ID generated in save()
            # save() is called on creation. We'll wrap in atomic block and raise exception to rollback.
            
            print(f"Using bon: {bon}")
            report = MSRNReport(bon_commande=bon, user="test_script")
            report.save()
            print(f"GENERATED REPORT NUMBER: {report.report_number}")
            
            if report.report_number == "MSRN2506501" or (int(report.report_number[6:]) >= 6501):
                 print("SUCCESS: Report number is in the correct range.")
            else:
                 print(f"FAILURE: Report number {report.report_number} is unexpected.")
                 
            raise Exception("Rolling back test creation")
        else:
            print("No existing reports to base test on. Skipping creation test.")

except Exception as e:
    if "Rolling back" in str(e):
        print("Transaction rolled back as expected.")
    else:
        print(f"Error during test: {e}")
