
import os
import django
import sys
import logging

sys.path.append(r'c:\Users\Lenovo\CascadeProjects\msrn\report')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reports.settings")
django.setup()

from orders.models import ActivityLog, LigneFichier, FichierImporte

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_logs():
    print("--- Debugging ActivityLogs for Fichier 1 ---")
    # Take a few logs from Fichier 1 (which we know is empty/problematic)
    logs = ActivityLog.objects.filter(fichier_id=1)[:5]
    
    if not logs:
        print("No logs found for Fichier 1. Checking any File...")
        logs = ActivityLog.objects.all()[:5]

    for log in logs:
        print(f"\nLog ID: {log.id}")
        print(f"  Bon Commande: {log.bon_commande}")
        print(f"  Log Business ID: '{log.business_id}'")
        
        if not log.business_id:
            print("  WARN: No business_id on Log!")
            continue

        # Try to find matching LigneFichier
        matching_lines = LigneFichier.objects.filter(business_id=log.business_id)
        count = matching_lines.count()
        print(f"  Matching LigneFichier count: {count}")
        
        if count > 0:
            last_line = matching_lines.order_by('-date_creation').first()
            print(f"  Last Line ID: {last_line.id}")
            content = last_line.contenu
            # print(f"  Content Keys: {list(content.keys())}")
            
            # Simulate the extraction logic
            line_description = ''
            for key, value in content.items():
                key_lower = key.lower() if key else ''
                if 'description' in key_lower and 'line' in key_lower and value:
                    line_description = str(value)
                    print(f"  FOUND Description (key='{key}'): '{line_description}'")
                    break
            
            if not line_description:
                print("  WARN: No 'Line Description' found in content.")
                # Print all keys/values to see what is there
                print("  Content Dump:", content)
        else:
            print("  ERROR: No LigneFichier found for this business_id!")
            # Check if maybe the format is slightly different?
            # Try partial match?
            

if __name__ == '__main__':
    target_po = 'CI-OR-3000001032'
    print("\n" * 5)
    print(f"--- INSPECTING PO: {target_po} ---")
    
    logs = ActivityLog.objects.filter(bon_commande__icontains=target_po)
    print(f"Found {logs.count()} logs for this PO.")
    
    for log in logs[:3]: # Check first 3
        print(f"\nLog ID: {log.id}")
        print(f"  Fichier ID: {log.fichier_id}")
        print(f"  Business ID: '{log.business_id}'")
        
        if not log.business_id:
            print("  [!] ERROR: Missing Business ID on Log")
            continue
            
        # Lookup LigneFichier
        lines = LigneFichier.objects.filter(business_id=log.business_id).order_by('-date_creation')
        print(f"  Matching LigneFichier count: {lines.count()}")
        
        if lines.exists():
            l = lines.first()
            print(f"  Using LigneFichier ID: {l.id} (from Fichier {l.fichier_id})")
            
            # Check content
            found_desc = False
            for key, value in l.contenu.items():
                k = key.lower().strip()
                if 'description' in k and 'line' in k:
                    print(f"  [OK] Found Description key '{key}': {value}")
                    found_desc = True
                    break
            
            if not found_desc:
                print("  [!] FAIL: No 'Line Description' key found in content.")
                print("  Keys:", list(l.contenu.keys()))
        else:
            print("  [!] FAIL: No LigneFichier found for this business_id!")
