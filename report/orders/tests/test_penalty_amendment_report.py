import pytest


@pytest.mark.django_db
def test_generate_penalty_amendment_report_smoke(user_active):
    from orders.models import NumeroBonCommande
    from orders.penalty_amendment_data import collect_penalty_amendment_context
    from orders.penalty_amendment_report import generate_penalty_amendment_report

    # PO minimal
    po = NumeroBonCommande.objects.create(numero='PO-AMD-PDF-1')

    # Contexte par défaut via le collecteur d'amendement (gère les valeurs manquantes)
    ctx = collect_penalty_amendment_context(po)

    buf = generate_penalty_amendment_report(po, ctx, user_email='tester@example.com')
    pdf_bytes = buf.getvalue() if hasattr(buf, 'getvalue') else buf

    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert pdf_bytes[:4] == b'%PDF'
    assert len(pdf_bytes) > 1024
