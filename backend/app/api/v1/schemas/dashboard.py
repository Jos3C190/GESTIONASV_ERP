"""Dashboard aggregate DTOs."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class DepartmentDistributionOut(BaseModel):
    label: str
    value: int


class ActivitySeriesPointOut(BaseModel):
    date: date
    value: int


class DashboardPersonOut(BaseModel):
    id: uuid.UUID
    name: str
    initials: str
    department: str


class RecentUserOut(DashboardPersonOut):
    status: str
    created_at: datetime


class DashboardSummaryOut(BaseModel):
    active_users: int
    employees: int
    warehouses: int
    events_today: int
    branches: int
    onboarding_progress: int
    department_distribution: list[DepartmentDistributionOut]
    activity_series: list[ActivitySeriesPointOut]
    team: list[DashboardPersonOut]
    recent_users: list[RecentUserOut]
