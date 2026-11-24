"""Offline tests for the machine-readable derivation (`biblical_books.derive`)."""
import json
import unittest

from biblical_books import cli, derive

MARC = {
    "leader": "     cam a22      c 4500",
    "fields": [
        {"tag": "001", "value": "42"},
        {"tag": "245", "ind1": "1", "ind2": "0", "subfields": [
            {"code": "a", "value": "Biblische Theologie"},
            {"code": "c", "value": "hrsg. von Walter Strolz"},
        ]},
        # primary author, inverted, with dates and a GND id
        {"tag": "100", "ind1": "1", "ind2": " ", "subfields": [
            {"code": "a", "value": "Strolz, Walter"},
            {"code": "d", "value": "1927-2022"},
            {"code": "0", "value": "(DE-588)118619101"},
            {"code": "4", "value": "aut"},
        ]},
        # editor with a role text but no relator code
        {"tag": "700", "ind1": "1", "ind2": " ", "subfields": [
            {"code": "a", "value": "Doe, Jane"},
            {"code": "e", "value": "Herausgeber"},
        ]},
        # corporate body: no personal-name structure
        {"tag": "710", "ind1": "2", "ind2": " ", "subfields": [
            {"code": "a", "value": "Deutsche Bibelgesellschaft"},
            {"code": "0", "value": "(DE-588)2068675-8"},
            {"code": "4", "value": "pbl"},
        ]},
        # translator, open-ended dates
        {"tag": "700", "ind1": "1", "ind2": " ", "subfields": [
            {"code": "a", "value": "Luther, Martin"},
            {"code": "d", "value": "1483-1546"},
            {"code": "4", "value": "trl"},
        ]},
        # subject with a GND id and a scheme
        {"tag": "650", "ind1": " ", "ind2": "0", "subfields": [
            {"code": "a", "value": "Bibel"},
            {"code": "x", "value": "Theologie"},
            {"code": "0", "value": "(DE-588)4006406-2"},
            {"code": "2", "value": "gnd"},
        ]},
        # the GND chain that the flat export ignored
        {"tag": "689", "ind1": "0", "ind2": "0", "subfields": [
            {"code": "D", "value": "u"},
            {"code": "0", "value": "(DE-588)4006406-2"},
            {"code": "a", "value": "Bibel"},
            {"code": "2", "value": "gnd"},
        ]},
    ],
}


class DeriveTests(unittest.TestCase):
    def setUp(self):
        self.row = derive.derive(json.dumps(MARC))

    def test_contributor_roles_and_primary_flag(self):
        rows = self.row["contributor_records"]
        self.assertEqual([r["contributor_type"] for r in rows], ["aut", "None" if False else None, "pbl", "trl"])
        self.assertTrue(rows[0]["is_primary"])
        self.assertFalse(rows[1]["is_primary"])
        # an editor identified only by its relator text is still an editor
        self.assertIn("Doe, Jane", self.row["editors"])
        self.assertEqual(set(self.row["contributor_types"]), {"aut", "pbl", "trl"})

    def test_name_order_follows_indicator(self):
        author, _, corporate, _ = self.row["contributor_records"]
        self.assertTrue(author["name_inverted"])
        self.assertEqual((author["surname"], author["forenames"]), ("Strolz", "Walter"))
        self.assertTrue(corporate["is_corporate"])
        self.assertIsNone(corporate["surname"])

    def test_compat_lists_are_subsets_of_contributors(self):
        self.assertEqual(self.row["authors"], ["Strolz, Walter"])
        self.assertTrue(set(self.row["authors"]) | set(self.row["editors"]) <= set(self.row["contributors"]))
        self.assertEqual(len(self.row["contributors"]), 4)

    def test_gnd_ids_cover_names_subjects_and_chain(self):
        rows = self.row["contributor_records"]
        self.assertEqual(rows[0]["gnd_id"], "118619101")
        self.assertEqual(rows[0]["gnd_uri"], "https://d-nb.info/gnd/118619101")
        self.assertIn("118619101", self.row["name_authority_ids"])
        self.assertIn("2068675-8", self.row["name_authority_ids"])
        # 689 has the same id as 650; duplicates collapse but the chain is no longer dropped
        self.assertEqual(self.row["subject_authority_ids"], ["4006406-2"])
        self.assertEqual(set(self.row["authority_ids"]),
                         {"118619101", "2068675-8", "4006406-2"})

    def test_subject_structure_splits_heading_from_subdivisions(self):
        subject = next(s for s in self.row["subjects_structured"] if s["marc_tag"] == "650")
        self.assertEqual(subject["heading"], "Bibel")
        self.assertEqual(subject["subdivisions"], ["Theologie"])
        self.assertEqual(subject["scheme"], "gnd")
        self.assertEqual(subject["gnd_id"], "4006406-2")
        self.assertTrue(any(s["marc_tag"] == "689" for s in self.row["subjects_structured"]))

    def test_date_ranges_are_parsed(self):
        author = self.row["contributor_records"][0]
        self.assertEqual((author["date_earliest"], author["date_latest"]), (1927, 2022))
        self.assertEqual(author["date_precision"], "range")
        self.assertEqual(author["date_source"], "marc_$d")

    def test_date_parser_handles_the_measured_shapes(self):
        cases = {
            "1878-1937": (1878, 1937, "range"),
            "1961-": (1961, None, "open_end"),
            "-405": (None, 405, "open_start"),
            "260-339": (260, 339, "range"),
            "1483-1546": (1483, 1546, "range"),
            "1994": (1994, 1994, "year"),
            "fl. 1803": (1803, 1803, "floruit"),
            "d. 1755": (None, 1755, "death_only"),
            "1697 or 8-1760": (1697, 1760, "range"),
            "v766-v686": (686, 766, "range"),
            "ca. 1800-1850": (1800, 1850, "range"),
            "15XX-1627": (None, 1627, "range_from_unknown"),
            "10th cent": (None, None, "century"),
            "": (None, None, None),
        }
        for text, (earliest, latest, precision) in cases.items():
            with self.subTest(text=text):
                parsed = derive.parse_date_text(text)
                self.assertEqual((parsed["date_earliest"], parsed["date_latest"]), (earliest, latest))
                self.assertEqual(parsed["date_precision"], precision)

    def test_unparsed_dates_are_flagged_not_guessed(self):
        self.assertIn("reversed", derive.parse_date_text("v766-v686")["date_flags"])
        self.assertIn("approximate", derive.parse_date_text("ca. 1800-1850")["date_flags"])
        self.assertIn("century=10", derive.parse_date_text("10th cent")["date_flags"])
        self.assertEqual(derive.parse_date_text("19th cent")["date_earliest"], None)

    def test_authority_helpers(self):
        self.assertEqual(derive.gnd_of("(DE-588)118575449"), "118575449")
        self.assertEqual(derive.gnd_of("(DE-625)rvk/123050:"), None)
        self.assertEqual(derive.scheme_of("(DE-625)rvk/123050:"), "DE-625")
        self.assertIsNone(derive.gnd_of(""))

    def test_schema_names_are_unique_and_keep_compat_columns(self):
        schema = derive.books_schema()
        self.assertEqual(len(schema.names), len(set(schema.names)))
        for name in ("authors", "editors", "contributors", "contributor_records",
                     "subjects_structured", "authority_ids", "subject_authority_ids"):
            self.assertIn(name, schema.names)
        self.assertNotIn("marc_json", schema.names)
        self.assertIn("marc_json", derive.books_schema(keep_marc_json=True).names)
        # the structured column must not collide with the flat contributor list
        self.assertNotEqual(schema.field("contributors").type, schema.field("contributor_records").type)

    def test_headingless_689_shells_are_dropped(self):
        marc = {"leader": "x", "fields": [
            {"tag": "689", "ind1": "0", "ind2": "0", "subfields": [
                {"code": "D", "value": "u"}, {"code": "0", "value": "(DE-588)4006406-2"},
                {"code": "a", "value": "Bibel"}, {"code": "2", "value": "gnd"}]},
            {"tag": "689", "ind1": "0", "ind2": " ", "subfields": [{"code": "5", "value": "(DE-627)"}]},
        ]}
        row = derive.derive(json.dumps(marc))
        # the empty shell carries no heading and must not become a subject
        self.assertEqual(len(row["subjects_structured"]), 1)
        self.assertEqual(row["subjects_structured"][0]["heading"], "Bibel")

    def test_entity_type_comes_from_the_chain_marker(self):
        rows = self.row["subjects_structured"]
        chain = next(r for r in rows if r["marc_tag"] == "689")
        self.assertEqual(chain["entity_type"], "u")
        self.assertIsNone(next(r for r in rows if r["marc_tag"] == "650")["entity_type"])

    def test_concept_id_falls_back_to_the_normalised_heading(self):
        rows = self.row["subjects_structured"]
        bible = next(r for r in rows if r["gnd_id"] == "4006406-2")
        self.assertEqual(bible["concept_id"], "gnd:4006406-2")
        self.assertEqual(bible["concept_label"], "Bibel")
        self.assertEqual(derive.normalize_heading("Bible  O.T.,  "), "bible o t")

    def test_concept_map_merges_german_and_english_labels(self):
        """The map is learned from records that carry both vocabularies."""
        concept_map = derive.ConceptMap()
        # witnesses: one GND subject and one identifier-less English heading in the same record
        for i in range(derive.ConceptMap.MIN_SUPPORT + 2):
            concept_map.observe(f"rec{i}", [
                {"heading": "Bibel", "gnd_id": "4006406-2", "marc_tag": "689",
                 "concept_id": "gnd:4006406-2"},
                {"heading": "Bible", "gnd_id": None, "marc_tag": "650",
                 "concept_id": "heading:bible"},
            ])
        # a single co-occurrence must NOT be treated as an equivalence
        concept_map.observe("recOther", [
            {"heading": "Bibel", "gnd_id": "4006406-2", "marc_tag": "689",
             "concept_id": "gnd:4006406-2"},
            {"heading": "Hermeneutik", "gnd_id": None, "marc_tag": "650",
             "concept_id": "heading:hermeneutik"},
        ])
        concept_map.build()

        rows = concept_map.apply([
            {"heading": "Bible", "gnd_id": None, "marc_tag": "650", "concept_id": "heading:bible"},
            {"heading": "Hermeneutik", "gnd_id": None, "marc_tag": "650",
             "concept_id": "heading:hermeneutik"},
        ])
        self.assertEqual(rows[0]["concept_id"], "gnd:4006406-2")
        self.assertEqual(rows[0]["concept_label"], "Bibel / Bible")
        # not enough support: stays its own concept
        self.assertEqual(rows[1]["concept_id"], "heading:hermeneutik")
        self.assertEqual(concept_map.summary()["learned_aliases"], 1)

    def test_concept_map_rejects_a_concept_without_identifiers(self):
        concept_map = derive.ConceptMap()
        concept_map.observe("rec1", [{"heading": "Bible", "gnd_id": None, "marc_tag": "650",
                                      "concept_id": "heading:bible"}])
        concept_map.build()
        self.assertEqual(concept_map.summary()["learned_aliases"], 0)
        self.assertEqual(concept_map.summary()["heading_concepts"], 1)

    def test_schema_is_a_superset_of_the_exported_book_columns(self):
        # `export` writes date_type/first_seen/last_seen outside STRING_COLUMNS; a missing one here
        # would silently break notebook cells that read them.
        schema = derive.books_schema()
        expected = set(derive.STRING_COLUMNS) - {"marc_json"} | set(derive.LIST_COLUMNS)
        expected |= {"date_type", "first_seen", "last_seen", "publication_year",
                     "is_textual_monograph", "matched_queries"}
        self.assertEqual(sorted(extra for extra in expected if extra not in schema.names), [])


if __name__ == "__main__":
    unittest.main()
