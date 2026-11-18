import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from biblical_books import cli
from biblical_books.marc import MARC, parse_record

XML = '''<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader><controlfield tag="001">42</controlfield><controlfield tag="008">000000s2020    xx            000 0 eng  </controlfield><datafield tag="245" ind1="0" ind2="0"><subfield code="a">Biblical worlds :</subfield><subfield code="b">essays /</subfield></datafield><datafield tag="700" ind1="1" ind2=" "><subfield code="a">Doe, Jane</subfield><subfield code="4">edt</subfield></datafield><datafield tag="650" ind1=" " ind2="0"><subfield code="a">Bible</subfield><subfield code="x">Criticism</subfield></datafield><datafield tag="020" ind1=" " ind2=" "><subfield code="a">123</subfield><subfield code="a">456</subfield></datafield></record>'''

# K10plus returns this in place of one unretrievable record, with HTTP 200 and a full page.
SRU_BAD_RECORD = '<diagnostic xmlns="http://www.loc.gov/zing/srw/diagnostic/"><uri>info:srw/diagnostic/1/63</uri><message>System error in retrieving records</message></diagnostic>'
SRU_PAGE = '''<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><version>1.1</version><numberOfRecords>{total}</numberOfRecords><records><record><recordSchema>marcxml</recordSchema><recordPacking>xml</recordPacking><recordData>{first}</recordData><recordPosition>1</recordPosition></record><record><recordSchema>marcxml</recordSchema><recordPacking>xml</recordPacking><recordData>{second}</recordData><recordPosition>{position}</recordPosition></record></records></searchRetrieveResponse>'''


class PipelineTests(unittest.TestCase):
    def test_marc_repeated_metadata_roles_and_format(self):
        row = parse_record(ET.fromstring(XML))
        self.assertEqual(row['full_title'], 'Biblical worlds: essays')
        self.assertEqual(row['editors'], ['Doe, Jane'])
        self.assertEqual(row['isbns'], ['123', '456'])
        self.assertEqual(row['subjects'], ['Bible Criticism'])
        self.assertTrue(row['is_textual_monograph'])
        saved = json.loads(row['marc_json'])
        self.assertEqual(saved['fields'][-1]['subfields'][1]['value'], '456')
        article = ET.fromstring(XML)
        article.find(MARC+'leader').text = '00000naa a2200000 a 4500'
        self.assertFalse(parse_record(article)['is_textual_monograph'])

    def test_diagnostic_and_unexpected_html_are_not_empty_successes(self):
        class Response:
            def raise_for_status(self): pass
        class Client:
            def __init__(self, content): self.content=content
            def get(self, *a, **k):
                r=Response(); r.content=self.content; return r
        for content in [b'<html/>', b'<r><diagnostic><message>bad query</message></diagnostic></r>']:
            with self.assertRaises(RuntimeError):
                cli.request_page(Client(content), 'https://example.test', 'x', 1, 10)

    def test_record_level_diagnostic_is_reported_not_raised(self):
        class Response:
            def raise_for_status(self): pass
        class Client:
            def __init__(self, content): self.content=content
            def get(self, *a, **k):
                r=Response(); r.content=self.content; return r
        page = SRU_PAGE.format(total=2, first=XML, second=SRU_BAD_RECORD, position=2)
        content, total, records, failures = cli.request_page(Client(page.encode()), 'https://example.test', 'x', 1, 2)
        self.assertEqual(total, 2)
        self.assertEqual(len(records), 1)
        self.assertEqual(failures[0]['position'], 2)
        self.assertIn('System error in retrieving records', failures[0]['diagnostic'])
        # A page that is mostly unretrievable is a systemic fault, not one bad record.
        bulk = SRU_PAGE.format(total=2, first=SRU_BAD_RECORD, second=SRU_BAD_RECORD, position=2)
        with self.assertRaises(RuntimeError):
            cli.request_page(Client(bulk.encode()), 'https://example.test', 'x', 1, 2)

    def test_resume_union_provenance_and_parquet(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root/'queries.json'
            config.write_text(json.dumps({'endpoint':'https://example.test', 'queries':[{'id':'a','cql':'a'},{'id':'b','cql':'b'}]}))
            args = argparse.Namespace(config=config, data_dir=root/'data', query=None, delay=0, page_size=1, max_pages=None, batch_size=1)
            row = parse_record(ET.fromstring(XML))
            def page(client, endpoint, cql, start, size):
                if cql=='a':
                    item=dict(row, record_id=str(40+start))
                    return XML.encode(), 2, [item], []
                return XML.encode(), 1, [dict(row,record_id='41')], []
            with patch.object(cli,'request_page',side_effect=page) as fetch, patch.object(cli.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
                cli.harvest(args)
                self.assertEqual(fetch.call_count,3)
                cli.harvest(args)
                self.assertEqual(fetch.call_count,3)
                cli.export(args)
            frame=pd.read_parquet(args.data_dir/'records.parquet')
            self.assertEqual(len(frame),2)
            self.assertEqual(set(frame.loc[frame.record_id=='41','matched_queries'].iloc[0]), {'a','b'})
            self.assertEqual(len(pd.read_parquet(args.data_dir/'books.parquet')),2)
            self.assertTrue(json.loads((args.data_dir/'status.json').read_text())['selection_complete'])
            config.write_text(json.dumps({'endpoint':'https://other.test','queries':[{'id':'a','cql':'a'}]}))
            with self.assertRaises(ValueError): cli.harvest(args)

    def test_interruption_does_not_mark_query_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            config=root/'queries.json'
            config.write_text(json.dumps({'endpoint':'https://example.test','queries':[{'id':'a','cql':'a'},{'id':'b','cql':'b'}]}))
            args=argparse.Namespace(config=config,data_dir=root/'data',query=['a'],delay=0,page_size=1,max_pages=1)
            row=parse_record(ET.fromstring(XML))
            with patch.object(cli,'request_page',return_value=(XML.encode(),10,[row],[])), patch.object(cli.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
                cli.harvest(args)
            report=json.loads((args.data_dir/'status.json').read_text())
            self.assertFalse(report['selection_complete'])
            self.assertFalse(report['queries'][0]['complete'])

    def test_unretrievable_position_is_recorded_not_silently_dropped(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            config=root/'queries.json'
            config.write_text(json.dumps({'endpoint':'https://example.test','queries':[{'id':'a','cql':'a'}]}))
            args=argparse.Namespace(config=config,data_dir=root/'data',query=None,delay=0,page_size=3,max_pages=None,batch_size=10)
            row=parse_record(ET.fromstring(XML))
            rows=[dict(row, record_id='42'), dict(row, record_id='43')]
            failure={'position':2,'diagnostic':'System error in retrieving records'}
            # A full page: two retrievable records and one unretrievable position.
            with patch.object(cli,'request_page',return_value=(XML.encode(),3,rows,[failure])), patch.object(cli.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
                cli.harvest(args)
            report=json.loads((args.data_dir/'status.json').read_text())
            self.assertEqual(report['skipped_positions'],1)
            self.assertEqual(report['unretrievable_records'][0]['position'],2)
            self.assertEqual(report['queries'][0]['skipped_positions'],1)
            self.assertTrue(report['queries'][0]['complete'])
            with sqlite3.connect(args.data_dir/'harvest.sqlite') as db:
                self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT query_id,position FROM failures').fetchone(),('a',2))
                # the cursor advanced past the whole page exactly once
                self.assertEqual(db.execute('SELECT start,count,skipped FROM pages').fetchall(),[(1,3,1)])



if __name__=='__main__': unittest.main()
