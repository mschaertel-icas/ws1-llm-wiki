"""Tests für tools/wiki_graph.py.  Aufruf: python -m unittest discover -s tests"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import wiki_graph  # noqa: E402

SEITEN = {
    "a.md": """---
titel: Seite A
typ: thema
---

# Seite A

Siehe [B](b.md) und [Abschnitt in B](b.md#abschnitt).
Extern: [Hochschule](https://www.hs-coburg.de), [Mail](mailto:x@example.org),
[Anker](#oben), [kaputt](gibt-es-nicht.md).
""",
    "b.md": """---
titel: Dokument: Seite "B"
typ: dokument
---

# Seite B

Zurück zu [A](a.md), und [mich selbst](b.md).
""",
    "c.md": """# Seite C ohne Kopf

Verweist auf [A](./a.md), aber niemand verweist auf C.
""",
    "index.md": "# Index\n\n- [A](a.md)\n- [B](b.md)\n- [C](c.md)\n",
    "log.md": "# Protokoll\n\n[C](c.md)\n",
}


class WikiGraphTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.wiki = self.root / "wiki"
        self.wiki.mkdir()
        for name, text in SEITEN.items():
            (self.wiki / name).write_text(text, encoding="utf-8")

    def test_titel_aus_kopf_und_ueberschrift(self):
        titel, _ = wiki_graph.baue_graph(self.wiki)
        self.assertEqual(titel["a.md"], "Seite A")
        self.assertEqual(titel["c.md"], "Seite C ohne Kopf")
        self.assertEqual(titel["b.md"], 'Dokument: Seite "B"')

    def test_titel_in_anfuehrungszeichen(self):
        text = '---\ntitel: "Dokument: X"\n---\n'
        self.assertEqual(wiki_graph.lies_titel(text, "datei"), "Dokument: X")

    def test_titel_fallback_dateiname(self):
        self.assertEqual(wiki_graph.lies_titel("nur Text", "datei"), "datei")

    def test_sonderseiten_ausgeblendet(self):
        titel, kanten = wiki_graph.baue_graph(self.wiki)
        self.assertEqual(set(titel), {"a.md", "b.md", "c.md"})
        self.assertFalse(any("index.md" in k or "log.md" in k for kante in kanten for k in kante))

    def test_kanten(self):
        _, kanten = wiki_graph.baue_graph(self.wiki)
        # Anker zusammengefasst; extern, mailto, Anker, kaputter Link und Selbstlink ignoriert
        self.assertEqual(kanten, {("a.md", "b.md"), ("b.md", "a.md"), ("c.md", "a.md")})

    def test_verwaiste(self):
        titel, kanten = wiki_graph.baue_graph(self.wiki)
        self.assertEqual(wiki_graph.verwaiste(titel, kanten), {"c.md"})

    def test_mermaid(self):
        titel, kanten = wiki_graph.baue_graph(self.wiki)
        text = wiki_graph.als_mermaid(titel, kanten, wiki_graph.verwaiste(titel, kanten))
        self.assertIn("```mermaid\ngraph LR\n", text)
        self.assertIn('n_a["Seite A"]', text)
        self.assertIn('n_b["Dokument: Seite #quot;B#quot;"]', text)
        self.assertIn("n_a --> n_b", text)
        self.assertIn("n_b --> n_a", text)
        self.assertIn("n_c --> n_a", text)
        self.assertEqual(text.count(" --> "), 3)
        self.assertIn("class n_c verwaist", text)
        self.assertIn("classDef verwaist", text)

    def test_knoten_ids_eindeutig(self):
        ids = wiki_graph.knoten_ids(["a-b.md", "a_b.md"])
        self.assertEqual(len(set(ids.values())), 2)

    def test_main_schreibt_datei(self):
        out = self.root / "docs" / "wiki-graph.md"
        rc = wiki_graph.main(["--wiki", str(self.wiki), "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertTrue(out.is_file())
        self.assertIn("graph LR", out.read_text(encoding="utf-8"))

    def test_main_ohne_wiki(self):
        rc = wiki_graph.main(["--wiki", str(self.root / "fehlt"), "--out", str(self.root / "x.md")])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
