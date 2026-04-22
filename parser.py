import json

import requests
from bs4 import BeautifulSoup
from datetime import datetime

UTL = "https://timetable.magtu.ru"

def get_html(group:str) -> str:
    response = requests.get(f"{UTL}/{group}")
    return response.text

def check_week_parity() -> bool:
    """Проверка на четность недели

    Returns:
        bool: True - если неделя четная, False - если нечетная
    """    
    week_number = datetime.now().isocalendar()[1]
    
    if week_number % 2 == 0:
        return True
    else:
        return False


def get_timetable(group:str, all_weeks:bool=False) -> str|None:
    html = get_html(group)
    soup = BeautifulSoup(html, 'html.parser')
    timetable = {}

    if all_weeks:
        week_num = ["1", "2"]
    else:
        if check_week_parity():
            week_num = "1"
        else:
            week_num = "2"

    for week_id in week_num:
        timetable[week_id] = {}
        week = soup.find('div', id=f'week-{week_id}')
        if not week:
            return None

        days = week.find_all('div', class_='day')
        for day in days:
            day_name = day.find('div', class_='day-name').text.strip() # type: ignore
            timetable[week_id][day_name] = {}
            lessons = day.find_all('div', class_='less-wrap')
            if not lessons:
                continue
            for lesson in lessons:
                title = lesson.find('div', class_='title').text.strip() # type: ignore
                clearfix_div = lesson.find('div', class_='clearfix')
                les_type = (
                    clearfix_div.find(string=True, recursive=False).strip() # type: ignore
                    if clearfix_div and clearfix_div.find(string=True, recursive=False)
                    else "Нет данных"
                )
                teachers = [teacher.text.strip() for teacher in lesson.find_all('div', class_='teacher')]
                aud = lesson.find('div', class_='aud').text.strip() # type: ignore
                time  = lesson.find('div', class_='time').text.strip() # type: ignore
                couple_number = lesson.find('div', class_='couple-number').text.strip() # type: ignore

                timetable[week_id][day_name][couple_number] = {}
                timetable[week_id][day_name][couple_number]["title"] = title
                timetable[week_id][day_name][couple_number]["type"] = les_type
                timetable[week_id][day_name][couple_number]["teachers"] = teachers
                timetable[week_id][day_name][couple_number]["aud"] = aud
                timetable[week_id][day_name][couple_number]["time"] = time

    return json.dumps(timetable)

if __name__ == "__main__":
    data = get_timetable("АВб-25-2_2", True)
    if data:
        print(json.loads(data))