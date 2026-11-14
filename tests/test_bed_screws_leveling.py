import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from test_capabilities import display, snapshot


class BedScrewsLevelingTests(unittest.TestCase):
    def test_bed_screws_entry_opens_guided_maintenance_prepare(self):
        plain = display(snapshot())
        self.assertNotIn('BEDSCREWS', [e[0] for e in plain._leveling_menu_entries()])
        data = snapshot()
        data['objects'].append('bed_screws')
        view = display(data)
        keys = lambda: [entry[0] for entry in view._leveling_menu_entries()]
        self.assertIn('BEDSCREWS', keys())

        row = SimpleNamespace(feature_id='P12', device=None)
        view.pd.maintenance_guided_plan = Mock(return_value=(row,))
        view.Enter_Maintenance_Menu = Mock()
        view._maintenance_open = Mock()
        view.get_encoder_state = Mock(return_value=view.ENCODER_DIFF_ENTER)
        view.checkkey = view.BedMeshMenu
        view._mesh_menu_selection = keys().index('BEDSCREWS')
        view.HMI_Bed_Mesh_Menu()
        view.Enter_Maintenance_Menu.assert_called_once_with()
        view._maintenance_open.assert_called_once_with('prepare', row)


if __name__ == '__main__':
    unittest.main()
