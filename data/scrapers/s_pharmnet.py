"""Source 2 (priority) - Pharm'Net DZ (pharmnet-dz.com), Algeria.

The site is a Vue.js SPA on top of Supabase (PostgREST). The public
"publishable" key is embedded in the page, so the catalogue can be queried
directly:

  /rest/v1/dci      -> Algerian DCI nomenclature (code, denomination)
  /rest/v1/produits -> the product register (brand, lab, form, dosage,
                       registration number, Rcp_url, notice_url, ...)
  /rest/v1/laboratoires -> the pharmaceutical companies

Pharm'Net mostly carries the *register* information; RCP / notice documents
are rare but exist (Rcp_url / notice_url). Everything that is present is
harvested here.
"""
import json
import os
import sys
import time
import unicodedata
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http_util import get

SU = "https://yqhaaitrqqpvtcnomljm.supabase.co"
KEY = "sb_publishable_kCraKHzowqNyXwv9jfC81w_BQI7dIpK"
HEAD = {"apikey": KEY, "Authorization": "Bearer " + KEY, "Accept": "application/json"}

PRODUIT_COLS = ("id,num_enregistrement,dci_code,nom_commercial,forme,dosage,"
                "conditionnement,liste,circuit_hop,circuit_off,observation,"
                "date_enr_initial,date_enr_final,type,statut_fab,stabilite_mois,"
                "registre,prix_ppa,code_barre,notice_url,image_url,en_rupture,"
                "Rcp_url,nom_tri,moderation,updated_at")


def rest(path, params=None, timeout=90):
    url = SU + "/rest/v1/" + path
    if params:
        url += "?" + "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    r = get(url, headers=HEAD, timeout=timeout)
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return None


def _ascii(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c)).upper().strip()


def fetch_dci_codes(groups):
    """Algerian DCI codes matching the molecule.

    `groups` is a list of groups; each group is a list of alternative
    needles (accent-free, upper case). A DCI code qualifies when *every*
    group has at least one needle matching its denomination.
    """
    groups = [[_ascii(x) for x in g] for g in groups]
    groups = [g for g in groups if g]
    if not groups:
        return []
    per_group = []
    for g in groups:
        rows, seen = [], set()
        for needle in g:
            r = rest("dci", {"select": "code,denomination,sous_classe,classe_code",
                             "denomination": f"ilike.*{needle}*"})
            for row in r or []:
                if row["code"] in seen:
                    continue
                seen.add(row["code"])
                rows.append(row)
        per_group.append(rows)
    if not per_group:
        return []
    common = None
    for rows in per_group:
        codes = {r["code"]: r for r in rows}
        common = codes if common is None else {k: v for k, v in common.items() if k in codes}
        if not common:
            return []
    return list(common.values())


def fetch_produits_for_codes(codes, limit=400):
    """All products registered under one of the given DCI codes."""
    if not codes:
        return []
    rows = []
    # PostgREST `in` has a URL length limit -> chunk the codes
    for i in range(0, len(codes), 20):
        chunk = codes[i:i + 20]
        params = {
            "select": PRODUIT_COLS,
            "dci_code": "in.(" + ",".join(c.replace(" ", "%20") for c in chunk) + ")",
            "limit": limit,
        }
        r = get(SU + "/rest/v1/produits?" + "&".join(
            f"{k}={v}" for k, v in params.items()), headers=HEAD, timeout=120)
        if r.status_code != 200:
            continue
        try:
            rows.extend(r.json())
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)
    seen, uniq = set(), []
    for p in rows:
        if p.get("id") in seen:
            continue
        seen.add(p.get("id"))
        uniq.append(p)
    return uniq


def fetch_laboratories():
    rows = rest("laboratoires", {"select": "id,nom,slug,pays,est_local,site_web",
                                 "order": "nom"})
    return rows or []


def fetch_notifications():
    rows = rest("notifications", {"select": "*", "order": "created_at.desc", "limit": 500})
    return rows or []


def build_documents(drug_id, groups, dci_rows, produits, labs, notifications):
    """Turn the raw rows into structured documents."""
    lab_by_id = {l["id"]: l for l in labs}
    dci_denom = {d["code"]: d["denomination"] for d in dci_rows}
    docs = []
    for p in produits:
        lab = lab_by_id.get(p.get("laboratoire_id"), {})
        doc = {
            "source": "pharmnet",
            "source_priority": 2,
            "drug_id": drug_id,
            "language": "fr",
            "doc_type": "fiche_produit",
            "title": p.get("nom_commercial"),
            "brand": p.get("nom_commercial"),
            "dci": dci_denom.get(p.get("dci_code"), ""),
            "dci_code": p.get("dci_code"),
            "lab": lab.get("nom", ""),
            "manufacturer": lab.get("nom", ""),
            "country": lab.get("pays", ""),
            "form": p.get("forme"),
            "dosage": p.get("dosage"),
            "conditionnement": p.get("conditionnement"),
            "reg_number": p.get("num_enregistrement"),
            "reg_status": p.get("statut_fab"),
            "reg_type": p.get("type"),
            "prescription_list": p.get("liste"),
            "hospital_circuit": p.get("circuit_hop"),
            "official_circuit": p.get("circuit_off"),
            "price_ppa": p.get("prix_ppa"),
            "tarif_ref": p.get("tarif_ref"),
            "en_rupture": p.get("en_rupture"),
            "observation": p.get("observation"),
            "date_enr_initial": p.get("date_enr_initial"),
            "date_enr_final": p.get("date_enr_final"),
            "updated_at": p.get("updated_at"),
            "url": "https://www.pharmnet-dz.com/",
            "source_url": "https://www.pharmnet-dz.com/",
            "rcp_url": p.get("Rcp_url"),
            "notice_url": p.get("notice_url"),
            "sections": [],
            "text": "",
            "ingredients": [],
        }
        if doc["dci"]:
            doc["ingredients"] = [doc["dci"]]
        if doc["dosage"]:
            doc["ingredients"].append(f"Dosage : {doc['dosage']}")
        # turn the flat register fields into readable sections
        sections = []
        if doc["dci"]:
            sections.append({"key": "composition", "label": "Composition / DCI",
                             "number": None, "title": "DCI",
                             "text": doc["dci"]})
        if doc["form"] or doc["dosage"] or doc["conditionnement"]:
            t = []
            if doc["form"]:
                t.append(f"Forme pharmaceutique : {doc['form']}")
            if doc["dosage"]:
                t.append(f"Dosage : {doc['dosage']}")
            if doc["conditionnement"]:
                t.append(f"Conditionnement : {doc['conditionnement']}")
            sections.append({"key": "forme_pharmaceutique",
                             "label": "Présentation", "number": "3",
                             "title": "Forme pharmaceutique", "text": "\n".join(t)})
        sections.append({"key": "titulaire", "label": "Titulaire de l'AMM",
                         "number": "7", "title": "Titulaire de l'AMM",
                         "text": (f"{doc['lab']} ({doc['country']})\n"
                                  f"Numéro d'enregistrement : {doc['reg_number']}\n"
                                  f"Statut : {doc['reg_status']} | Type : {doc['reg_type']}\n"
                                  f"Liste : {doc['prescription_list']}\n"
                                  f"Circuit hospitalier : {doc['hospital_circuit']} | "
                                  f"Circuit officiel : {doc['official_circuit']}")})
        if doc["observation"]:
            sections.append({"key": "observation", "label": "Observations",
                             "number": None, "title": "Observations",
                             "text": doc["observation"]})
        if doc["rcp_url"]:
            sections.append({"key": "rcp_link", "label": "RCP (document)",
                             "number": None, "title": "RCP",
                             "text": f"RCP disponible : {doc['rcp_url']}"})
        if doc["notice_url"]:
            sections.append({"key": "notice_link", "label": "Notice (document)",
                             "number": None, "title": "Notice",
                             "text": f"Notice disponible : {doc['notice_url']}"})
        doc["sections"] = sections
        doc["text"] = "\n\n".join(f"{s['label']}\n{s['text']}" for s in sections)
        docs.append(doc)

    for n in notifications:
        blob = json.dumps(n, ensure_ascii=False)
        needle = _ascii(groups[0][0]) if groups and groups[0] else ""
        if needle and needle not in blob.upper():
            continue
        docs.append({
            "source": "pharmnet", "source_priority": 2, "drug_id": drug_id,
            "language": "fr", "doc_type": "notification",
            "title": n.get("titre") or n.get("title") or "Notification",
            "url": n.get("url") or "https://www.pharmnet-dz.com/",
            "sections": [{"key": "info_importante", "label": "Informations importantes",
                          "number": None, "title": n.get("titre", ""),
                          "text": json.dumps(n, ensure_ascii=False, indent=1)}],
            "text": json.dumps(n, ensure_ascii=False, indent=1),
            "ingredients": [],
        })
    return docs
