import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reports.settings')
django.setup()

from orders.models import MSRNReport

reports = MSRNReport.objects.all()
count = reports.count()
print(f"Propagating snapshots for {count} reports...")

updated = 0
for i, report in enumerate(reports):
    try:
        # Saving will trigger the newly refactored save() method
        report.save()
        updated += 1
        if i > 0 and i % 50 == 0:
            print(f"Progress: {i}/{count}...")
    except Exception as e:
        print(f"Error saving report {report.report_number}: {e}")

print(f"Finished. Updated {updated} reports.")
