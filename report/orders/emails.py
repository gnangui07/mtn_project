"""
Module de gestion des notifications par email pour les rapports MSRN
"""
import os
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def send_msrn_notification(msrn_report):
    """
    Envoie une notification email aux superusers quand un MSRN est généré.
    
    Args:
        msrn_report: Instance de MSRNReport
        
    Returns:
        bool: True si l'email a été envoyé avec succès, False sinon
    """
    # Vérifier si les notifications sont activées
    if not getattr(settings, 'ENABLE_EMAIL_NOTIFICATIONS', True):
        logger.info("Notifications email désactivées dans les paramètres")
        return False
    
    try:
        # Récupérer tous les superusers avec un email valide
        superusers = User.objects.filter(is_superuser=True, email__isnull=False).exclude(email='')
        
        if not superusers.exists():
            logger.warning("Aucun superuser avec email trouvé pour envoyer la notification MSRN")
            return False
        
        recipient_list = [user.email for user in superusers]
        
        # Préparer les données pour le template
        bon_commande = msrn_report.bon_commande
        context = {
            'msrn_report': msrn_report,
            'report_number': msrn_report.report_number,
            'purchase_order': bon_commande.numero if bon_commande else 'N/A',
            'supplier': bon_commande.get_supplier() if bon_commande and hasattr(bon_commande, 'get_supplier') else 'N/A',
            'currency': bon_commande.get_currency() if bon_commande and hasattr(bon_commande, 'get_currency') else 'N/A',
            'po_amount': bon_commande.montant_total() if bon_commande and callable(getattr(bon_commande, 'montant_total', None)) else 0,
            'amount_delivered': bon_commande.montant_recu() if bon_commande and callable(getattr(bon_commande, 'montant_recu', None)) else 0,
            'delivery_rate': msrn_report.progress_rate_snapshot or 0,
            'retention_rate': msrn_report.retention_rate or 0,
            'retention_cause': msrn_report.retention_cause or 'N/A',
            'created_by': msrn_report.user,
            'created_at': msrn_report.created_at,
            'download_url': f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/orders/msrn-report/{msrn_report.id}/",
        }
        
        # Générer le contenu HTML de l'email
        html_content = render_to_string('orders/emails/msrn_notification.html', context)
        
        # Générer le contenu texte brut (fallback)
        text_content = f"""
MSRN Report Generated - {msrn_report.report_number}

A new MSRN report has been generated:

Report Number: {msrn_report.report_number}
Purchase Order: {context['purchase_order']}
Supplier: {context['supplier']}
PO Amount: {context['po_amount']:,.2f} {context['currency']}
Amount Delivered: {context['amount_delivered']:,.2f} {context['currency']}
Delivery Rate: {context['delivery_rate']:.2f}%
Payment Retention Rate: {context['retention_rate']}%
Retention Cause: {context['retention_cause']}

Created by: {context['created_by']}
Created at: {context['created_at'].strftime('%Y-%m-%d %H:%M:%S') if context['created_at'] else 'N/A'}

Download the report: {context['download_url']}

---
This is an automated notification from the MSRN System.
        """
        
        # Créer l'email avec version HTML et texte
        # Ajouter l'utilisateur générateur en CC s'il a un email valide
        cc_list = []
        try:
            generator_email = (msrn_report.user or '').strip()
            if generator_email and '@' in generator_email and generator_email not in recipient_list:
                cc_list.append(generator_email)
        except Exception:
            pass

        email = EmailMultiAlternatives(
            subject=f'MSRN Generated: {msrn_report.report_number} - PO {context["purchase_order"]}',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
            cc=cc_list or None,
        )
        email.attach_alternative(html_content, "text/html")
        
        # Joindre le PDF du MSRN si disponible
        try:
            if getattr(msrn_report, 'pdf_file', None) and getattr(msrn_report.pdf_file, 'path', None):
                pdf_path = msrn_report.pdf_file.path
                if os.path.exists(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        pdf_bytes = f.read()
                    filename = f"MSRN-{msrn_report.report_number}.pdf"
                    email.attach(filename, pdf_bytes, 'application/pdf')
        except Exception as attach_err:
            logger.warning(f"Impossible d'attacher le PDF MSRN au courriel: {attach_err}")
        
        # Envoyer l'email
        email.send(fail_silently=False)
        
        logger.info(f"Notification MSRN envoyée avec succès pour {msrn_report.report_number} à {len(recipient_list)} destinataire(s)")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de la notification MSRN pour {msrn_report.report_number}: {str(e)}", exc_info=True)
        return False


def send_test_email(recipient_email):
    """
    Envoie un email de test pour vérifier la configuration.
    
    Args:
        recipient_email: Email du destinataire
        
    Returns:
        bool: True si l'email a été envoyé avec succès, False sinon
    """
    try:
        send_mail(
            subject='Test Email - MSRN System',
            message='This is a test email from the MSRN notification system. If you receive this, your email configuration is working correctly!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        logger.info(f"Email de test envoyé avec succès à {recipient_email}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email de test: {str(e)}", exc_info=True)
        return False
