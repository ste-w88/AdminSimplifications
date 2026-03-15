from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
import pandas as pd
import os


# wenn dry_run = true dann testphase ohne aktive Dateiumbenennung
DRY_RUN = True


## Pfadangaben für Projektordner mit Dokumenten die umzubenennen sind und Pfad zur Projektliste
## mit Angaben Bauwerksbezeichnung, Dokumenttypbezeichnung sowie Nummerierungen
## ideal in der Form:
## 4.5.35;24.0;Stützmauer Colra;Überprüfungsbericht
## 4.5.46;25.0;Wandmauer Colra II;Nutzungsvereinbarung

file_project_list = "Projektliste-textverknüpft.txt"
folder_name_pl = "Daten"
folder_name_data = "Daten_Try"
folder_name_parent = os.path.dirname(os.getcwd())

project_folder = Path(os.path.join(folder_name_parent, folder_name_data))
path_proj_list = Path(os.path.join(os.path.dirname(__file__), folder_name_pl, file_project_list))

# --------- Erzeugung Projektliste (beilagen_nr, dok_nr, bauwerk, doc_typ) ---------

## erstellt die Projektliste, d.h. Bauwerke werden mit Dokumenttypen verknüpft und mit Nr. aus Inhaltsverzeichnis versehen
@dataclass(frozen=True)
class ProjectEntry:
    beilagen_nr: str
    dok_nr: str
    bauwerk: str
    doc_typ: str
    
def projectList(path: Path) -> list[ProjectEntry]:

    df = pd.read_csv(path, sep=";", header=None)

    project_list = []

    for _, row in df.iterrows():

        project_list.append(
            ProjectEntry(
                beilagen_nr=str(row[0]),
                dok_nr=str(row[1]),
                bauwerk=str(row[2]),
                doc_typ=str(row[3])
            )
        )

    return project_list


######! besser aus project_list nehmen
## Auflistung relevanten Bauwerksnamen und Dokumenttypen (diese Daten sind im Inhaltsverzeichnis ebenfalls enthalten)
bw_list = ["Stützmauer Nesslaboden I", "Wandmauer Nesslaboden I", "Wandmauer Nesslaboden II", "Stützmauer Nesslaboden II", "Wandmauer Nesslaboden III", "Stützmauer Nesslaboden III",
           "Stützmauer Nesslaboden IV", "Wandmauer Colra I", "Wandmauer Colra II", "Stützmauer Colra", "Wandmauer Foppa", "Stützmauer Umleitungsstollen Bargiasbach",
           "Stützmauer Ausstellplatz Ost", "Stützmauer Compogna V", "Stützmauer Compogna VI", "Stützmauer Compogna VII", "Stützmauer Compogna VIII", "Stützmauer Nolla IV",
           "Stützmauer Hinterrheinbrücke I", "Stützmauer Hinterrheinbrücke II"]


######! besser aus project_list nehmen
## Dokumenttypen und Aliases 
DOC_ALIASES: dict[str, list[str]] = {
    "statische berechnungen": ["statik", "statisch", "statischer bericht"],
    "projektbasis": [],
    "nutzungsvereinbarung": [],
    "überprüfungsbericht": ["ueberpruefungsbericht", "überprüfung", "pruefbericht", "prüfbericht"],
    "technischer bericht": ["technisch"],
    "faktenblatt": []
}

## offiziellen Dokumenttypbezeichnungen
doc_list = [f.lower() for f in DOC_ALIASES]


## Unterordner im Hauptprojektordner die ebenfalls zu berücksichtigen sind (optional)
# mit letter_starts angegben mit welchen Ziffern die Ordner beginnen 
# ansonsten werden nur Dokumente im Hauptordner berücksichtigt
def mainFolders(letter_starts: list[str], main_path: list[Path] = [project_folder]) -> list[Path]:
    main_folders = []
    for ele_main_path in main_path:
        folder_all = [f for f in ele_main_path.iterdir() if f.is_dir()]
        for ele_path in folder_all:
            for ele_let in letter_starts:
                length_letter = len(ele_let)
                if ele_path.name[:length_letter]==ele_let:
                    main_folders.append(ele_path)
    return main_folders


## Normalisierung Bauwerksindex (II/VIII vs 2/8)
_ROMAN = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
    "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
}

def roman_to_int(s: str) -> Optional[int]:
    return _ROMAN.get(s.lower())

## Normalisierung Text
# alles Kleinbuchstaben und "-" sowie "_" ersetzt durch Leerzeichen
# Abstände am Anfang und Ende des Textes werden entfernt
def normalize_text(s: str) -> str:
    s = str(s).lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

## Trennung Bauwerksziffer und Bauwerksname. Bauwerksziffer wird zum Index
# z.B. colra ii -> base=colra, idx=ii 
def split_base_and_index(name: str) -> tuple[str, Optional[int]]:
    """
    Akzeptiert:
    - 'colra ii', 'colra_ii', 'colra-ii'
    - 'colra 2', 'colra2'
    - 'compogna viii', 'compogna 8'
    """
    name = normalize_text(name)

    # 'base <idx>'
    m = re.match(r"^(.*?)(?:\s+)(\d+|[ivx]+)$", name)
    if m:
        base = m.group(1).strip()
        raw = m.group(2)
        idx = int(raw) if raw.isdigit() else roman_to_int(raw)
        return base, idx

    # 'base<idx>'
    m = re.match(r"^(.*?)(\d+|[ivx]+)$", name)
    if m:
        base = m.group(1).strip()
        raw = m.group(2)
        idx = int(raw) if raw.isdigit() else roman_to_int(raw)
        return base, idx

    return name, None


## entnehmen Bauwerkstyp (bw_typ), Name (base) und Index (idx)
# z.B. 09_WM_Colra_II -> bw_typ=wandmauer, base=colra, idx=ii
def parse_bauwerk(text: str) -> tuple[str, str, Optional[int]]:
    """
    Input kann sein:
    - 'Wandmauer Colra II' (Projektliste)
    - Ordnername wie '09_WM_Colra_II'
    - Dateiname mit 'Wm-Colra-II', 'Compogna_8' etc.
    """
    t = normalize_text(text)

    token_map = {
        "wm": "wandmauer",
        "wandmauer": "wandmauer",
        "stm": "stützmauer",
        "stutzmauer": "stützmauer",
        "stützmauer": "stützmauer",
        "stuetzmauer": "stützmauer",
    }

    parts = t.split()
    bw_typ = ""
    typ_pos = None

    for i, tok in enumerate(parts):
        if tok in token_map:
            bw_typ = token_map[tok]
            typ_pos = i
            break

    # Wenn im Text kein Typ vorkommt (z.B. nur 'Colra II'), dann bw_typ leer lassen
    rest = " ".join(parts[typ_pos + 1 :]) if typ_pos is not None else t
    base, idx = split_base_and_index(rest)
    return bw_typ, base, idx

## Entnahme offizielle Dokumentypbezeichnung (siehe Liste DOC_ALIASES ganz am Anfang)
def normalize_doc_type(text: str) -> Optional[str]:
    t = normalize_text(text)
    for canonical, aliases in DOC_ALIASES.items():
        if canonical in t:
            return canonical
        if any(a in t for a in aliases):
            return canonical
    return None


## erzeugte Projektliste siehe Anfang mit Index versehen pro Bauwerk und Dokumenttypbezeichnung

Key = tuple[str, str, Optional[int], str]  # (bw_typ, bw_base, bw_idx, doc_typ)

def build_project_index(project_list: Iterable[ProjectEntry]) -> dict[Key, list[ProjectEntry]]:
    """
    Mehrere Einträge pro Key möglich => list (für MULTI_MATCH-Report).
    """
    index: dict[Key, list[ProjectEntry]] = {}

    for p in project_list:
        bw_typ, bw_base, bw_idx = parse_bauwerk(p.bauwerk)
        doc = normalize_doc_type(p.doc_typ) or normalize_text(p.doc_typ)

        key = (bw_typ, bw_base, bw_idx, doc)
        index.setdefault(key, []).append(p)

    return index


## sammeln aller Files aus den relevanten Ordnern
# Möglichkeit zum Angeben von Sperrbezeichnungen wie "Alt" oder "Anhang" im Dateinamen -> sind von Umbenennung ausgeschlossen
# oder auch ignorierende Dateitypen z.B. ".png"
def collect_files(
    folders: Iterable[Path],
    sperr_bez: list[str] | None = None,
    ignore_suffixes: list[str] | None = None,
) -> list[Path]:
    sperr = [s.lower() for s in (sperr_bez or [])]
    ignore_suffixes = ignore_suffixes or [".lnk"]

    files: list[Path] = []
    for folder in folders:
        for p in folder.iterdir():
            if not p.is_file():
                """ print(f"Das gefundene Element ist kein File: {p.name}")
                print("exists:", p.exists())
                print("is_file:", p.is_file())
                print("is_dir:", p.is_dir())
                print("is_symlink:", p.is_symlink())
                print("suffix:", p.suffix)
                print("full path:", p)
                print("---") """
                continue
            if any(p.name.lower().endswith(suf.lower()) for suf in ignore_suffixes):
                continue
            name_lower = p.name.lower()
            if any(block in name_lower for block in sperr):
                continue
            if p.name.startswith("~$"):
                continue
            files.append(p)
    return files


@dataclass(frozen=True)
class MatchResult:
    status: str  # OK / NO_MATCH / MULTI_MATCH
    file: Path
    key: Key
    matches: list[ProjectEntry]


## matchen Files mit Projektliste
def match_files(files: Iterable[Path], project_index: dict[Key, list[ProjectEntry]]) -> list[MatchResult]:
    results: list[MatchResult] = []

    for f in files:
        # Bauwerk bevorzugt aus Ordnernamen (bei euch sehr stabil: 09_WM_Colra_II etc.)
        bw_typ, bw_base, bw_idx = parse_bauwerk(f.parent.name)

        # Fallback: wenn Typ leer bleibt, aus Datei versuchen
        if not bw_typ:
            bw_typ2, bw_base2, bw_idx2 = parse_bauwerk(f.name)
            bw_typ, bw_base, bw_idx = bw_typ2, bw_base2, bw_idx2

        doc = normalize_doc_type(f.name)
        if doc is None:
            # Datei enthält keinen erkennbaren Dokumenttyp
            key = (bw_typ, bw_base, bw_idx, "")
            results.append(MatchResult("NO_MATCH", f, key, []))
            continue

        key = (bw_typ, bw_base, bw_idx, doc)
        hits = project_index.get(key, [])

        if not hits:
            results.append(MatchResult("NO_MATCH", f, key, []))
        elif len(hits) == 1:
            results.append(MatchResult("OK", f, key, hits))
        else:
            results.append(MatchResult("MULTI_MATCH", f, key, hits))

    return results

## Erstellung neuer Dateiname
def build_new_filename(entry: ProjectEntry, original_suffix: str) -> str:
    """
    Namensschema nach deinem Textfile-Beispiel:
    <BeilagenNr>_<DokNr>_<Bauwerk>_<DocTyp><Suffix>
    -> du kannst das leicht ändern.
    """
    bw = entry.bauwerk.replace("  ", " ").strip()
    bw = bw.replace(" ", "_")
    doc = entry.doc_typ.replace("  ", " ").strip()
    return f"{entry.beilagen_nr}_{bw}_{doc}{original_suffix}"

## Datei umbenennen mit neuem Dateinamen
def plan_renames(matches: Iterable[MatchResult]) -> list[tuple[Path, Path]]:
    plans: list[tuple[Path, Path]] = []
    for m in matches:
        if m.status != "OK":
            continue
        entry = m.matches[0]
        new_name = build_new_filename(entry, m.file.suffix)
        new_path = m.file.with_name(new_name)
        plans.append((m.file, new_path))
    return plans
    
   
# -------- ab hier beginnt das Hauptprogramm (oben sind alle Funktionen aufgelistet) ------- #
   
    
## Erzeugung Projektliste mit Index
project_list = projectList(path_proj_list)

""" for e in project_list:
    print(e) """
    
project_index = build_project_index(project_list)

""" for e in project_index:
    print(e) """


## Files ermitteln
letter_starts = ["01"]
main_folders = mainFolders(letter_starts)
#main_folders = [project_folder]

sperr_bez = ["Alt","Anhang","Anwend","Anpass"]
files = collect_files(main_folders,sperr_bez)

""" for e in files:
    print(e.name) """

## Liste: welche Files sind in Projektliste und welche nicht
matches = match_files(files, project_index)

for e in matches:
    print(f"{e.status} : {e.file.name} : {e.key}")

rename_plan = plan_renames(matches)


if DRY_RUN:
    print("Anzahl Dateien umzubenennen: ",len(rename_plan))
    for e in rename_plan:
        print(f"Alt: {e[0].name} / Neu: {e[1].name}")
else:
    for old_path, new_path in rename_plan:
        print(f"Alt: {old_path.name} / Neu: {new_path.name}")
        old_path.replace(new_path)
  
    
   