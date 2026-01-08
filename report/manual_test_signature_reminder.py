"""
Script de test pour le système de rappel de signature MSRN.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reports.settings')
django.setup()

from orders.models import MSRNSignatureTracking, MSRNReport, NumeroBonCommande
from orders.emails import find_user_email_by_name, send_signature_reminder
from orders.tasks import send_signature_reminder_task
from datetime import timedelta
from django.utils import timezone


def test_name_matching():
    """Test 1: Correspondance nom -> email"""
    print('=' * 60)
    print('TEST 1: Correspondance nom -> email')
    print('=' * 60)
    
    test_names = ['BONI HERMANN', 'JEAN-MARC KONIN', 'KONIN JM', 'PRISCA TRAORE', 'ADAMA SORO']
    for name in test_names:
        email = find_user_email_by_name(name)
        status = '✅' if email else '❌'
        print(f'{status} {name} -> {email or "NON TROUVE"}')
    print()


def test_pending_signatures():
    """Test 2: Compter les signatures pending"""
    print('=' * 60)
    print('TEST 2: Signatures en base')
    print('=' * 60)
    
    pending_count = MSRNSignatureTracking.objects.filter(status='pending').count()
    signed_count = MSRNSignatureTracking.objects.filter(status='signed').count()
    total = pending_count + signed_count
    
    print(f'Total: {total}')
    print(f'Pending: {pending_count}')
    print(f'Signed: {signed_count}')
    print()


def test_celery_task_simulation():
    """Test 3: Simulation de la tâche Celery (sans envoyer d'email)"""
    print('=' * 60)
    print('TEST 3: Simulation tâche Celery')
    print('=' * 60)
    
    # Prendre une signature pending au hasard
    sig = MSRNSignatureTracking.objects.filter(status='pending').first()
    
    if not sig:
        print('❌ Aucune signature pending trouvée')
        return
    
    print(f'Signature ID: {sig.id}')
    print(f'Signataire: {sig.signatory_name}')
    print(f'Rôle: {sig.get_signatory_role_display()}')
    print(f'Status: {sig.status}')
    print(f'MSRN: {sig.msrn_report.report_number}')
    print(f'PO: {sig.msrn_report.bon_commande.numero if sig.msrn_report.bon_commande else "N/A"}')
    
    # Trouver l'email
    email = find_user_email_by_name(sig.signatory_name)
    if email:
        print(f'✅ Email trouvé: {email}')
    else:
        print(f'❌ Email non trouvé pour {sig.signatory_name}')
    print()


def test_send_real_email():
    """Test 4: Envoi réel d'un email de test"""
    print('=' * 60)
    print('TEST 4: Envoi réel d\'un email')
    print('=' * 60)
    
    # Prendre une signature avec un email trouvable
    sig = MSRNSignatureTracking.objects.filter(status='pending').first()
    
    if not sig:
        print('❌ Aucune signature pending trouvée')
        return
    
    email = find_user_email_by_name(sig.signatory_name)
    
    if not email:
        print(f'❌ Pas d\'email pour {sig.signatory_name}, essai avec BONI HERMANN')
        email = find_user_email_by_name('BONI HERMANN')
        sig_name = 'BONI HERMANN'
    else:
        sig_name = sig.signatory_name
    
    if not email:
        print('❌ Aucun email trouvé pour test')
        return
    
    # Préparer les données
    pending_report = {
        'po_number': sig.msrn_report.bon_commande.numero if sig.msrn_report.bon_commande else 'TEST-PO',
        'report_number': sig.msrn_report.report_number,
        'created_at': sig.msrn_report.created_at,
        'deadline': sig.msrn_report.created_at + timedelta(hours=48),
        'signatory_role': sig.get_signatory_role_display(),
    }
    
    print(f'Envoi à: {sig_name} ({email})')
    print(f'PO: {pending_report["po_number"]}')
    print(f'MSRN: {pending_report["report_number"]}')
    
    # Demander confirmation
    confirm = input('\nEnvoyer l\'email? (o/n): ')
    if confirm.lower() != 'o':
        print('Annulé.')
        return
    
    # Envoyer
    success = send_signature_reminder(sig_name, email, [pending_report])
    
    if success:
        print('✅ Email envoyé avec succès!')
    else:
        print('❌ Échec de l\'envoi')


if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('   TESTS DU SYSTÈME DE RAPPEL DE SIGNATURE MSRN')
    print('=' * 60 + '\n')
    
    test_name_matching()
    test_pending_signatures()
    test_celery_task_simulation()
    
    # Test d'envoi réel (optionnel)
    print('=' * 60)
    print('TEST 4: Envoi réel (optionnel)')
    print('=' * 60)
    do_send = input('Voulez-vous tester l\'envoi réel d\'un email? (o/n): ')
    if do_send.lower() == 'o':
        test_send_real_email()
    else:
        print('Test d\'envoi ignoré.')
    
    print('\n✅ Tests terminés!')
