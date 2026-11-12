import unittest
import app


class SeedControlLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = app.build_ui()
        cls.config = cls.ui.get_config_file()
        cls.components = {item['id']: item for item in cls.config['components']}
        cls.paths = {}
        cls.order = []

        def visit(node, ancestors):
            cls.paths[node['id']] = ancestors
            cls.order.append(node['id'])
            for child in node.get('children', []):
                visit(child, ancestors + [node['id']])

        visit(cls.config['layout'], [])
        cls.panel = next(key for key, item in cls.components.items()
                         if item['props'].get('elem_id') == 'generate-panel')

    def controls_with_class(self, name):
        return [key for key, item in self.components.items()
                if name in item['props'].get('elem_classes', [])
                and self.panel in self.paths.get(key, [])]

    def test_shared_seed_controls_stay_outside_settings_and_commentary_tabs(self):
        seeds = self.controls_with_class('shared-seed')
        randomizers = self.controls_with_class('seed-randomize')
        self.assertEqual(len(seeds), 1)
        self.assertEqual(len(randomizers), 1)
        for key in seeds + randomizers:
            ancestors = [self.components[item] for item in self.paths[key]
                         if item in self.components]
            self.assertFalse(any('generation-settings' in item['props'].get('elem_classes', [])
                                 for item in ancestors), 'Seed controls must remain visible when settings are closed.')
            self.assertFalse(any(item['props'].get('elem_id') == 'commentary-mode-tabs'
                                 for item in ancestors), 'Both Single and Multiple must use the same seed controls.')

    def test_seed_row_is_immediately_before_shared_generate(self):
        row, = self.controls_with_class('shared-seed-row')
        button = next(key for key, item in self.components.items()
                      if item['props'].get('elem_id') == 'generate-commentary')
        self.assertEqual(self.paths[row], self.paths[button])
        siblings = [key for key in self.order if self.paths[key] == self.paths[button]]
        self.assertEqual(siblings[siblings.index(button) - 1], row)
        tabs = next(key for key, item in self.components.items()
                    if item['props'].get('elem_id') == 'commentary-mode-tabs')
        self.assertLess(self.order.index(tabs), self.order.index(row))

    def test_seed_controls_have_no_persistent_info_or_dedicated_help_icon(self):
        for key in self.controls_with_class('shared-seed') + self.controls_with_class('seed-randomize'):
            self.assertFalse(self.components[key]['props'].get('info'))
        self.assertFalse(self.controls_with_class('seed-help'))

    def test_generation_still_uses_the_visible_shared_seed(self):
        seed, = self.controls_with_class('shared-seed')
        full = next(fn for fn in self.ui.fns.values() if fn.fn is app.generate_workflow_ui)
        self.assertEqual(full.inputs[12]._id, seed)
        self.assertEqual(self.components[seed]['props']['value'], 42)
        self.assertEqual(self.components[self.controls_with_class('seed-randomize')[0]]['props']['value'], False)


if __name__ == '__main__':
    unittest.main()
