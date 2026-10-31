"""Offline checks for important generation/curation invariants."""
import unittest
from src.presentation import quantify_recipe
from src.fitness import novelty_score
from src.llm_method import judge_messages, validate_judgments
from src.main import select_collections


class PipelineTests(unittest.TestCase):
    def test_quantities_are_stable_and_sum_to_known_mass(self):
        db = {n: {'relative_quantities': [0.1, 0.3], 'known_mass_fractions': []}
              for n in ['flour', 'milk', 'sugar']}
        db['mint'] = {'relative_quantities': [], 'known_mass_fractions': []}
        names = list(db)
        first = quantify_recipe(names, db, seed=42)
        self.assertEqual(first, quantify_recipe(names, db, seed=42))
        self.assertAlmostEqual(sum(i['amount'] for i in first if i['unit'] == 'g'), 500)
        self.assertEqual(first[-1]['amount'], 'q.b.')

    def test_novelty_is_nearest_source_distance(self):
        sources = [{'ingredients': ['a', 'b']}, {'ingredients': ['c', 'd']}]
        self.assertEqual(novelty_score(['a', 'b'], sources), 0)
        self.assertEqual(novelty_score(['x', 'y'], sources), 1)
        self.assertAlmostEqual(novelty_score(['a', 'x'], sources), 2 / 3)

    def test_judge_does_not_receive_explicit_fitness_or_profile(self):
        row = {'id': 'C01', 'fitness': 0.9, 'profile': 'conservative',
               'ingredients': [{'name': 'milk', 'amount': 500, 'unit': 'g'}]}
        text = judge_messages([row])[1]['content']
        self.assertNotIn('fitness', text)
        self.assertNotIn('conservative', text)
        self.assertIn('C01', text)

    def test_reject_nonfinite_judgment(self):
        data = {'judgments': [{'id': 'C01', 'potential': float('nan'),
                              'creativity': 5, 'reason': 'test'}]}
        with self.assertRaises(ValueError):
            validate_judgments(data, ['C01'])

    def test_selection_is_disjoint_and_respects_floor(self):
        candidates = [{'id': str(i), 'ingredient_names': [f'ingredient-{i}'],
                       'fitness_breakdown': {'novelty': i / 10}} for i in range(6)]
        judgments = {str(i): {'potential': 4 if i == 0 else 8,
                             'creativity': i} for i in range(6)}
        books = select_collections(candidates, judgments, count=2)
        self.assertEqual(len(books['promising']), 2)
        self.assertEqual(len(books['creative']), 2)
        self.assertFalse(set(books['promising']) & set(books['creative']))
        self.assertNotIn('0', books['promising'] + books['creative'])


if __name__ == '__main__':
    unittest.main()
