# Generated manually for performance optimization with 50K+ lines

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_initial'),  # La dernière migration existante
    ]

    operations = [
        # Index sur LigneFichier.business_id (CRITIQUE pour 50K+ lignes)
        migrations.AlterField(
            model_name='lignefichier',
            name='business_id',
            field=models.CharField(
                max_length=255,
                db_index=True,  # Index ajouté
                verbose_name="Business ID"
            ),
        ),
        
        # Index sur Reception.business_id (CRITIQUE pour 50K+ lignes)
        migrations.AlterField(
            model_name='reception',
            name='business_id',
            field=models.CharField(
                max_length=255,
                db_index=True,  # Index ajouté
                verbose_name="Business ID"
            ),
        ),
        
        # Index sur MSRNReport.report_number (pour éviter race conditions)
        migrations.AlterField(
            model_name='msrnreport',
            name='report_number',
            field=models.CharField(
                max_length=10,
                unique=True,
                db_index=True,  # Index ajouté
                verbose_name="Report Number"
            ),
        ),
        
        # Index composite sur Reception pour les requêtes fréquentes
        migrations.AddIndex(
            model_name='reception',
            index=models.Index(
                fields=['bon_commande', 'quantity_delivered'],
                name='reception_bon_qty_idx'
            ),
        ),
        
        # Index sur LigneFichier.fichier pour les jointures
        migrations.AddIndex(
            model_name='lignefichier',
            index=models.Index(
                fields=['fichier', 'business_id'],
                name='ligne_fichier_bid_idx'
            ),
        ),
    ]
