from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class UserMonthlySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    user_id: str
    month: date
    income: int
    surplus: int
    cash: int
    debt_to_income_ratio: Decimal
    buffer_coverage_months: Decimal
    computed_at: datetime
