#!/usr/bin/env python
"""
Script pour vérifier si les 58 569 lignes manquantes sont des répétitions exactes
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'msrn.settings')
django.setup()

from orders.models import LigneFichier, FichierImporte
from collections import defaultdict, Counter
import json

def analyser_repetitions():
    """Analyse détaillée des répétitions"""
    
    print("=" * 80)
    print("🔍 ANALYSE DES 58 569 LIGNES MANQUANTES")
    print("=" * 80)
    
    # 1. Statistiques de base
    print("\n📊 STATISTIQUES CONNUES:")
    total_attendu = 17396 + 1 + 61500
    total_reel = LigneFichier.objects.count()
    uniques = LigneFichier.objects.values('business_id').distinct().count()
    doublons_systeme = total_reel - uniques
    
    print(f"   • Total attendu (3 fichiers) : {total_attendu:,}")
    print(f"   • Total réel en base        : {total_reel:,}")
    print(f"   • Manquant                  : {total_attendu - total_reel:,}")
    print(f"   • Doublons système          : {doublons_systeme:,}")
    print(f"   • Business IDs uniques      : {uniques:,}")
    
    # 2. Analyser les répétitions INTERNES à chaque fichier
    print("\n📁 ANALYSE PAR FICHIER:")
    fichiers = FichierImporte.objects.all().order_by('-date_importation')
    total_brut_fichiers = 0
    total_net_fichiers = 0
    
    for f in fichiers:
        # Compter les lignes brutes du fichier (avant déduplication)
        # On simule ce que le fichier contenait en regardant les business_ids
        lignes_brutes = f.lignes.count()
        uniques_fichier = f.lignes.values('business_id').distinct().count()
        repetitions_internes = lignes_brutes - uniques_fichier
        
        total_brut_fichiers += lignes_brutes
        total_net_fichiers += uniques_fichier
        
        print(f"\n   Fichier {f.id}: {f.fichier.name[:50] if f.fichier else 'Sans nom'}")
        print(f"   • Lignes en base     : {lignes_brutes:,}")
        print(f"   • Business IDs uniques: {uniques_fichier:,}")
        print(f"   • Répétitions internes: {repetitions_internes:,}")
        
        # Analyser les répétitions dans ce fichier
        if repetitions_internes > 0:
            doublons_details = f.lignes.values('business_id')\
                .annotate(count=models.Count('business_id'))\
                .filter(count__gt=1)\
                .order_by('-count')[:5]
            
            print("   • Top 5 des business_ids répétés:")
            for d in doublons_details:
                bid = d['business_id']
                print(f"     - {bid}: {d['count']} fois")
    
    print(f"\n📈 TOTAL RÉPÉTITIONS INTERNES: {total_brut_fichiers - total_net_fichiers:,}")
    
    # 3. Vérifier les lignes sans business_id
    print("\n❓ LIGNES SANS BUSINESS_ID:")
    sans_bid = LigneFichier.objects.filter(business_id__isnull=True).count()
    print(f"   • Lignes sans business_id: {sans_bid:,}")
    
    if sans_bid > 0:
        exemples = LigneFichier.objects.filter(business_id__isnull=True)[:3]
        print("   • Exemples:")
        for ex in exemples:
            print(f"     - Fichier {ex.fichier_id}, Ligne {ex.numero_ligne}")
            if ex.contenu:
                print(f"       Contenu: {str(ex.contenu)[:100]}...")
    
    # 4. Calcul de ce qui manque vraiment
    print("\n🧮 CALCUL DES LIGNES MANQUANTES:")
    manquant_total = total_attendu - total_reel
    repetitions_internes_totales = total_brut_fichiers - total_net_fichiers
    
    print(f"   • Manquant total              : {manquant_total:,}")
    print(f"   • Répétitions internes totales: {repetitions_internes_totales:,}")
    print(f"   • Restant à expliquer         : {manquant_total - repetitions_internes_totales:,}")
    
    # 5. Hypothèses sur les lignes manquantes
    print("\n💡 HYPOTHÈSES SUR LES LIGNES MANQUANTES:")
    print("   1. Lignes vides ou invalides ignorées lors de l'import")
    print("   2. Lignes avec valeurs manquantes (pas de Order/Line/Item)")
    print("   3. Erreurs de lecture du fichier (corrompu ou mal formaté)")
    print("   4. Filtrage automatique des lignes avec 'false', 'null', etc.")
    
    # 6. Vérifier les lignes filtrées
    print("\n🔍 VÉRIFICATION DES LIGNES FILTRÉES:")
    # Regarder le contenu pour voir les patterns
    lignes_vides = LigneFichier.objects.filter(
        models.Q(contenu__isnull=True) | 
        models.Q(contenu={}) |
        models.Q(business_id='')
    ).count()
    print(f"   • Lignes avec contenu vide: {lignes_vides:,}")
    
    # Export des résultats
    resultats = {
        'total_attendu': total_attendu,
        'total_reel': total_reel,
        'manquant': total_attendu - total_reel,
        'doublons_systeme': doublons_systeme,
        'uniques': uniques,
        'repetitions_internes': total_brut_fichiers - total_net_fichiers,
        'sans_business_id': sans_bid,
        'lignes_vides': lignes_vides
    }
    
    with open('analyse_repetitions.json', 'w', encoding='utf-8') as f:
        json.dump(resultats, f, indent=2, ensure_ascii=False)
    
    print("\n✅ Analyse terminée !")

if __name__ == "__main__":
    from django.db import models
    analyser_repetitions()
