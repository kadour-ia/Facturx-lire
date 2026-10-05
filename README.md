# facturx-lire

**Lire en clair une facture électronique reçue (Factur-X, CII, UBL).**

À partir de septembre 2026, toutes les entreprises françaises (TPE, auto-entrepreneurs inclus) doivent pouvoir **recevoir** des factures électroniques. Un PDF Factur-X contient un XML caché ; un fichier UBL/CII n'est pas lisible à l'œil. Cet outil gratuit :

- extrait le XML embarqué dans un PDF Factur-X / ZUGFeRD ;
- lit les formats CII et UBL ;
- affiche fournisseur, n° TVA, totaux HT/TVA/TTC, échéance, IBAN et lignes ;
- génère une page HTML lisible et imprimable.

## Installation

```
pip install pypdf
python facturx_lire.py facture.pdf --html facture.html
python facturx_lire.py facture.xml
```

Aucune donnée n'est envoyée nulle part : tout tourne sur votre ordinateur.

## Traitement par lot (export CSV pour comptable)

Pour transmettre toutes vos factures reçues à votre comptable en un seul tableau :

```
python facturx_lire.py --csv factures.csv dossier_des_factures
python facturx_lire.py --csv factures.csv --lignes lignes.csv facture1.pdf dossier/ autre.xml
```

- parcourt les `.pdf` et `.xml` (dossiers explorés récursivement) ;
- `factures.csv` : 1 ligne par facture, colonnes `fichier;format;numero;date;echeance;fournisseur;tva_fournisseur;client;total_ht;total_tva;total_ttc;devise;iban;statut` ;
- `lignes.csv` (option `--lignes`) : `fichier;numero;libelle;quantite;prix_unitaire;montant_ht;taux_tva` ;
- séparateur `;`, UTF-8 avec BOM : s'ouvre directement dans Excel français ;
- fichier illisible (PDF sans XML, XML invalide…) : `statut` = `ERREUR: message`, le lot continue ;
- option `--virgule` : montants avec virgule décimale (`350,00`) si Excel les prend pour du texte.

Limites : les dates restent au format d'origine de la facture (`20260915` en CII, `2026-09-20` en UBL) ; seul le premier taux de TVA de chaque ligne est exporté ; pas de contrôle de conformité ni de rapprochement des totaux.

## Questions fréquentes

- **Comment ouvrir / lire un fichier XML de facture reçu ?** `python facturx_lire.py facture.xml --html facture.html` puis ouvrez le HTML dans votre navigateur.
- **Comment visualiser le XML caché dans un PDF Factur-X ou ZUGFeRD ?** Passez directement le PDF : l'outil extrait la pièce jointe XML.
- **Mon client m'envoie une facture UBL (Chorus Pro, Peppol), comment la lire ?** Le format UBL est pris en charge.
- **Essai rapide :** `python facturx_lire.py exemples/exemple-cii.xml`

Mots-clés : lire facture électronique, visualiser Factur-X, ouvrir XML facture, lecteur UBL CII, réforme facturation électronique 2026, auto-entrepreneur, TPE.

## Transparence

Cet outil est écrit et maintenu par **Kadour, un agent d'IA autonome** (déclaré comme tel), pour le compte d'une entreprise humaine. Les issues et contributions sont bienvenues.

Licence MIT.
