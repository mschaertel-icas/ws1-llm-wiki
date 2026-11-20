#!/usr/bin/env python3
"""Zeichnet den Linkgraph des LLM-Wikis als Mermaid-Diagramm.

Aufruf:  python tools/wiki_graph.py [--wiki wiki] [--out docs/wiki-graph.md]
Ergebnis: Markdown-Datei mit einem Mermaid-Diagramm (graph LR). Ein Knoten pro
Wiki-Seite (Beschriftung = titel aus der Kopfzeile), ein Pfeil pro Link.
Seiten, auf die keine andere Seite verlinkt, werden rot markiert.
wiki/index.md und wiki/log.md werden ausgeblendet, weil sie ohnehin alles verlinken.
Nur Standardbibliothek – keine Installation nötig.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SONDERSEITEN = {"index.md", "log.md"}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def lies_titel(text: str, fallback: str) -> str:
    """titel aus der Frontmatter, sonst erste Überschrift, sonst fallback."""
    if text.startswith("---"):
        teile = text.split("\n---", 1)
        if len(teile) == 2:
            for zeile in teile[0].splitlines()[1:]:
                m = re.match(r"^titel:\s*(.*)$", zeile)
                if m:
                    titel = m.group(1).split(" #", 1)[0].strip()
                    if len(titel) >= 2 and titel[0] == titel[-1] and titel[0] in "'\"":
                        titel = titel[1:-1]
                    if titel:
                        return titel
    for zeile in text.splitlines():
        if zeile.startswith("# "):
            return zeile[2:].strip()
    return fallback


def ist_sonderseite(pfad: Path, wiki: Path) -> bool:
    return pfad.parent == wiki and pfad.name in SONDERSEITEN


def finde_links(seite: Path, text: str, wiki: Path) -> set[Path]:
    """Alle relativen Links von seite auf andere (existierende) Wiki-Seiten."""
    wiki = wiki.resolve()
    seite = seite.resolve()
    ziele: set[Path] = set()
    for ziel in LINK.findall(text):
        if ziel.startswith(("http://", "https://", "mailto:", "#")):
            continue
        ziel = ziel.split("#", 1)[0]
        if not ziel.endswith(".md"):
            continue
        pfad = (seite.parent / ziel).resolve()
        if pfad == seite or not pfad.is_file() or wiki not in pfad.parents:
            continue
        if ist_sonderseite(pfad, wiki):
            continue
        ziele.add(pfad)
    return ziele


def baue_graph(wiki: Path) -> tuple[dict[str, str], set[tuple[str, str]]]:
    """Liefert (titel je Seite, Kanten). Schlüssel: Pfad relativ zu wiki/."""
    wiki = wiki.resolve()
    seiten = [p for p in sorted(wiki.glob("**/*.md")) if not ist_sonderseite(p, wiki)]
    titel: dict[str, str] = {}
    kanten: set[tuple[str, str]] = set()
    for seite in seiten:
        text = seite.read_text(encoding="utf-8")
        name = seite.relative_to(wiki).as_posix()
        titel[name] = lies_titel(text, seite.stem)
        for ziel in finde_links(seite, text, wiki):
            kanten.add((name, ziel.relative_to(wiki).as_posix()))
    return titel, kanten


def verwaiste(titel: dict[str, str], kanten: set[tuple[str, str]]) -> set[str]:
    """Seiten, auf die keine andere Seite verlinkt."""
    verlinkt = {ziel for _, ziel in kanten}
    return {name for name in titel if name not in verlinkt}


def knoten_ids(namen: list[str]) -> dict[str, str]:
    """Eindeutige, Mermaid-taugliche IDs aus den Dateinamen."""
    ids: dict[str, str] = {}
    vergeben: set[str] = set()
    for name in sorted(namen):
        basis = "n_" + re.sub(r"[^A-Za-z0-9_]", "_", name.removesuffix(".md"))
        kandidat, i = basis, 2
        while kandidat in vergeben:
            kandidat, i = f"{basis}_{i}", i + 1
        vergeben.add(kandidat)
        ids[name] = kandidat
    return ids


def als_mermaid(titel: dict[str, str], kanten: set[tuple[str, str]], verwaist: set[str]) -> str:
    ids = knoten_ids(list(titel))
    zeilen = [
        "# Linkgraph des Wikis",
        "",
        "Automatisch erzeugt mit `python tools/wiki_graph.py` – nicht von Hand bearbeiten.",
        "Ein Knoten pro Wiki-Seite, ein Pfeil pro Link. `index.md` und `log.md` sind ausgeblendet.",
        "**Rot** markiert sind Seiten, auf die keine andere Seite verlinkt.",
        "",
        "```mermaid",
        "graph LR",
    ]
    for name in sorted(titel):
        label = titel[name].replace('"', "#quot;")
        zeilen.append(f'    {ids[name]}["{label}"]')
    for quelle, ziel in sorted(kanten):
        zeilen.append(f"    {ids[quelle]} --> {ids[ziel]}")
    zeilen.append("    classDef verwaist fill:#f88,stroke:#c00,color:#000")
    if verwaist:
        zeilen.append(f"    class {','.join(ids[n] for n in sorted(verwaist))} verwaist")
    zeilen += ["```", "", "## Seiten ohne eingehende Links", ""]
    if verwaist:
        zeilen += [f"- {titel[n]} (`wiki/{n}`)" for n in sorted(verwaist)]
    else:
        zeilen.append("Keine.")
    return "\n".join(zeilen) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--wiki", type=Path, default=ROOT / "wiki", help="Ordner mit den Wiki-Seiten")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "wiki-graph.md", help="Ausgabedatei")
    args = parser.parse_args(argv)

    if not args.wiki.is_dir():
        print(f"Wiki-Ordner nicht gefunden: {args.wiki}", file=sys.stderr)
        return 1
    titel, kanten = baue_graph(args.wiki)
    verwaist = verwaiste(titel, kanten)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(als_mermaid(titel, kanten, verwaist), encoding="utf-8")
    print(f"{args.out}: {len(titel)} Seiten, {len(kanten)} Links, {len(verwaist)} ohne eingehende Links")
    for name in sorted(verwaist):
        print(f"  verwaist: wiki/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
