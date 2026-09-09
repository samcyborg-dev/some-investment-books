"""Checks for the dossier's educational calculations and finished PDF.

These tests do not validate the legacy trading engine or establish an empirical edge.
Run: python3 -m unittest discover -s research/strategy_1 -p 'test_research.py' -v
"""
from pathlib import Path
from itertools import product
from zoneinfo import ZoneInfo
from datetime import datetime
import hashlib
import importlib.util
import json
import re
import sys
import unittest

import numpy as np
import pymupdf

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('orb_examples',HERE/'calculate_examples.py')
examples=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=examples
spec.loader.exec_module(examples)


class ArithmeticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results=json.loads((HERE/'illustrative_results.json').read_text())

    def test_break_even_geometry(self):
        self.assertAlmostEqual(self.results['breakeven_p_no_cost'],.375)
        self.assertAlmostEqual(self.results['breakeven_p_cost_010'],.4125)
        p=.4125
        self.assertAlmostEqual(p*(5/3)-(1-p)-.10,0)

    def test_paper_arithmetic_discrepancy(self):
        x=self.results['paper2_consistency']
        self.assertEqual(x['wealth_implied_by_return'],2362500)
        self.assertEqual(x['return_implied_by_wealth_pct'],25500)
        self.assertNotEqual(x['wealth_implied_by_return'],x['claimed_wealth'])

    def test_all_path_outcomes_accounted_for(self):
        self.assertEqual(len(self.results['grid']),12)
        self.assertEqual(len(self.results['stress']),7)
        for r in self.results['grid']+self.results['stress']:
            self.assertEqual(r['passed']+r['breached']+r['unresolved'],20000)
            self.assertAlmostEqual(r['pass_pct']+r['breach_pct']+r['unresolved_pct'],100)
            self.assertLessEqual(r['pass_ci_low_pct'],r['pass_pct'])
            self.assertGreaterEqual(r['pass_ci_high_pct'],r['pass_pct'])
            self.assertEqual(r['daily_intrabar_compliance'],'NOT ESTIMATED')

    def test_saved_base_is_reproducible(self):
        rng=np.random.default_rng(examples.SEED)
        n=examples.N;h=examples.HORIZON
        draws=(rng.random((h,n)),rng.random((h,n)),rng.random(n),rng.random((h,n)))
        got=examples.simulate(examples.Scenario('Base: independent'),draws)
        self.assertEqual(got,self.results['stress'][0])
        self.assertEqual(got['passed'],2073)

    def test_dependency_preserves_stationary_probability(self):
        q=.55;q_ll=.75;q_lw=q*(1-q_ll)/(1-q)
        self.assertAlmostEqual(q*q_ll+(1-q)*q_lw,q)

    def test_run_recursion_matches_brute_force(self):
        q=.55;n=8;k=3
        exact=0
        for seq in product([0,1],repeat=n):
            if '1'*k in ''.join(map(str,seq)):
                exact+=(q**sum(seq))*((1-q)**(n-sum(seq)))
        self.assertAlmostEqual(examples.probability_run(n,q,k),exact)
        self.assertAlmostEqual(examples.probability_run(100,.55,10),.10086908739214817)

    def test_constructed_drawdowns_and_recovery(self):
        eq=np.array(self.results['toy_equity']);dd=1-eq/np.maximum.accumulate(eq)
        self.assertAlmostEqual(float(dd.max())*100,8.490566037735846)
        self.assertEqual(eq[2],eq[9]);self.assertEqual(eq[10],eq[14])
        self.assertLess(eq[-1],eq[15]) # final episode is right-censored

    def test_floor_contract_sizing_examples(self):
        self.assertEqual(int(500//330),1)
        self.assertEqual(int(500//34.5),14)
        self.assertEqual(int(20//34.5),0)

    def test_nairobi_time(self):
        ny=ZoneInfo('America/New_York');nai=ZoneInfo('Africa/Nairobi')
        self.assertEqual(datetime(2026,9,8,9,30,tzinfo=ny).astimezone(nai).strftime('%H:%M'),'16:30')
        self.assertEqual(datetime(2026,12,8,9,30,tzinfo=ny).astimezone(nai).strftime('%H:%M'),'17:30')
        self.assertEqual(datetime(2026,12,8,16,tzinfo=ny).astimezone(nai).day,9)


class DocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf=pymupdf.open(ROOT/'STRATEGY_1_ORB_FORENSIC_RESEARCH.pdf')
        cls.md=(HERE/'report.md').read_text()
        cls.sources=json.loads((HERE/'sources.json').read_text())['sources']
        cls.meta=json.loads((HERE/'build_metadata.json').read_text())

    @classmethod
    def tearDownClass(cls):cls.pdf.close()

    def test_substantive_page_count(self):
        self.assertEqual(len(self.pdf),49)
        self.assertEqual(len(re.findall(r'<!-- PAGE ',self.md)),len(self.pdf))
        self.assertGreaterEqual(len(self.pdf),31)
        self.assertGreater(sum(len(p.get_text().split()) for p in self.pdf),14000)
        for p in self.pdf:
            self.assertGreater(len(p.get_text().split()),60)

    def test_bibliography_and_links(self):
        self.assertEqual(len(self.sources),15)
        self.assertEqual(sum('ssrn' in s for s in self.sources),11)
        urls={link['uri'] for p in self.pdf for link in p.get_links() if 'uri' in link}
        for s in self.sources:self.assertIn(s['url'],urls)
        self.assertEqual(len(self.pdf.get_toc()),49)
        self.assertGreater(sum(len(p.get_links()) for p in self.pdf),120)

    def test_no_unrendered_markup_or_corruption(self):
        text='\n'.join(p.get_text() for p in self.pdf)
        for fragment in ['LINKTOKEN','{{TOC}}',':::formula','<!-- PAGE','\ufffd','rounfidence','The ro for this dossier']:
            self.assertNotIn(fragment,text)
        self.assertEqual(self.md.count('## Reproduction steps'),1)
        self.assertIn('2,073 of 20,000',text)

    def test_measured_layout(self):
        for row in self.meta['layout']:
            self.assertLessEqual(row['used_points'],row['available_points'])
            self.assertGreaterEqual(row['body_font_pt'],9.2)
        for page in self.pdf:
            for block in page.get_text('dict')['blocks']:
                if block['type']!=0:continue
                for line in block['lines']:
                    for span in line['spans']:
                        x0,y0,x1,y1=span['bbox']
                        self.assertGreaterEqual(x0,12)
                        self.assertGreaterEqual(y0,10)
                        self.assertLessEqual(x1,page.rect.width-12)
                        self.assertLessEqual(y1,page.rect.height-10)

    def test_original_figures_present_and_embedded(self):
        from PIL import Image
        paths=re.findall(r'!\[[^\]]+\]\((figures/[^)]+)\)',self.md)
        self.assertEqual(len(paths),8)
        for path in paths:
            with Image.open(HERE/path) as image:
                self.assertGreater(image.width,800)
                self.assertGreater(image.height,300)
        self.assertEqual(sum(len(p.get_images()) for p in self.pdf),8)

    def test_internal_navigation_targets_exist(self):
        for page in self.pdf:
            for link in page.get_links():
                if link['kind']==pymupdf.LINK_GOTO:
                    self.assertGreaterEqual(link['page'],0)
                    self.assertLess(link['page'],len(self.pdf))

    def test_build_hashes_match_delivered_files(self):
        for path,h in self.meta['sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),h)

    def test_engine_not_modified_since_audit(self):
        hashes=json.loads((HERE/'audited_code_hashes.json').read_text())['files']
        for path,h in hashes.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),h)

    def test_limited_scope_disclosures(self):
        text='\n'.join(p.get_text() for p in self.pdf)
        for phrase in ['not independently replicated','first 30 PDF pages','right-censored',
                       'not a new ORB backtest','unknown','No Pine Script']:
            self.assertIn(phrase,text)
        journal=(ROOT/'TRADING_JOURNAL.md').read_text()
        self.assertIn('NOT LIVE-VALIDATED',journal[:500])

if __name__=='__main__':unittest.main()
