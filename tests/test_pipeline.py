import unittest
import pipeline


class PipelineTests(unittest.TestCase):
    def row(self):
        return dict(lot_id='L01', wafer_id='W01', device_id='D01', temperature_c=25,
                    voltage_v=3.3, current_ma=60, leakage_ua=10, gain_db=18,
                    test_timestamp='2026-01-01T09:00:00')

    def test_spec_boundaries_and_multiple_failures(self):
        row = self.row()
        self.assertEqual(pipeline.classify(row), ('PASS', 'NORMAL'))
        row.update(current_ma=60.01, leakage_ua=10.01, gain_db=17.99)
        self.assertEqual(pipeline.classify(row), ('FAIL', 'HIGH_LEAKAGE|OVER_CURRENT|LOW_GAIN'))

    def test_valid_failure_is_not_cleaned_away(self):
        row = self.row()
        row['leakage_ua'] = 1000
        good, bad = pipeline.validate([row])
        self.assertEqual(len(bad), 0)
        self.assertEqual(good[0]['test_result'], 'FAIL')

    def test_corrupt_and_duplicate_records(self):
        a, b = self.row(), self.row()
        b.update(device_id='D02', current_ma='not_a_number')
        good, bad = pipeline.validate([a, dict(a), b])
        self.assertEqual(len(good), 1)
        self.assertEqual(len(bad), 2)
        self.assertIn('duplicate', bad[0]['rejection_reason'])

    def test_nonfinite_measurement(self):
        row = self.row()
        row['gain_db'] = 'NaN'
        good, bad = pipeline.validate([row])
        self.assertFalse(good)
        self.assertIn('invalid_gain_db', bad[0]['rejection_reason'])

    def test_sql_known_yield(self):
        a, b = self.row(), self.row()
        b.update(device_id='D02', gain_db=17)
        good, _ = pipeline.validate([a, b])
        connection, result = pipeline.analyze(good)
        connection.close()
        self.assertEqual(result['overall'][0]['yield_percent'], 50)
        self.assertEqual(result['overall'][0]['devices_failed'], 1)

    def test_generated_accounting(self):
        raw = pipeline.generate()
        good, bad = pipeline.validate(raw)
        self.assertEqual(len(raw), 12020)
        self.assertEqual(len(good), 11900)
        self.assertEqual(len(bad), 120)
        self.assertEqual(len({r['device_id'] for r in good}), len(good))


if __name__ == '__main__':
    unittest.main()
