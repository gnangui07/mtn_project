# Generated manually

from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_msrnreport_payment_terms_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='reception',
            name='amount_not_delivered',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=20, verbose_name='Amount Not Delivered'),
        ),
    ]
