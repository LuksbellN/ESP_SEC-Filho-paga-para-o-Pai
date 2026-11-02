"""Casos pequenos para conferir o detector sem depender do arquivo de blocos."""
import copy
import unittest
from analyze import transaction_metrics, is_candidate, analyze_block


def tx(idx, refs=None, values=(1000,), fee=100, address=True):
    refs = refs or [(10000 + idx, 0, sum(values) + fee)]
    outputs = [dict(n=n, value=v, **({'addr': 'endereco-teste'} if address else {}))
               for n, v in enumerate(values)]
    return dict(tx_index=idx, hash=f'{idx:064x}', weight=800, fee=fee,
                inputs=[dict(prev_out=dict(tx_index=p, n=n, value=v))
                        for p, n, v in refs], out=outputs)


def block(txs):
    return dict(hash='bloco', height=1, time=1, n_tx=len(txs), tx=txs)


class EconomicTests(unittest.TestCase):
    def test_rules(self):
        self.assertTrue(is_candidate(100, 200, 1900, 200, 5))
        self.assertFalse(is_candidate(100, 200, 900, 200, 5))
        self.assertTrue(is_candidate(0, 200, 2000, 200, 5))
        self.assertFalse(is_candidate(100, 200, 100, 200, 5))
        self.assertFalse(is_candidate(0, 200, 2000, 200, 0))

    def test_weight_rounding_and_fee(self):
        t = tx(1); t['weight'] = 801
        self.assertEqual(transaction_metrics(t)['vsize'], 201)
        self.assertEqual(transaction_metrics(t)['fee_sat'], 100)

    def test_invalid_metrics(self):
        for change in ['negative', 'fee', 'weight']:
            t = tx(1)
            if change == 'negative': t['inputs'][0]['prev_out']['value'] = 1
            if change == 'fee': t['fee'] = 123
            if change == 'weight': t['weight'] = 0
            with self.assertRaises(ValueError): transaction_metrics(t)


class GraphTests(unittest.TestCase):
    def test_multiple_inputs_one_pair(self):
        p = tx(1, values=(1000, 2000))
        c = tx(2, [(1, 0, 1000), (1, 1, 2000)], values=(2900,))
        result = analyze_block(block([p, c]))
        self.assertEqual(len(result['pairs']), 1)
        self.assertEqual(result['pairs'][0]['consumed_sat'], 3000)
        self.assertEqual(result['block_row']['edges'], 1)

    def test_external_parent_and_empty(self):
        self.assertEqual(analyze_block(block([tx(1)]))['pairs'], [])
        self.assertEqual(analyze_block(block([]))['pairs'], [])

    def test_chain_and_branch_are_complex(self):
        p = tx(1, values=(1000, 2000))
        c = tx(2, [(1, 0, 1000)], values=(900,))
        for d in [tx(3, [(2, 0, 900)], values=(800,)),
                  tx(3, [(1, 1, 2000)], values=(1900,))]:
            r = analyze_block(block([p, c, d]))
            self.assertEqual(r['pairs'], [])
            self.assertEqual(r['block_row']['complex_components'], 1)
            self.assertEqual(r['block_row']['complex_transactions'], 3)

    def test_coinbase_excluded(self):
        coin = tx(0); coin['inputs'][0]['prev_out']['n'] = 4294967295
        r = analyze_block(block([coin, tx(1)]))['block_row']
        self.assertEqual(r['coinbase'], 1)
        self.assertEqual(r['normal_transactions'], 1)
        self.assertEqual(r['median_rate'], .5)

    def test_bad_internal_references(self):
        p = tx(1); c = tx(2, [(1, 0, 1000)], values=(900,))
        bad = copy.deepcopy(c); bad['inputs'][0]['prev_out']['n'] = 9
        with self.assertRaises(ValueError): analyze_block(block([p, bad]))
        bad = copy.deepcopy(c); bad['inputs'][0]['prev_out']['value'] = 1001
        bad['fee'] = 101
        with self.assertRaises(ValueError): analyze_block(block([p, bad]))
        with self.assertRaises(ValueError): analyze_block(block([p, p]))
        with self.assertRaises(ValueError): analyze_block(block([c, p]))

    def test_missing_address(self):
        p = tx(1, address=False)
        c = tx(2, [(1, 0, 1000)], values=(900,))
        pair = analyze_block(block([p, c]))['pairs'][0]
        self.assertEqual(pair['consumed_outputs'][0]['address'], None)


if __name__ == '__main__':
    unittest.main()
