"""Schedule Manager - assigns posting time slots for daily batch uploads."""

from datetime import date, datetime, time
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python < 3.9 fallback to pytz
    try:
        import pytz
        ZoneInfo = None  # Use pytz instead
    except ImportError:
        raise ImportError(
            "Timezone support requires either Python 3.9+ (zoneinfo) or pytz package. "
            "Install with: pip install pytz"
        )


class ScheduleManager:
    """Manages daily posting schedule with configurable time slots."""

    def __init__(self, timezone: str = "Europe/London", posting_hours: Optional[list[int]] = None):
        """
        Initialize schedule manager.

        Args:
            timezone: Timezone string (e.g., "Europe/London", "America/New_York")
            posting_hours: List of posting hours in local time (24-hour format, e.g., [11, 14, 18, 20, 22]).
                          Defaults to [11, 14, 18, 20, 22] if not provided.
        """
        self.timezone_str = timezone
        self.posting_hours = posting_hours or [11, 14, 18, 20, 22]
        
        # Validate posting hours
        if not self.posting_hours:
            raise ValueError("posting_hours cannot be empty")
        for hour in self.posting_hours:
            if not isinstance(hour, int) or hour < 0 or hour > 23:
                raise ValueError(f"Invalid posting hour: {hour}. Must be integer between 0-23.")
        
        if ZoneInfo is not None:
            # Python 3.9+ with zoneinfo
            try:
                self.tz = ZoneInfo(timezone)
            except Exception as e:
                raise ValueError(f"Unknown timezone: {timezone}. Error: {e}")
        else:
            # Fallback to pytz
            try:
                self.tz = pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                raise ValueError(f"Unknown timezone: {timezone}. Use a valid pytz timezone string.")

    def get_daily_slots(self, target_date: date, count: int) -> list[datetime]:
        """
        Get posting time slots for a given date.

        Args:
            target_date: Date to schedule posts for
            count: Number of slots needed

        Returns:
            List of timezone-aware datetime objects in the configured timezone

        Business rules:
        - If count < len(posting_hours), use the first N hours
        - If count > len(posting_hours), repeat the sequence
        """
        slots = []
        hours_used = 0

        while len(slots) < count:
            # Cycle through posting hours
            hour_index = hours_used % len(self.posting_hours)
            hour = self.posting_hours[hour_index]

            # Create datetime in the target timezone
            local_time = datetime.combine(target_date, time(hour=hour, minute=0, second=0))
            # Make it timezone-aware
            if ZoneInfo is not None:
                # Python 3.9+ with zoneinfo
                timezone_aware_dt = local_time.replace(tzinfo=self.tz)
            else:
                # Fallback to pytz
                timezone_aware_dt = self.tz.localize(local_time)

            slots.append(timezone_aware_dt)
            hours_used += 1

        return slots

