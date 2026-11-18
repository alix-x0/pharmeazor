"""French RCP (Résumé des Caractéristiques du Produit) section parser.

Works on two input shapes:
  * plain text (PDF extraction, e.g. ANPP)  -> parse_rcp_text()
  * ANSM/BDPM HTML with `Amm*` CSS classes -> parse_rcp_html()

The canonical section keys are shared across all sources so that the RAG
index can be queried uniformly (e.g. "contre_indications" always means the
same thing whatever the source).
"""
import re

from textutil import fold, normalize_text, strip_accents


def fold_match(s: str) -> str:
    """Folding used for heading matching: accents removed, hyphens/apostrophes
    turned into spaces so that "Contre-indications" == "contre indications"."""
    s = fold(s)
    s = re.sub(r"[-'’ʼ]", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# ---------------------------------------------------------------- canonical map
# key -> (regexp over folded title, human label)
CANON = {
    "denomination": (r"^denomination du medicament", "Dénomination du médicament"),
    "nom_commercial": (r"^denomination commerciale", "Dénomination commerciale"),
    "dci": (r"^denomination commune internationale", "DCI"),
    "composition": (r"^composition qualitative et quantitative", "Composition qualitative et quantitative"),
    "forme_pharmaceutique": (r"^forme pharmaceutique", "Forme pharmaceutique"),
    "donnees_cliniques": (r"^donnees cliniques", "Données cliniques"),
    "indications": (r"^indications therapeutiques", "Indications thérapeutiques"),
    "posologie": (r"^posologie", "Posologie et mode d'administration"),
    "contre_indications": (r"^contre indications", "Contre-indications"),
    "mises_en_garde": (r"^mises en garde", "Mises en garde et précautions d'emploi"),
    "interactions": (r"^interaction", "Interactions médicamenteuses"),
    "fertilite_grossesse": (r"^fertilite grossesse", "Fertilité, grossesse et allaitement"),
    "aptitude_conduite": (r"^effets sur l aptitude a conduire", "Aptitude à conduire"),
    "effets_indesirables": (r"^effets indesirables", "Effets indésirables"),
    "surdosage": (r"^surdosage", "Surdosage"),
    "proprietes_pharmacologiques": (r"^proprietes pharmacologiques", "Propriétés pharmacologiques"),
    "pharmacodynamique": (r"^proprietes pharmacodynamiques", "Propriétés pharmacodynamiques"),
    "pharmacocinetique": (r"^proprietes pharmacocinetiques", "Propriétés pharmacocinétiques"),
    "securite_preclinique": (r"^donnees de securite preclinique", "Données de sécurité préclinique"),
    "donnees_pharmaceutiques": (r"^donnees pharmaceutiques", "Données pharmaceutiques"),
    "excipients": (r"^liste des excipients", "Liste des excipients"),
    "incompatibilites": (r"^incompatibilites", "Incompatibilités"),
    "duree_conservation": (r"^duree de conservation", "Durée de conservation"),
    "precautions_conservation": (r"^precautions particulieres de conservation", "Précautions de conservation"),
    "conditionnement": (r"^nature et contenu de l emballage", "Nature et contenu de l'emballage"),
    "elimination": (r"^precautions particulieres d elimination", "Précautions d'élimination"),
    "titulaire": (r"^titulaire de l autorisation", "Titulaire de l'AMM"),
    "numero_autorisation": (r"^numero", "Numéro d'AMM"),
    "date_premiere_autorisation": (r"^date de premiere autorisation", "Date de première autorisation"),
    "date_mise_a_jour": (r"^date de mise a jour du texte", "Date de mise à jour du texte"),
    "dosimetrie": (r"^dosimetrie", "Dosimétrie"),
    "radiopharma": (r"^instructions pour la preparation des radiopharmaceutiques", "Instructions radiopharmaceutiques"),
    "info_importante": (r"^informations importantes", "Informations importantes"),
}

# numeric code -> canonical key (used when the heading number is available)
CODE_MAP = {
    "1": "denomination", "2": "composition", "3": "forme_pharmaceutique",
    "4": "donnees_cliniques", "4.1": "indications", "4.2": "posologie",
    "4.3": "contre_indications", "4.4": "mises_en_garde", "4.5": "interactions",
    "4.6": "fertilite_grossesse", "4.7": "aptitude_conduite", "4.8": "effets_indesirables",
    "4.9": "surdosage", "5": "proprietes_pharmacologiques", "5.1": "pharmacodynamique",
    "5.2": "pharmacocinetique", "5.3": "securite_preclinique", "6": "donnees_pharmaceutiques",
    "6.1": "excipients", "6.2": "incompatibilites", "6.3": "duree_conservation",
    "6.4": "precautions_conservation", "6.5": "conditionnement", "6.6": "elimination",
    "7": "titulaire", "8": "numero_autorisation", "9": "date_premiere_autorisation",
    "10": "date_mise_a_jour", "11": "dosimetrie", "12": "radiopharma",
}

# headings that are only "chapter" titles and must not swallow subsections
_CHAPTER_ONLY = {"donnees_cliniques", "donnees_pharmaceutiques",
                 "proprietes_pharmacologiques"}

# ---------------------------------------------------------- heading detection
_NUM_HEAD = re.compile(
    r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\s*[.)]?\s*(\S.{2,150})$")


def _classify(num, title):
    """Return (canonical_key, matched_len) for a heading, or (None, 0).

    The *title* must match a known RCP heading; the section number is only
    used to disambiguate (it is never enough on its own, otherwise body
    lines such as "2. 000 mg chez l'enfant ..." would be read as headings).
    """
    folded = fold_match(title)
    matches = []
    for k, (pat, _lbl) in CANON.items():
        m = re.match(pat, folded)
        if m:
            matches.append((k, m.end()))
    if not matches:
        return None, 0
    # the number, when present, wins if it points at one of the candidates
    if num:
        wanted = CODE_MAP.get(num)
        for k, _end in matches:
            if k == wanted:
                return k, dict((kk, ee) for kk, ee in matches)[k]
    # otherwise the longest title match wins
    matches.sort(key=lambda x: -x[1])
    return matches[0][0], matches[0][1]


def _is_heading_line(line, min_len=3, max_len=160):
    """Heuristic: does this line look like an RCP heading?"""
    s = line.strip()
    if not s or len(s) < min_len or len(s) > max_len:
        return False
    if s.endswith((".", ",", ";", ":", "!", "?")) and not re.match(r"^\d", s):
        return False
    if re.match(r"^\d{1,2}(?:\.\d{1,2})*\s+[a-zà-ÿ]", s):
        # numbered sentence in body text -> not a heading (lowercase start)
        return False
    return True


def _looks_like_body_continuation(title, matched_len):
    """True when the line starts with a known heading phrase but then keeps
    going (e.g. "Liste des excipients : benzoate de sodium, ...")."""
    rest = fold_match(title)[matched_len:].strip()
    if not rest:
        return False
    if rest[0] in ":;,":
        return True
    return len(rest) > 60


def parse_rcp_text(text):
    """Split plain French RCP text into canonical sections.

    Returns list of dicts: {key, label, number, title, text}
    """
    text = normalize_text(text or "")
    if not text:
        return []
    lines = text.split("\n")
    sections = []
    cur = None

    def start(key, number, title):
        nonlocal cur
        cur = {"key": key, "label": CANON.get(key, (None, key))[1],
               "number": number, "title": title.strip(), "text": ""}
        sections.append(cur)

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            if cur is not None:
                cur["text"] += "\n"
            continue

        key = None
        num = None
        title = None
        matched = 0
        m = _NUM_HEAD.match(stripped)
        if m and _is_heading_line(stripped):
            cand_num, cand_title = m.group(1), m.group(2)
            k, ml = _classify(cand_num, cand_title)
            if k and not _looks_like_body_continuation(cand_title, ml):
                key, num, title, matched = k, cand_num, cand_title, ml
        if key is None and _is_heading_line(stripped):
            # heading without leading number
            k, ml = _classify(None, stripped)
            if k and not _looks_like_body_continuation(stripped, ml):
                key, num, title, matched = k, None, stripped, ml

        if key:
            if cur is not None and cur["key"] == key and not cur["text"].strip():
                # duplicate/continued heading -> keep the first one
                cur["text"] += ""
                continue
            start(key, num, title)
        elif cur is not None:
            cur["text"] += line + "\n"

    out = []
    for s in sections:
        s["text"] = re.sub(r"\n{3,}", "\n\n", s["text"]).strip()
        if s["text"] or s["key"] in CANON:
            out.append(s)
    return out


# ------------------------------------------------------------------- HTML path
_HTML_TITLE_CLASSES = ("AmmAnnexeTitre1", "AmmAnnexeTitre2", "AmmAnnexeTitre3")


def parse_rcp_html(panel_soup):
    """Parse a BDPM/ANSM `Amm*` styled HTML block into canonical sections."""
    sections = []
    cur = None
    for el in panel_soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5"]):
        classes = el.get("class") or []
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        is_title = any(c in classes for c in _HTML_TITLE_CLASSES)
        if not is_title:
            if cur is not None and not el.find(["p", "div", "li"], recursive=True):
                cur["text"] += txt + "\n"
            continue
        m = re.match(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\s*[.)]?\s*(\S.*)$", txt)
        num, title = (m.group(1), m.group(2)) if m else (None, txt)
        key, _ml = _classify(num, title)
        if key is None:
            continue
        cur = {"key": key, "label": CANON.get(key, (None, key))[1],
               "number": num, "title": title.strip(), "text": ""}
        sections.append(cur)
    for s in sections:
        s["text"] = re.sub(r"\n{3,}", "\n\n", s["text"]).strip()
    return sections


def extract_ingredients(section_text):
    """Best-effort split of the composition section into ingredient lines."""
    if not section_text:
        return []
    out = []
    for line in section_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(pour|excipient|excipients)\b", fold(line)):
            out.append(line)
            continue
        if re.search(r"\d", line):
            out.append(line)
    return out


def section_index(sections):
    """key -> section dict (first wins)."""
    idx = {}
    for s in sections:
        if s["key"] not in idx:
            idx[s["key"]] = s
    return idx
