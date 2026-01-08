import os

file_path = r'c:\Users\Lenovo\CascadeProjects\msrn\report\orders\models.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

save_method_content = """    def save(self, *args, **kwargs):
        # 1) GÉNÉRATION DU NUMÉRO DE RAPPORT (Uniquement à la création)
        if not self.report_number:
            from django.db import transaction
            year_suffix = "25"
            year_prefix = f"MSRN{year_suffix}"
            with transaction.atomic():
                latest_report = MSRNReport.objects.filter(
                    report_number__startswith=year_prefix
                ).select_for_update().only('report_number').order_by('-report_number').first()
            
            if latest_report:
                latest_number = latest_report.report_number
                sequence_part = latest_number[6:] 
                next_sequence = int(sequence_part) + 1
                if next_sequence < 6501:
                    next_sequence = 6501
            else:
                next_sequence = 6501
            
            sequence_formatted = f"{next_sequence:05d}"
            self.report_number = f"{year_prefix}{sequence_formatted}"

        # 2) CAPTURE DES SNAPSHOTS (Pour les nouveaux ET les existants)
        from decimal import Decimal
        
        # Montants et Taux
        if self.montant_total_snapshot is None:
            self.montant_total_snapshot = self.bon_commande.montant_total() or Decimal('0')
        if self.montant_recu_snapshot is None:
            self.montant_recu_snapshot = self.bon_commande.montant_recu() or Decimal('0')
        if self.progress_rate_snapshot is None:
            self.progress_rate_snapshot = Decimal(str(self.bon_commande.taux_avancement() or '0'))
        
        if not self.retention_rate_snapshot:
            self.retention_rate_snapshot = self.retention_rate or Decimal('0')
        if not self.retention_amount_snapshot:
            self.retention_amount_snapshot = self.retention_amount or Decimal('0')
        if not self.payable_amount_snapshot:
            self.payable_amount_snapshot = self.payable_amount or Decimal('0')
            
        # Devise
        if not self.currency_snapshot:
            if hasattr(self.bon_commande, 'get_currency'):
                self.currency_snapshot = self.bon_commande.get_currency() or 'XOF'
            else:
                self.currency_snapshot = 'XOF'
        
        # Métadonnées (Firme, CPU, PM...)
        if not self.supplier_snapshot: self.supplier_snapshot = self.bon_commande.get_supplier()
        if not self.cpu_snapshot: self.cpu_snapshot = self.bon_commande.get_cpu()
        if not self.project_manager_snapshot: self.project_manager_snapshot = self.bon_commande.get_project_manager()
        if not self.project_coordinator_snapshot: self.project_coordinator_snapshot = self.bon_commande.get_project_coordinator()
        if not self.senior_pm_snapshot: self.senior_pm_snapshot = self.bon_commande.get_senior_pm()
        if not self.manager_portfolio_snapshot: self.manager_portfolio_snapshot = self.bon_commande.get_manager_portfolio()
        if not self.gm_epmo_snapshot: self.gm_epmo_snapshot = self.bon_commande.get_gm_epmo()

        # Payment Terms
        if not self.payment_terms_snapshot:
            from .models import Reception, LigneFichier
            try:
                reception = Reception.objects.filter(bon_commande=self.bon_commande).only('business_id').first()
                if reception and reception.business_id:
                    ligne = LigneFichier.objects.filter(business_id=reception.business_id).only('contenu').first()
                    if ligne and ligne.contenu:
                        contenu = ligne.contenu
                        pk = 'Payment Terms ' if 'Payment Terms ' in contenu else 'Payment Terms'
                        if pk in contenu and contenu.get(pk):
                            val = str(contenu.get(pk)).strip()
                            if val and val.lower() not in ['n/a', 'na', '', 'none']:
                                self.payment_terms_snapshot = val
            except: pass

        # Réceptions détaillées
        if not self.receptions_data_snapshot:
            receptions = self.bon_commande.receptions.all()
            receptions_snapshot = []
            for reception in receptions:
                q_p = (reception.quantity_delivered or Decimal('0')) - (reception.quantity_not_delivered or Decimal('0'))
                if q_p < 0: q_p = Decimal('0')
                a_p = q_p * (reception.unit_price or Decimal('0'))
                
                desc = "N/A"
                from .models import LigneFichier
                ligne_po = LigneFichier.objects.filter(business_id=reception.business_id).only('contenu').first()
                if ligne_po and ligne_po.contenu:
                    desc = ligne_po.contenu.get('Line Description') or "N/A"
                
                receptions_snapshot.append({
                    'id': reception.id,
                    'line_description': desc,
                    'ordered_quantity': str(reception.ordered_quantity or Decimal('0')),
                    'received_quantity': str(reception.received_quantity or Decimal('0')),
                    'quantity_delivered': str(reception.quantity_delivered or Decimal('0')),
                    'amount_delivered': str(reception.amount_delivered or Decimal('0')),
                    'quantity_payable': str(q_p),
                    'amount_payable': str(a_p),
                })
            self.receptions_data_snapshot = receptions_snapshot
        
        super().save(*args, **kwargs)
"""

# Find start and end of save method
start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if 'def save(self, *args, **kwargs):' in line:
        start_idx = i
    if start_idx != -1 and 'super().save(*args, **kwargs)' in line:
        end_idx = i + 1
        break

if start_idx != -1 and end_idx != -1:
    final_lines = lines[:start_idx] + [save_method_content] + lines[end_idx:]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
    print("SUCCESS")
else:
    print(f"FAILED: start_idx={start_idx}, end_idx={end_idx}")
