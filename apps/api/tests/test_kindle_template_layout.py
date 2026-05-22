from pathlib import Path
import unittest


TEMPLATE = Path(__file__).resolve().parents[1] / "static" / "templates" / "kindle_home.html"


class KindleTemplateLayoutTest(unittest.TestCase):
    def test_current_sky_text_is_grouped_with_temperature(self):
        template = TEMPLATE.read_text()
        temp_block_start = template.index('<div class="flex items-start gap-2 sm:gap-3">')
        meta_block_start = template.index('{{ weather.region }}')
        temp_block = template[temp_block_start:meta_block_start]
        temp_size_class = "text-[clamp(2.55rem,9.2vw,4.15rem)]"

        self.assertIn("weather.current.sky_text", temp_block)
        self.assertIn("kindle-current-condition", temp_block)
        self.assertIn("items-baseline", temp_block)
        self.assertIn("self-start", temp_block)
        self.assertGreaterEqual(temp_block.count(temp_size_class), 2)

    def test_weather_cards_do_not_draw_outer_border(self):
        template = TEMPLATE.read_text()
        weather_card_start = template.index(".weather-card")
        weather_card_end = template.index(".chart-wrap")
        weather_card_css = template[weather_card_start:weather_card_end]

        self.assertIn("border: 0;", weather_card_css)

    def test_chart_uses_compact_height_to_reduce_bottom_whitespace(self):
        template = TEMPLATE.read_text()

        self.assertIn('viewBox="0 0 1000 160"', template)
        self.assertIn("const chartHeight = 160;", template)
        self.assertIn("const top = 34;", template)
        self.assertIn("const bottom = 2;", template)

    def test_chart_viewbox_tracks_rendered_width(self):
        template = TEMPLATE.read_text()

        self.assertIn("svg.clientWidth", template)
        self.assertIn('svg.setAttribute("viewBox"', template)
        self.assertNotIn("const width = 1000;", template)
        self.assertNotIn("Math.max(Math.ceil(svg.clientWidth), 1000)", template)
        self.assertIn('preserveAspectRatio="none"', template)

    def test_stage_expands_with_browser_width(self):
        template = TEMPLATE.read_text()
        stage_start = template.index(".stage")
        stage_end = template.index(".weather-card")
        stage_css = template[stage_start:stage_end]

        self.assertIn("width: 96vw;", stage_css)
        self.assertNotIn("1500px", stage_css)

    def test_weather_metrics_use_five_column_briefing_row(self):
        template = TEMPLATE.read_text()
        metrics_start = template.index("kindle-metrics")
        chart_start = template.index("chart-wrap", metrics_start)
        metrics_block = template[metrics_start:chart_start]

        self.assertIn("grid-cols-5", metrics_block)
        self.assertIn("강수", metrics_block)
        self.assertIn("습도", metrics_block)
        self.assertIn("풍속", metrics_block)
        self.assertIn("미세", metrics_block)
        self.assertIn("초미세", metrics_block)
        self.assertEqual(metrics_block.count("kindle-metric-value"), 5)
        self.assertIn("text-[clamp(0.92rem,3vw,1.18rem)]", metrics_block)

    def test_weekly_forecast_uses_connected_strip(self):
        template = TEMPLATE.read_text()
        strip_start = template.index("kindle-weekly-strip")
        strip_end = template.index("{% for day in weekly_outlook %}")
        strip_block = template[strip_start:strip_end]

        self.assertIn("kindle-weekly-strip", template)
        self.assertIn("border-y-2 border-[#1f1f1f]", strip_block)
        self.assertNotIn("rounded", strip_block)
        self.assertIn("border-r border-[#6b6b6b]", template)


if __name__ == "__main__":
    unittest.main()
