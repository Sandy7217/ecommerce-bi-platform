from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RegionalReturnKpiTest(unittest.TestCase):
    def test_regional_return_kpi_uses_overall_rate_not_max_state_outlier(self) -> None:
        source = (ROOT / "frontend" / "app" / "(dashboard)" / "regional" / "RegionalClient.tsx").read_text()

        self.assertIn("const regionalReturnPct = totalQty ? (totalReturns * 100) / totalQty : 0;", source)
        self.assertIn('title="Return %"', source)
        self.assertIn("value={regionalReturnPct}", source)
        self.assertNotIn("Highest Return %", source)
        self.assertNotIn("highestReturn", source)

    def test_regional_page_filters_metrics_and_tables_by_selected_state(self) -> None:
        source = (ROOT / "frontend" / "app" / "(dashboard)" / "regional" / "RegionalClient.tsx").read_text()

        self.assertIn('const [selectedState, setSelectedState] = useState("all");', source)
        self.assertIn('selectedState === "all" ? states : states.filter((row) => row.state === selectedState)', source)
        self.assertIn("filteredStates.reduce", source)
        self.assertIn("<select", source)
        self.assertIn('<option value="all">All states</option>', source)
        self.assertIn("setSelectedState(event.target.value)", source)
        self.assertIn("<IndiaMap data={filteredStates} />", source)
        self.assertIn("rows={filteredStates}", source)


if __name__ == "__main__":
    unittest.main()
