from datetime import datetime, timedelta

from django.utils import timezone

from posthog.constants import INSIGHT_FUNNELS, FunnelVizType
from posthog.models.filters import Filter
from posthog.queries.funnels.funnel_trends_persons import ClickhouseFunnelTrendsActors
from posthog.session_recordings.test.test_factory import create_session_recording_events
from posthog.test.base import APIBaseTest, ClickhouseTestMixin, snapshot_clickhouse_queries
from posthog.test.test_journeys import journeys_for

filter_data = {
    "insight": INSIGHT_FUNNELS,
    "funnel_viz_type": FunnelVizType.TRENDS,
    "interval": "day",
    "date_from": "2021-05-01 00:00:00",
    "date_to": "2021-05-07 23:59:59",
    "funnel_window_days": 14,
    "funnel_from_step": 0,
    "entrance_period_start": "2021-05-01 00:00:00",
    "drop_off": False,
    "events": [{"id": "step one", "order": 0}, {"id": "step two", "order": 1}, {"id": "step three", "order": 2}],
    "include_recordings": "true",
}


class TestFunnelTrendsPersons(ClickhouseTestMixin, APIBaseTest):
    @snapshot_clickhouse_queries
    def test_funnel_trend_persons_returns_recordings(self):
        persons = journeys_for(
            {
                "user_one": [
                    {"event": "step one", "timestamp": datetime(2021, 5, 1), "properties": {"$session_id": "s1a"}},
                    {"event": "step two", "timestamp": datetime(2021, 5, 2), "properties": {"$session_id": "s1b"}},
                    {"event": "step three", "timestamp": datetime(2021, 5, 3), "properties": {"$session_id": "s1c"}},
                ]
            },
            self.team,
        )
        create_session_recording_events(self.team.pk, timezone.now() + timedelta(days=1), "user_one", "s1b")

        filter = Filter(data={"funnel_to_step": 1, **filter_data})
        _, results, _ = ClickhouseFunnelTrendsActors(filter, self.team).get_actors()
        self.assertEqual([person["id"] for person in results], [persons["user_one"].uuid])
        self.assertEqual([person["matched_recordings"][0]["session_id"] for person in results], ["s1b"])

    @snapshot_clickhouse_queries
    def test_funnel_trend_persons_with_no_to_step(self):
        persons = journeys_for(
            {
                "user_one": [
                    {"event": "step one", "timestamp": datetime(2021, 5, 1), "properties": {"$session_id": "s1a"}},
                    {"event": "step two", "timestamp": datetime(2021, 5, 2), "properties": {"$session_id": "s1b"}},
                    {"event": "step three", "timestamp": datetime(2021, 5, 3), "properties": {"$session_id": "s1c"}},
                ]
            },
            self.team,
        )
        create_session_recording_events(self.team.pk, timezone.now() + timedelta(days=1), "user_one", "s1c")

        filter = Filter(data=filter_data)
        _, results, _ = ClickhouseFunnelTrendsActors(filter, self.team).get_actors()
        self.assertEqual([person["id"] for person in results], [persons["user_one"].uuid])
        self.assertEqual([person["matched_recordings"][0]["session_id"] for person in results], ["s1c"])

    @snapshot_clickhouse_queries
    def test_funnel_trend_persons_with_drop_off(self):
        persons = journeys_for(
            {
                "user_one": [
                    {"event": "step one", "timestamp": datetime(2021, 5, 1), "properties": {"$session_id": "s1a"}}
                ]
            },
            self.team,
        )
        create_session_recording_events(self.team.pk, timezone.now() + timedelta(days=1), "user_one", "s1a")

        filter = Filter(data={**filter_data, "drop_off": True})
        _, results, _ = ClickhouseFunnelTrendsActors(filter, self.team).get_actors()
        self.assertEqual([person["id"] for person in results], [persons["user_one"].uuid])
        self.assertEqual([person["matched_recordings"][0].get("session_id") for person in results], ["s1a"])
