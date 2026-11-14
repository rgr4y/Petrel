import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from test_capabilities import display, snapshot
from petrel.features.maintenance.domains.probe import MaintenanceProbeController


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


class BedScrewsHeatTests(unittest.TestCase):
    def owner(self):
        owner = MaintenanceProbeController.__new__(MaintenanceProbeController)
        owner._row = SimpleNamespace(feature_id='P12', device=None)
        return owner

    def test_start_heats_bed_to_default_or_existing_target(self):
        owner = self.owner()
        cold = {'heater_bed': {'target': 0., 'temperature': 22.}}
        self.assertEqual(owner.script('start', cold), 'M190 S65\nBED_SCREWS_ADJUST')
        warm = {'heater_bed': {'target': 60., 'temperature': 60.}}
        self.assertEqual(owner.script('start', warm), 'M190 S60\nBED_SCREWS_ADJUST')

    def test_hot_extruder_ignored_and_cold_bed_refused_after_start(self):
        owner = self.owner()
        settings = {'extruder': {'heater_pin': 'PA0'}, 'heater_bed': {'heater_pin': 'PC9'}}
        hot = {'extruder': {'target': 200., 'temperature': 200., 'power': .5},
               'heater_bed': {'target': 65., 'temperature': 64., 'power': .3}}
        owner.check_heaters(settings, hot, 'start')
        owner.check_heaters(settings, hot, 'accept')
        cold_bed = dict(hot, heater_bed={'target': 0., 'temperature': 30., 'power': 0.})
        owner.check_heaters(settings, cold_bed, 'start')
        owner.check_heaters(settings, cold_bed, 'abort')
        with self.assertRaisesRegex(ValueError, 'bed_screws_requires_warm_bed'):
            owner.check_heaters(settings, cold_bed, 'adjusted')


if __name__ == '__main__':
    unittest.main()
