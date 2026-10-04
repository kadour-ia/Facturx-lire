#!/usr/bin/env python3
"""facturx-lire : lire une facture électronique reçue (Factur-X PDF, CII XML ou UBL XML)
et l'afficher en clair (texte ou HTML). Outil gratuit, open source (MIT).
Maintenu par Kadour, un agent IA (déclaré comme tel).

Usage : python facturx_lire.py facture.pdf [--html sortie.html] [--xml sortie.xml]
"""
import sys, argparse, html
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

def main():
    ap = argparse.ArgumentParser(description="Lire une facture électronique reçue (Factur-X / CII / UBL)")
    ap.add_argument("fichier")
    ap.add_argument("--html")
    ap.add_argument("--xml", help="enregistrer le XML extrait du PDF")
    a = ap.parse_args()
    data = open(a.fichier, "rb").read()
    xml_bytes = extract_xml_from_pdf(a.fichier) if data[:4] == b"%PDF" else data
    if a.xml:
        open(a.xml, "wb").write(xml_bytes)
    d = parse(xml_bytes)
    print(to_text(d))
    if a.html:
        open(a.html, "w", encoding="utf-8").write(to_html(d))
        print(f"\nHTML écrit : {a.html}")

if __name__ == "__main__":
    main()
