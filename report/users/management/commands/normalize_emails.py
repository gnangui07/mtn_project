"""
Commande de gestion pour normaliser tous les emails existants en minuscules.

Usage:
    python manage.py normalize_emails
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Normalise tous les emails des utilisateurs en minuscules'

    def handle(self, *args, **options):
        users = User.objects.all()
        updated_count = 0
        
        for user in users:
            original_email = user.email
            normalized_email = original_email.lower().strip()
            
            if original_email != normalized_email:
                user.email = normalized_email
                user.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Normalisé: {original_email} → {normalized_email}')
                )
        
        if updated_count == 0:
            self.stdout.write(self.style.SUCCESS('✓ Tous les emails sont déjà normalisés'))
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ {updated_count} email(s) normalisé(s) avec succès')
            )
