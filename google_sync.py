import json
from datetime import datetime, timedelta, time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from parser import get_timetable
from utils.config import config

SERVICE_ACCOUNT_FILE = config.CRED_PATH
TIMEZONE = "Europe/Moscow"
HOLIDAY_CALENDAR_ID = "ru.russian#holiday@group.v.calendar.google.com"


def get_service():
    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=scopes
    )
    return build("calendar", "v3", credentials=creds)


def is_holiday_date(service, date_obj):
    """
    Проверяет, является ли дата праздником, путем запроса к календарю праздников.
    Возвращает True, если в этот день есть событие в календаре праздников.
    """
    start_dt = datetime.combine(date_obj, time.min)
    end_dt = datetime.combine(date_obj, time.max)

    try:
        events = (
            service.events()
            .list(
                calendarId=HOLIDAY_CALENDAR_ID,
                timeMin=start_dt.isoformat() + "Z",
                timeMax=end_dt.isoformat() + "Z",
                maxResults=1,
            )
            .execute()
        )

        items = events.get("items", [])
        return len(items) > 0
    except HttpError:
        return False


def sync_timetable_to_calendar(data, CALENDAR_ID, colors=None):
    if colors is None:
        colors = {"Лекция": "5", "Практика": "6", "Лабораторная": "7"}

    if isinstance(data, str):
        data = json.loads(data)

    service = get_service()
    days_map = {
        "Понедельник": 0,
        "Вторник": 1,
        "Среда": 2,
        "Четверг": 3,
        "Пятница": 4,
        "Суббота": 5,
        "Воскресенье": 6,
    }

    now = datetime.now()
    current_monday = now - timedelta(days=now.weekday())
    current_monday = current_monday.replace(hour=0, minute=0, second=0, microsecond=0)

    current_week_num = now.isocalendar()[1]
    current_week_type = "1" if current_week_num % 2 != 0 else "2"

    weeks_to_sync = 2

    time_min = current_monday.isoformat() + "Z"
    time_max = (current_monday + timedelta(weeks=weeks_to_sync)).isoformat() + "Z"

    existing_events_map = {}
    try:
        events_result = (
            service.events()
            .list(
                calendarId=CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=2500,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        for event in events_result.get("items", []):
            ext_props = event.get("extendedProperties", {})
            private_props = ext_props.get("private", {})
            key = private_props.get("lesson_key")
            if key:
                existing_events_map[key] = event
    except HttpError:
        return

    processed_keys = set()
    batch = service.new_batch_http_request(callback=lambda *args: None)

    created_count = 0
    updated_count = 0
    deleted_count = 0

    holiday_cache = {}

    for week_id, days in data.items():
        if week_id == current_week_type:
            week_offset = 0
        elif week_id == ("2" if current_week_type == "1" else "1"):
            week_offset = 7
        else:
            continue

        for day_name, lessons in days.items():
            if day_name not in days_map or not lessons:
                continue

            day_index = days_map[day_name]
            event_date = (
                current_monday + timedelta(days=day_index + week_offset)
            ).date()

            if event_date not in holiday_cache:
                holiday_cache[event_date] = is_holiday_date(service, event_date)

            if holiday_cache[event_date]:
                continue  # Не создаем события в этот день

            for num, info in lessons.items():
                time_str = info["time"]
                time_parts = time_str.replace("–", "-").replace("—", "-").split("-")
                if len(time_parts) < 2:
                    continue

                start_time_str = time_parts[0].strip()
                end_time_str = time_parts[1].strip()

                start_dt = f"{event_date}T{start_time_str}:00"
                end_dt = f"{event_date}T{end_time_str}:00"

                unique_id = f"lesson_{week_id}_{day_index}_{num}"
                processed_keys.add(unique_id)

                event_body = {
                    "summary": f"{info['title']}",
                    "location": info["aud"],
                    "colorId": colors.get(info["type"], "5"),
                    "description": f"{info['type']}\nПреподаватели: {', '.join(info['teachers'])}",
                    "start": {"dateTime": start_dt, "timeZone": TIMEZONE},
                    "end": {"dateTime": end_dt, "timeZone": TIMEZONE},
                    "extendedProperties": {"private": {"lesson_key": unique_id}},
                }

                if unique_id in existing_events_map:
                    existing_event = existing_events_map[unique_id]
                    batch.add(
                        service.events().update(
                            calendarId=CALENDAR_ID,
                            eventId=existing_event["id"],
                            body=event_body,
                        )
                    )
                    updated_count += 1
                else:
                    batch.add(
                        service.events().insert(calendarId=CALENDAR_ID, body=event_body)
                    )
                    created_count += 1

    if batch._requests:
        batch.execute()

    keys_to_delete = set(existing_events_map.keys()) - processed_keys

    delete_batch = service.new_batch_http_request(callback=lambda *args: None)
    for key in keys_to_delete:
        event_id = existing_events_map[key]["id"]
        delete_batch.add(
            service.events().delete(calendarId=CALENDAR_ID, eventId=event_id)
        )
        deleted_count += 1

    if delete_batch._requests:
        delete_batch.execute()


if __name__ == "__main__":
    with open(config.USERS_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)

    service = get_service()

    for email in users.keys():
        try:
            timetable_data = get_timetable(users[email]["group"], True)
            if timetable_data:
                sync_timetable_to_calendar(
                    timetable_data, email, users[email].get("colors")
                )
        except Exception as e:
            print(f"Ошибка синхронизации для {email}: {e}")
