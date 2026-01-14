#!/usr/bin/env python
"""
Script pour vérifier les doublons dans les imports de fichiers
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'msrn.settings')
django.setup()

from orders.models import LigneFichier, FichierImporte
from collections import defaultdict
import json

def analyser_doublons():
    """Analyse détaillée des doublons"""
    
    print("=" * 80)
    print("🔍 ANALYSE DES DOUBLONS D'IMPORTATION")
    print("=" * 80)
    
    # 1. Statistiques générales
    print("\n📊 STATISTIQUES GÉNÉRALES:")
    total_lignes = LigneFichier.objects.count()
    business_ids_uniques = LigneFichier.objects.values('business_id').distinct().count()
    print(f"   • Total lignes: {total_lignes:,}")
    print(f"   • Business IDs uniques: {business_ids_uniques:,}")
    print(f"   • Doublons évités: {total_lignes - business_ids_uniques:,}")
    
    # 2. Analyse par fichier
    print("\n📁 FICHIERS IMPORTÉS:")
    fichiers = FichierImporte.objects.all().order_by('-date_importation')
    for f in fichiers:
        lignes_count = f.lignes.count()
        unique_bids = f.lignes.values('business_id').distinct().count()
        print(f"   • {f.fichier.name[:50]:50} : {lignes_count:,} lignes, {unique_bids:,} uniques")
    
    # 3. Trouver les doublons
    print("\n🔄 DOUBLONS DÉTECTÉS:")
    doublons = LigneFichier.objects.values('business_id')\
        .annotate(count=models.Count('business_id'))\
        .filter(count__gt=1)\
        .order_by('-count')[:20]
    
    print(f"   • Nombre de business_id en double: {doublons.count():,}")
    
    # 4. Exemples de doublons
    print("\n📋 EXEMPLES DE DOUBLONS:")
    for dup in doublons[:10]:
        bid = dup['business_id']
        lignes = LigneFichier.objects.filter(business_id=bid).select_related('fichier')
        print(f"\n   Business ID: {bid}")
        print(f"   → Apparaît {dup['count']} fois:")
        for l in lignes:
            print(f"     • Fichier {l.fichier.id} - Ligne {l.numero_ligne}")
            # Afficher le contenu pertinent
            if l.contenu:
                order = l.contenu.get('Order', l.contenu.get('ORDER', 'N/A'))
                line = l.contenu.get('Line', l.contenu.get('LINE', 'N/A'))
                item = l.contenu.get('Item', l.contenu.get('ITEM', 'N/A'))
                print(f"       Order: {order}, Line: {line}, Item: {item}")
    
    # 5. Pourquoi sont-ils des doublons?
    print("\n❓ POURQUOI SONT-ILS CONSIDÉRÉS COMME DOUBLONS?")
    print("\n   Un business_id est généré à partir de:")
    print("   • Order (numéro de commande)")
    print("   • Line (numéro de ligne)")
    print("   • Item (code article)")
    print("   • Schedule (numéro de livraison)")
    print("\n   Si ces 4 valeurs sont identiques → même business_id → doublon")
    
    # 6. Analyse des doublons internes
    print("\n🔎 ANALYSE DES DOUBLONS PAR FICHIER:")
    for f in fichiers:
        doublons_fichier = f.lignes.values('business_id')\
            .annotate(count=models.Count('business_id'))\
            .filter(count__gt=1).count()
        if doublons_fichier > 0:
            print(f"   • {f.fichier.name[:30]:30} : {doublons_fichier:,} business_ids répétés")
    
    # 7. Statistiques finales
    print("\n📈 RÉSUMÉ:")
    print(f"   • Lignes totales importées: {total_lignes:,}")
    print(f"   • Lignes uniques réelles: {business_ids_uniques:,}")
    print(f"   • Taux de déduplication: {((total_lignes - business_ids_uniques) / total_lignes * 100):.1f}%")
    
    # Export des résultats
    print("\n💾 Export des résultats en cours...")
    with open('analyse_doublons.json', 'w', encoding='utf-8') as f:
        resultats = {
            'total_lignes': total_lignes,
            'business_ids_uniques': business_ids_uniques,
            'doublons_evites': total_lignes - business_ids_uniques,
            'taux_deduplication': round((total_lignes - business_ids_uniques) / total_lignes * 100, 2),
            'fichiers': [
                {
                    'nom': fi.fichier.name,
                    'lignes': fi.lignes.count(),
                    'uniques': fi.lignes.values('business_id').distinct().count()
                }
                for fi in fichiers
            ]
        }
        json.dump(resultats, f, indent=2, ensure_ascii=False)
    
    print("\n✅ Analyse terminée ! Résultats sauvegardés dans 'analyse_doublons.json'")

if __name__ == "__main__":
    from django.db import models
    analyser_doublons()
