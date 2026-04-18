from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from caldav import DAVClient
from lxml import etree
import requests
import vobject


@dataclass
class NaverCalendarEvent:
    uid: str | None
    summary: str
    start: datetime
    end: datetime
    is_all_day: bool


def _to_datetime(value: date | datetime, timezone: ZoneInfo) -> tuple[datetime, bool]:
    if isinstance(value, datetime):
        dt_value = value
        if dt_value.tzinfo is None:
            dt_value = dt_value.replace(tzinfo=timezone)
        return dt_value.astimezone(timezone), False

    start_dt = datetime.combine(value, time.min, tzinfo=timezone)
    return start_dt, True


def _iter_vevents(vobject_instance):
    if hasattr(vobject_instance, "vevent_list"):
        return vobject_instance.vevent_list
    if hasattr(vobject_instance, "vevent"):
        return [vobject_instance.vevent]
    return []


def _events_from_vobject(vobject_instance, start: datetime, end: datetime, timezone: ZoneInfo) -> list[NaverCalendarEvent]:
    result: list[NaverCalendarEvent] = []

    for vevent in _iter_vevents(vobject_instance):
        summary = str(getattr(getattr(vevent, "summary", None), "value", "")).strip()
        uid = getattr(getattr(vevent, "uid", None), "value", None)

        raw_start = getattr(getattr(vevent, "dtstart", None), "value", None)
        raw_end = getattr(getattr(vevent, "dtend", None), "value", None)
        if raw_start is None:
            continue

        start_dt, is_all_day = _to_datetime(raw_start, timezone)
        if raw_end is None:
            end_dt = start_dt + (timedelta(days=1) if is_all_day else timedelta(hours=1))
        else:
            end_dt, _ = _to_datetime(raw_end, timezone)

        if end_dt <= start or start_dt >= end:
            continue

        result.append(
            NaverCalendarEvent(
                uid=uid,
                summary=summary,
                start=start_dt,
                end=end_dt,
                is_all_day=is_all_day,
            )
        )

    return result


def _fetch_calendar_ics_events(calendar, start: datetime, end: datetime, timezone: ZoneInfo) -> list[NaverCalendarEvent]:
    client = calendar.client
    if client is None or calendar.url is None:
        return []

    # Ensure caldav client negotiates auth first (401 challenge).
    client.options(str(calendar.url))

    report_xml, _ = calendar.build_search_xml_query(
        event=True,
        start=start,
        end=end,
        expand=True,
    )
    payload = etree.tostring(
        report_xml.xmlelement(),
        encoding="utf-8",
        xml_declaration=True,
    )

    headers = dict(client.headers)
    headers["Depth"] = "1"
    headers["Content-Type"] = 'application/xml; charset="utf-8"'
    headers["Accept"] = "text/calendar, application/xml, text/xml, */*"

    response = client.session.request(
        "REPORT",
        str(calendar.url),
        data=payload,
        headers=headers,
        auth=client.auth,
        timeout=client.timeout,
        verify=client.ssl_verify_cert,
        cert=client.ssl_cert,
    )
    response.raise_for_status()

    text = response.content.decode(response.encoding or "utf-8", errors="replace")
    events: list[NaverCalendarEvent] = []

    xml_root = None
    try:
        xml_root = etree.fromstring(response.content)
    except etree.XMLSyntaxError:
        xml_root = None

    # If REPORT returns raw ICS, parse as-is.
    if xml_root is None:
        if "BEGIN:VCALENDAR" in text:
            for component in vobject.readComponents(text):
                events.extend(_events_from_vobject(component, start, end, timezone))
        return events

    # If REPORT returns XML multistatus, parse embedded calendar-data first.
    calendar_data_nodes = xml_root.xpath("//*[local-name()='calendar-data']")
    for node in calendar_data_nodes:
        ics_text = (node.text or "").strip()
        if not ics_text or "BEGIN:VCALENDAR" not in ics_text:
            continue
        for component in vobject.readComponents(ics_text):
            events.extend(_events_from_vobject(component, start, end, timezone))

    if events:
        return events

    # Some servers return XML multistatus with hrefs to .ics resources.
    href_nodes = xml_root.xpath(
        "//*[local-name()='response'][.//*[local-name()='status' and contains(text(), '200')]]/*[local-name()='href']"
    )

    for href_node in href_nodes:
        href_text = (href_node.text or "").strip()
        if not href_text:
            continue
        ics_url = urljoin(str(calendar.url), href_text)
        ics_resp = client.session.request(
            "GET",
            ics_url,
            headers={"Accept": "text/calendar, text/plain, */*"},
            auth=client.auth,
            timeout=client.timeout,
            verify=client.ssl_verify_cert,
            cert=client.ssl_cert,
        )
        if ics_resp.status_code >= 400:
            continue

        ics_text = ics_resp.content.decode(ics_resp.encoding or "utf-8", errors="replace")
        if "BEGIN:VCALENDAR" not in ics_text:
            continue

        for component in vobject.readComponents(ics_text):
            events.extend(_events_from_vobject(component, start, end, timezone))

    return events


def _extract_events_from_calendar(calendar, start: datetime, end: datetime, timezone: ZoneInfo) -> list[NaverCalendarEvent]:
    result = _fetch_calendar_ics_events(calendar, start, end, timezone)
    result.sort(key=lambda item: item.start)
    return result


def get_naver_today_events(
    *,
    caldav_url: str,
    username: str,
    password: str,
    timezone: ZoneInfo,
    calendar_name: str | None = None,
    now: datetime | None = None,
) -> list[NaverCalendarEvent]:
    base_time = now.astimezone(timezone) if now is not None else datetime.now(timezone)
    day_start = datetime.combine(base_time.date(), time.min, tzinfo=timezone)
    day_end = day_start + timedelta(days=1)

    with DAVClient(url=caldav_url, username=username, password=password) as client:
        principal = client.principal()
        calendars = principal.calendars()

        if calendar_name:
            calendars = [calendar for calendar in calendars if calendar.name == calendar_name]

        all_events: list[NaverCalendarEvent] = []
        for calendar in calendars:
            all_events.extend(_extract_events_from_calendar(calendar, day_start, day_end, timezone))

    all_events.sort(key=lambda item: item.start)
    return all_events
