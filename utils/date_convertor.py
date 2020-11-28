from datetime import datetime, timedelta
from typing import Optional


def convert_date_to_abs(dt) -> Optional[datetime]:
    now = datetime.now().replace(minute=0, hour=0, second=0, microsecond=0)
    if isinstance(dt, dict):
        if dt.get('day_is_relative') and not dt.get('month'):
            return now + timedelta(dt['day'])
        elif dt.get('day_is_relative') is False:
            month = now.month
            if dt.get('month_is_relative') is False:
                month = dt['month']
            result_date = datetime(day=dt['day'], month=month, year=now.year)
            if result_date < now:
                result_date = result_date.replace(result_date.year + 1)
            return result_date
        else:
            # don't know how to parse it
            return
    elif isinstance(dt, str):
        if dt == 'сегодня':
            return now
        elif dt == 'завтра':
            return now + timedelta(days=1)
        elif dt == 'послезавтра':
            return now + timedelta(days=2)


def date2ru(dt: datetime):
    if dt:
        return dt.strftime('%d.%m.%Y')
