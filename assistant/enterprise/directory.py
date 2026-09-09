# -*- coding: utf-8 -*-
"""员工名录：姓名 → userid / 分机 / 部门。本地 JSON，隐私数据不入 git。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Employee:
    name: str
    userid: str
    department: str
    title: str
    ext: str
    role: str = "staff"


class EmployeeDirectory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.employees: list[Employee] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        self.employees = [Employee(**item) for item in raw]

    def find(self, name: str) -> Optional[Employee]:
        """按姓名精确匹配；退化为包含匹配（如「给王总发消息」匹配不到就 None）。"""
        name = name.strip()
        for emp in self.employees:
            if emp.name == name:
                return emp
        for emp in self.employees:
            if name in emp.name:
                return emp
        return None

    def by_department(self, department: str) -> list[Employee]:
        return [e for e in self.employees if department in e.department]
