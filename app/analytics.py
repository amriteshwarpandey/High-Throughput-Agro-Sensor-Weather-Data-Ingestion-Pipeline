"""Aggregate queries, cached in Redis for 15 minutes."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Region, SensorReading as R
from .redis_client import cached


def _since(months: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=30 * months)


def _r(v):
    return None if v is None else round(float(v), 3)


def district_soil_carbon(db: Session, months: int):
    def compute():
        q = (select(Region.district, func.avg(R.soil_organic_carbon), func.count(R.id))
             .join(Region, Region.id == R.region_id)
             .where(R.recorded_at >= _since(months), R.soil_organic_carbon.is_not(None))
             .group_by(Region.district).order_by(Region.district))
        return [{"district": d, "avg_soil_organic_carbon": _r(a), "readings": n} for d, a, n in db.execute(q)]
    return cached("district_soc", (months,), compute)


def region_summary(db: Session, region_id: int, months: int):
    def compute():
        q = select(func.count(R.id), func.avg(R.soil_organic_carbon), func.avg(R.soil_moisture),
                   func.avg(R.soil_ph), func.avg(R.temperature_c), func.avg(R.rainfall_mm)
                   ).where(R.region_id == region_id, R.recorded_at >= _since(months))
        n, soc, moist, ph, temp, rain = db.execute(q).one()
        return {"readings": n, "avg_soil_organic_carbon": _r(soc), "avg_soil_moisture": _r(moist),
                "avg_soil_ph": _r(ph), "avg_temperature_c": _r(temp), "avg_rainfall_mm": _r(rain)}
    return cached("region_summary", (region_id, months), compute)


def region_monthly(db: Session, region_id: int, months: int):
    def compute():
        if db.bind.dialect.name == "postgresql":
            month = func.to_char(func.date_trunc("month", R.recorded_at), "YYYY-MM")
        else:
            month = func.strftime("%Y-%m", R.recorded_at)
        q = (select(month.label("m"), func.avg(R.soil_organic_carbon), func.avg(R.soil_moisture), func.count(R.id))
             .where(R.region_id == region_id, R.recorded_at >= _since(months))
             .group_by("m").order_by("m"))
        return [{"month": m, "avg_soil_organic_carbon": _r(a), "avg_soil_moisture": _r(b), "readings": n}
                for m, a, b, n in db.execute(q)]
    return cached("region_monthly", (region_id, months), compute)
