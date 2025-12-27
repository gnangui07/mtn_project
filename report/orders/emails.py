"""But:
- Envoyer des notifications email pour MSRN et autres PDFs (pénalités, etc.).

Étapes:
- Préparer les destinataires (superusers + CC l'utilisateur si possible).
- Construire le contenu (texte/HTML) et joindre le PDF si disponible.
- Envoyer l'email, journaliser succès/erreurs.

Entrées:
- Objets de rapport (MSRNReport) ou paramètres (bon_commande, buffer PDF, user_email, type).

Sorties:
- bool: True si l'envoi a réussi, False sinon (les erreurs n'empêchent pas le téléchargement côté utilisateur).
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
    """But:
    - Prévenir par email que le MSRN a été généré.

    Étapes:
    - Vérifier que les notifications sont activées.
    - Récupérer les superusers avec email.
    - Préparer contexte (PO, fournisseur, montants).
    - Rendre HTML et fallback texte, joindre PDF si présent.
    - Envoyer et journaliser.

    Entrées:
    - `msrn_report`: instance `MSRNReport` déjà sauvegardée.

    Sorties:
    - booléen de succès d'envoi.
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
        
        # Formater created_at de manière robuste (accepte datetime, date, str)
        created_at_val = context['created_at']
        try:
            created_at_str = (
                created_at_val.strftime('%Y-%m-%d %H:%M:%S')
                if hasattr(created_at_val, 'strftime')
                else (str(created_at_val) if created_at_val else 'N/A')
            )
        except Exception:
            created_at_str = 'N/A'

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
Created at: {created_at_str}

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
        
        # Joindre le PDF du MSRN si disponible (ouvrir directement pour être mock-friendly)
        try:
            if getattr(msrn_report, 'pdf_file', None) and getattr(msrn_report.pdf_file, 'path', None):
                pdf_path = msrn_report.pdf_file.path
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
                filename = f"{msrn_report.report_number}-{msrn_report.bon_commande.numero}.pdf"
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


def send_penalty_notification(bon_commande, pdf_buffer, user_email, report_type='penalty', filename=None):
    """But:
    - Envoyer l'email pour les rapports PDF hors MSRN (pénalité, amendement, délais, compensation).

    Étapes:
    - Vérifier le paramètre d'activation.
    - Cibler superusers + CC l'émetteur si possible.
    - Préparer un texte simple et joindre le PDF à partir du buffer.
    - Envoyer et journaliser.

    Entrées:
    - `bon_commande`: PO concerné.
    - `pdf_buffer`: buffer mémoire du PDF (BytesIO).
    - `user_email`: émetteur (mis en CC si valide).
    - `report_type`: 'penalty'|'penalty_amendment'|'delay_evaluation'|'compensation_letter'.
    - `filename`: nom du fichier PDF (optionnel).

    Sorties:
    - booléen de succès d'envoi.
    """
    if not getattr(settings, 'ENABLE_EMAIL_NOTIFICATIONS', True):
        logger.info(f"Notifications email désactivées pour {report_type}")
        return False
    
    try:
        superusers = User.objects.filter(is_superuser=True, email__isnull=False).exclude(email='')
        
        # Construire la liste des destinataires: superusers ou fallback sur l'émetteur
        if superusers.exists():
            recipient_list = [user.email for user in superusers]
        else:
            logger.warning(f"Aucun superuser avec email trouvé pour {report_type}")
            recipient_list = []
            # Fallback: si l'utilisateur émetteur a un email valable, l'utiliser comme destinataire
            if user_email and '@' in user_email:
                recipient_list = [user_email]
        
        if not recipient_list:
            # Toujours aucun destinataire valable
            return False
        
        # Préparer les données
        report_titles = {
            'penalty': 'Fiche de Pénalité',
            'penalty_amendment': 'Fiche d\'Amendement de Pénalité',
            'delay_evaluation': 'Évaluation des Délais de Livraison',
            'compensation_letter': 'Lettre de Demande de Compensation'
        }
        
        report_title = report_titles.get(report_type, 'Rapport')
        
        context = {
            'report_type': report_title,
            'purchase_order': bon_commande.numero if bon_commande else 'N/A',
            'supplier': bon_commande.get_supplier() if bon_commande and hasattr(bon_commande, 'get_supplier') else 'N/A',
            'created_by': user_email,
            'created_at': __import__('django.utils.timezone', fromlist=['now']).now(),
        }
        
        # Générer le contenu texte
        text_content = f"""
{report_title} - Généré automatiquement

Un nouveau rapport {report_title.lower()} a été généré:

Bon de Commande: {context['purchase_order']}
Fournisseur: {context['supplier']}
Généré par: {context['created_by']}
Date: {context['created_at'].strftime('%Y-%m-%d %H:%M:%S')}

---
Ceci est une notification automatique du système de gestion des rapports.
        """
        
        # Ajouter l'utilisateur générateur en CC
        cc_list = []
        try:
            if user_email and '@' in user_email and user_email not in recipient_list:
                cc_list.append(user_email)
        except Exception:
            pass
        
        # Créer l'email
        email = EmailMultiAlternatives(
            subject=f'{report_title} - PO {context["purchase_order"]}',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
            cc=cc_list or None,
        )
        
        # Joindre le PDF
        try:
            pdf_buffer.seek(0)
            pdf_bytes = pdf_buffer.read()
            filename = f"{report_type.upper()}-{bon_commande.numero}.pdf"
            email.attach(filename, pdf_bytes, 'application/pdf')
        except Exception as attach_err:
            logger.warning(f"Impossible d'attacher le PDF au courriel: {attach_err}")
        
        # Envoyer l'email
        email.send(fail_silently=False)
        
        logger.info(f"Notification {report_type} envoyée avec succès à {len(recipient_list)} destinataire(s)")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de la notification {report_type}: {str(e)}", exc_info=True)
        return False


def send_test_email(recipient_email):
    """But:
    - Vérifier rapidement la configuration d'envoi email.

    Étapes:
    - Envoyer un message très simple au destinataire.
    - Journaliser le succès/l'échec.

    Entrées:
    - `recipient_email`: adresse cible.

    Sorties:
    - booléen de succès.
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
