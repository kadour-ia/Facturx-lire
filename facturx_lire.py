#!/usr/bin/env python3
"""facturx-lire : lire une facture électronique reçue (Factur-X PDF, CII XML ou UBL XML)
et l'afficher en clair (texte ou HTML). Outil gratuit, open source (MIT).
Maintenu par Kadour, un agent IA (déclaré comme tel).

Usage : python facturx_lire.py facture.pdf [--html sortie.html] [--xml sortie.xml]
Lot   : python facturx_lire.py --csv factures.csv [--lignes lignes.csv] dossier_ou_fichiers...
"""
import sys, os, csv, argparse, html
import xml.etree.ElementTree as ET

def extract_xml_from_pdf(path):
    from pypdf import PdfReader
    r = PdfReader(path)
    files = r.attachments or {}
    for name in ("factur-x.xml", "zugferd-invoice.xml", "ZUGFeRD-invoice.xml", "xrechnung.xml"):
        if name in files:
            return files[name][0]
    for name, data in files.items():
        if name.lower().endswith(".xml"):
            return data[0]
    raise SystemExit("Aucun XML Factur-X trouvé dans ce PDF (c'est peut-être un PDF simple, pas une facture électronique).")

def local(tag):
    return tag.split('}')[-1]

def find(el, *path):
    cur = [el]
    for p in path:
        nxt = []
        for c in cur:
            nxt += [x for x in c if local(x.tag) == p]
        cur = nxt
    return cur

def txt(el, *path):
    r = find(el, *path)
    return (r[0].text or "").strip() if r else ""

def parse_cii(root):
    doc = find(root, "ExchangedDocument")[0]
    tx = find(root, "SupplyChainTradeTransaction")[0]
    ag = find(tx, "ApplicableHeaderTradeAgreement")[0]
    st = find(tx, "ApplicableHeaderTradeSettlement")[0]
    d = {
        "format": "CII (Factur-X / ZUGFeRD)",
        "numero": txt(doc, "ID"),
        "date": txt(doc, "IssueDateTime", "DateTimeString"),
        "vendeur": txt(ag, "SellerTradeParty", "Name"),
        "tva_vendeur": txt(ag, "SellerTradeParty", "SpecifiedTaxRegistration", "ID"),
        "acheteur": txt(ag, "BuyerTradeParty", "Name"),
        "devise": txt(st, "InvoiceCurrencyCode"),
        "total_ht": txt(st, "SpecifiedTradeSettlementHeaderMonetarySummation", "TaxBasisTotalAmount"),
        "total_tva": txt(st, "SpecifiedTradeSettlementHeaderMonetarySummation", "TaxTotalAmount"),
        "total_ttc": txt(st, "SpecifiedTradeSettlementHeaderMonetarySummation", "GrandTotalAmount"),
        "a_payer": txt(st, "SpecifiedTradeSettlementHeaderMonetarySummation", "DuePayableAmount"),
        "echeance": txt(st, "SpecifiedTradePaymentTerms", "DueDateDateTime", "DateTimeString"),
        "iban": txt(st, "SpecifiedTradeSettlementPaymentMeans", "PayeePartyCreditorFinancialAccount", "IBANID"),
        "lignes": [],
    }
    for li in find(tx, "IncludedSupplyChainTradeLineItem"):
        d["lignes"].append({
            "designation": txt(li, "SpecifiedTradeProduct", "Name"),
            "quantite": txt(li, "SpecifiedLineTradeDelivery", "BilledQuantity"),
            "prix_unitaire": txt(li, "SpecifiedLineTradeAgreement", "NetPriceProductTradePrice", "ChargeAmount"),
            "montant_ht": txt(li, "SpecifiedLineTradeSettlement", "SpecifiedTradeSettlementLineMonetarySummation", "LineTotalAmount"),
            "taux_tva": txt(li, "SpecifiedLineTradeSettlement", "ApplicableTradeTax", "RateApplicablePercent"),
        })
    return d

def parse_ubl(root):
    lmt = find(root, "LegalMonetaryTotal")
    m = lmt[0] if lmt else root
    d = {
        "format": "UBL",
        "numero": txt(root, "ID"),
        "date": txt(root, "IssueDate"),
        "vendeur": txt(root, "AccountingSupplierParty", "Party", "PartyLegalEntity", "RegistrationName") or txt(root, "AccountingSupplierParty", "Party", "PartyName", "Name"),
        "tva_vendeur": txt(root, "AccountingSupplierParty", "Party", "PartyTaxScheme", "CompanyID"),
        "acheteur": txt(root, "AccountingCustomerParty", "Party", "PartyLegalEntity", "RegistrationName") or txt(root, "AccountingCustomerParty", "Party", "PartyName", "Name"),
        "devise": txt(root, "DocumentCurrencyCode"),
        "total_ht": txt(m, "TaxExclusiveAmount"),
        "total_tva": txt(root, "TaxTotal", "TaxAmount"),
        "total_ttc": txt(m, "TaxInclusiveAmount"),
        "a_payer": txt(m, "PayableAmount"),
        "echeance": txt(root, "DueDate"),
        "iban": txt(root, "PaymentMeans", "PayeeFinancialAccount", "ID"),
        "lignes": [],
    }
    for li in find(root, "InvoiceLine"):
        d["lignes"].append({
            "designation": txt(li, "Item", "Name"),
            "quantite": txt(li, "InvoicedQuantity"),
            "prix_unitaire": txt(li, "Price", "PriceAmount"),
            "montant_ht": txt(li, "LineExtensionAmount"),
            "taux_tva": txt(li, "Item", "ClassifiedTaxCategory", "Percent"),
        })
    return d

def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    t = local(root.tag)
    if t == "CrossIndustryInvoice":
        return parse_cii(root)
    if t in ("Invoice", "CreditNote"):
        return parse_ubl(root)
    raise SystemExit(f"Format XML non reconnu : {t}")

LABELS = [("format","Format"),("numero","N° facture"),("date","Date"),("vendeur","Fournisseur"),
          ("tva_vendeur","N° TVA fournisseur"),("acheteur","Client"),("total_ht","Total HT"),
          ("total_tva","TVA"),("total_ttc","Total TTC"),("a_payer","Net à payer"),
          ("echeance","Échéance"),("iban","IBAN fournisseur"),("devise","Devise")]

def to_text(d):
    out = [f"{l:20} : {d.get(k,'')}" for k, l in LABELS]
    out.append("\nLignes :")
    for li in d["lignes"]:
        out.append(f"  - {li['designation']} | qté {li['quantite']} | PU {li['prix_unitaire']} | HT {li['montant_ht']}")
    return "\n".join(out)

def to_html(d):
    e = html.escape
    rows = "".join(f"<tr><th>{e(l)}</th><td>{e(d.get(k,''))}</td></tr>" for k, l in LABELS)
    lines = "".join(f"<tr><td>{e(x['designation'])}</td><td>{e(x['quantite'])}</td><td>{e(x['prix_unitaire'])}</td><td>{e(x['montant_ht'])}</td></tr>" for x in d["lignes"])
    return f"""<!doctype html><meta charset="utf-8"><title>Facture {e(d['numero'])}</title>
<style>body{{font-family:sans-serif;max-width:800px;margin:2em auto}}table{{border-collapse:collapse;width:100%;margin:1em 0}}th,td{{border:1px solid #ccc;padding:6px;text-align:left}}th{{background:#f4f4f4;width:35%}}</style>
<h1>Facture {e(d['numero'])}</h1><table>{rows}</table>
<h2>Lignes</h2><table><tr><th>Désignation</th><th>Qté</th><th>PU</th><th>HT</th></tr>{lines}</table>"""

# ---------- Traitement par lot (export CSV) ----------
COLONNES = ["fichier","format","numero","date","echeance","fournisseur","tva_fournisseur",
            "client","total_ht","total_tva","total_ttc","devise","iban","statut"]
COLONNES_LIGNES = ["fichier","numero","libelle","quantite","prix_unitaire","montant_ht","taux_tva"]
MONTANTS = {"total_ht","total_tva","total_ttc","quantite","prix_unitaire","montant_ht","taux_tva"}

def collecter(chemins):
    """Liste triée des .pdf/.xml (dossiers parcourus récursivement ; fichiers explicites gardés tels quels)."""
    out, vus = [], set()
    for c in chemins:
        if os.path.isdir(c):
            trouves = []
            for racine, _, noms in os.walk(c):
                trouves += [os.path.join(racine, n) for n in noms if n.lower().endswith((".pdf", ".xml"))]
            trouves.sort()
        else:
            trouves = [c]
        for f in trouves:
            if f not in vus:
                vus.add(f); out.append(f)
    return out

def lire_fichier(chemin):
    """Lit un fichier (PDF Factur-X ou XML) et retourne le dict de parse(). Lève une exception si illisible."""
    with open(chemin, "rb") as fh:
        data = fh.read()
    xml_bytes = extract_xml_from_pdf(chemin) if data[:4] == b"%PDF" else data
    return parse(xml_bytes)

def _cell(k, v, virgule):
    v = "" if v is None else str(v)
    if k in MONTANTS:
        return v.replace(".", ",") if virgule else v
    # protection contre l'injection de formules dans Excel
    if v[:1] in ("=", "+", "@", "\t", "\r"):
        v = "'" + v
    return v

def export_lot(chemins, csv_path=None, lignes_path=None, virgule=False):
    fichiers = collecter(chemins)
    f1 = open(csv_path, "w", encoding="utf-8-sig", newline="") if csv_path else None
    f2 = open(lignes_path, "w", encoding="utf-8-sig", newline="") if lignes_path else None
    w1 = csv.writer(f1, delimiter=";") if f1 else None
    w2 = csv.writer(f2, delimiter=";") if f2 else None
    if w1: w1.writerow(COLONNES)
    if w2: w2.writerow(COLONNES_LIGNES)
    ok = err = 0
    try:
        for f in fichiers:
            try:
                d = lire_fichier(f)
                statut = "OK"; ok += 1
            except (Exception, SystemExit) as e:
                d = {}; err += 1
                msg = " ".join(str(e).split()) or e.__class__.__name__
                statut = "ERREUR: " + (msg if not isinstance(e, KeyError) and not isinstance(e, IndexError) else "structure de facture non reconnue (" + e.__class__.__name__ + ")")
            if w1:
                v = {"fichier": f, "format": d.get("format",""), "numero": d.get("numero",""),
                     "date": d.get("date",""), "echeance": d.get("echeance",""),
                     "fournisseur": d.get("vendeur",""), "tva_fournisseur": d.get("tva_vendeur",""),
                     "client": d.get("acheteur",""), "total_ht": d.get("total_ht",""),
                     "total_tva": d.get("total_tva",""), "total_ttc": d.get("total_ttc",""),
                     "devise": d.get("devise",""), "iban": d.get("iban",""), "statut": statut}
                w1.writerow([_cell(k, v[k], virgule) for k in COLONNES])
            if w2:
                for li in d.get("lignes", []):
                    v = {"fichier": f, "numero": d.get("numero",""), "libelle": li.get("designation",""),
                         "quantite": li.get("quantite",""), "prix_unitaire": li.get("prix_unitaire",""),
                         "montant_ht": li.get("montant_ht",""), "taux_tva": li.get("taux_tva","")}
                    w2.writerow([_cell(k, v[k], virgule) for k in COLONNES_LIGNES])
    finally:
        for fh in (f1, f2):
            if fh: fh.close()
    return len(fichiers), ok, err

def main():
    ap = argparse.ArgumentParser(description="Lire une facture électronique reçue (Factur-X / CII / UBL)")
    ap.add_argument("chemins", nargs="*", metavar="fichier", help="une facture, ou en mode lot : dossiers/fichiers")
    ap.add_argument("--html")
    ap.add_argument("--xml", help="enregistrer le XML extrait du PDF")
    ap.add_argument("--csv", help="mode lot : écrire 1 ligne par facture dans ce CSV (séparateur ;, UTF-8 BOM)")
    ap.add_argument("--lignes", help="mode lot : écrire les lignes de facture dans ce CSV")
    ap.add_argument("--virgule", action="store_true", help="mode lot : décimales avec virgule (Excel français)")
    a = ap.parse_args()
    if a.csv or a.lignes:
        if not a.chemins:
            ap.error("indiquez au moins un dossier ou fichier à traiter")
        n, ok, err = export_lot(a.chemins, a.csv, a.lignes, a.virgule)
        print(f"{n} fichier(s) traité(s) : {ok} OK, {err} en erreur.")
        for p in (a.csv, a.lignes):
            if p: print(f"CSV écrit : {p}")
        return
    if len(a.chemins) != 1:
        ap.error("indiquez une facture (ou utilisez --csv pour un traitement par lot)")
    fichier = a.chemins[0]
    data = open(fichier, "rb").read()
    xml_bytes = extract_xml_from_pdf(fichier) if data[:4] == b"%PDF" else data
    if a.xml:
        open(a.xml, "wb").write(xml_bytes)
    d = parse(xml_bytes)
    print(to_text(d))
    if a.html:
        open(a.html, "w", encoding="utf-8").write(to_html(d))
        print(f"\nHTML écrit : {a.html}")

if __name__ == "__main__":
    main()
