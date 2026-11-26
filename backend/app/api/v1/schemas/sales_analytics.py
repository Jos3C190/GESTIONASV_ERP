"""DTO del análisis comercial y las metas de venta (V9a)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class TotalsOut(BaseModel):
    net_sales: Decimal
    documents: int
    average_ticket: Decimal | None
    returns: Decimal
    returns_percent: Decimal | None
    cost: Decimal | None = None
    margin: Decimal | None = None
    margin_percent: Decimal | None = None


class BucketOut(BaseModel):
    key: str
    label: str
    net_sales: Decimal
    documents: int
    quantity: Decimal
    cost: Decimal | None = None
    margin: Decimal | None = None
    margin_percent: Decimal | None = None
    goal: Decimal | None = None
    goal_percent: Decimal | None = None


class AnalysisOut(BaseModel):
    start: date
    end: date
    costs_visible: bool
    totals: TotalsOut
    by_day: list[BucketOut]
    by_hour: list[BucketOut]
    by_branch: list[BucketOut]
    by_category: list[BucketOut]
    top_customers: list[BucketOut]
    top_products: list[BucketOut]
    bottom_products: list[BucketOut]


class BranchGoalOut(BaseModel):
    branch_id: uuid.UUID
    branch_name: str
    amount: Decimal | None


class GoalsOut(BaseModel):
    period: str
    goals: list[BranchGoalOut]


class GoalIn(BaseModel):
    branch_id: uuid.UUID
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)


class GoalsIn(BaseModel):
    goals: list[GoalIn] = Field(min_length=1, max_length=200)
