"""
Commande Django pour tester l'envoi d'emails
Usage: python manage.py test_email votre-email@example.com
"""
from django.core.management.base import BaseCommand
from orders.emails import send_test_email


class Command(BaseCommand):
    help = 'Envoie un email de test pour vérifier la configuration SMTP'

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            type=str,
            help='Adresse email du destinataire'
        )

    def handle(self, *args, **options):
        email = options['email']
        
        self.stdout.write(self.style.WARNING(f'📧 Envoi d\'un email de test à {email}...'))
        
        try:
            success = send_test_email(email)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f'✅ Email de test envoyé avec succès à {email}!'))
                self.stdout.write(self.style.SUCCESS('Vérifiez votre boîte mail (et le dossier spam).'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Échec de l\'envoi de l\'email à {email}'))
                self.stdout.write(self.style.WARNING('Vérifiez les logs ci-dessus pour plus de détails.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur: {str(e)}'))
            self.stdout.write(self.style.WARNING('Vérifiez votre configuration email dans .env'))
