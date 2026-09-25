"""桥梁档案业务规则：状态流转、字段校验、多条件筛选/排序与常用视图都收在这里。

筛选条件口径：
- 桥梁类型、桥梁状态按精确值匹配，取值必须来自现有数据/允许集合；
- 最大跨径、建成年份支持闭区间，区间端点写反（下限 > 上限）视为条件矛盾，不执行查询；
- 关键字在桥梁编码、桥梁名称内做包含匹配。
任何不合规项由 validate_filters 收集为字段级错误，路由层据此返回 400，不静默给结果。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.store import store

MODULE = "bridge"
REQUIRED_FIELDS = ["桥梁编码", "桥梁名称", "桥梁类型"]
STATUS_ORDER = ["待移交", "正常养护", "限载通行", "封闭施工"]
ACTION_RULES = {"办理移交": "正常养护", "申请限载": "限载通行", "封闭桥梁": "封闭施工"}
NEGATIVE_ACTIONS = ["申请限载"]

# 列表与导出共用的字段顺序；最大跨径是本次筛选新增的结构参数
LIST_FIELDS = ["桥梁编码", "桥梁名称", "桥梁类型", "跨越对象", "桥梁全长", "最大跨径", "设计荷载", "建成年份"]
SORTABLE_FIELDS = {"桥梁编码", "桥梁名称", "桥梁类型", "桥梁全长", "最大跨径", "建成年份"}

# 详情页段落分组：从列表点字段可以直接定位到对应段落
DETAIL_SECTIONS = {
    "basic": {"title": "基本信息", "fields": ["桥梁编码", "桥梁名称", "桥梁类型", "跨越对象"]},
    "structure": {"title": "结构参数", "fields": ["桥梁全长", "最大跨径", "设计荷载"]},
    "build": {"title": "建成信息", "fields": ["建成年份"]},
    "manage": {"title": "管养信息", "fields": ["所在道路", "管养单位", "桥梁状态"]},
}
# 字段 -> 详情段落锚点
FIELD_ANCHORS = {
    field: anchor
    for anchor, section in DETAIL_SECTIONS.items()
    for field in section["fields"]
}

MIN_YEAR = 1800
MAX_YEAR = datetime.now().year
MIN_SPAN = 0.0
MAX_SPAN = 100000.0  # 米，市政/公路桥梁量级足够，超出按不合规处理

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _to_number(value: Any) -> float | None:
    """把 '120'、'120m'、'1,200' 之类宽松解析成数字；解析不出来返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if match is None:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _compact(values: dict[str, Any]) -> dict[str, str]:
    return {key: str(value).strip() for key, value in values.items() if str(value or "").strip()}


class BridgeService:
    def __init__(self) -> None:
        # 常用视图放内存仓库，和其它数据一致：重启回到示例状态
        self._views: list[dict[str, Any]] = []

    # ---------- 元数据 ----------
    def metadata(self) -> dict[str, Any]:
        """提供筛选项取值：桥梁类型、状态来自现有数据，避免前端写死后与数据脱节。"""
        rows = store.rows(MODULE)
        types = sorted({str(row.get("桥梁类型", "")).strip() for row in rows if row.get("桥梁类型")})
        spans = [num for num in (_to_number(row.get("最大跨径")) for row in rows) if num is not None]
        years = [int(num) for num in (_to_number(row.get("建成年份")) for row in rows) if num is not None]
        return {
            "types": types,
            "statuses": list(STATUS_ORDER),
            "sortable_fields": sorted(SORTABLE_FIELDS),
            "span": {"min": min(spans) if spans else None, "max": max(spans) if spans else None, "unit": "米"},
            "year": {"min": min(years) if years else None, "max": max(years) if years else None},
        }

    # ---------- 筛选校验 ----------
    def validate_filters(self, params: dict[str, Any]) -> tuple[dict[str, str], list[dict[str, str]]]:
        """校验并归一化筛选/排序参数。

        返回 (clean, errors)：errors 为空时 clean 可直接用于 list_entries；
        非空时调用方不得再查询，必须把每个错误项（field + message）告诉用户。
        """
        errors: list[dict[str, str]] = []

        def add_error(field: str, message: str) -> None:
            errors.append({"field": field, "message": message})

        bridge_type = str(params.get("bridge_type") or "").strip()
        if bridge_type:
            known_types = set(self.metadata()["types"])
            if bridge_type not in known_types:
                add_error("bridge_type", f"桥梁类型「{bridge_type}」不在可筛选的类型范围内")

        status = str(params.get("status") or "").strip()
        if status and status not in STATUS_ORDER:
            add_error("status", f"桥梁状态「{status}」不支持，可选：{'、'.join(STATUS_ORDER)}")

        span_min = self._parse_bound(params.get("span_min"), "span_min", "跨径下限", MIN_SPAN, MAX_SPAN, add_error)
        span_max = self._parse_bound(params.get("span_max"), "span_max", "跨径上限", MIN_SPAN, MAX_SPAN, add_error)
        if span_min is not None and span_max is not None and span_min > span_max:
            add_error("span_max", f"跨径区间写反了：下限 {span_min:g} 米不能大于上限 {span_max:g} 米")

        year_min = self._parse_year_bound(params.get("year_min"), "year_min", "年份下限", add_error)
        year_max = self._parse_year_bound(params.get("year_max"), "year_max", "年份上限", add_error)
        if year_min is not None and year_max is not None and year_min > year_max:
            add_error("year_max", f"建成年份区间写反了：下限 {year_min} 不能晚于上限 {year_max}")

        sort_by = str(params.get("sort_by") or "").strip()
        if sort_by and sort_by not in SORTABLE_FIELDS:
            add_error("sort_by", f"不支持按「{sort_by}」排序")
        sort_order = str(params.get("sort_order") or "asc").strip()
        if sort_order not in {"asc", "desc"}:
            add_error("sort_order", "排序方向只能是升序（asc）或降序（desc）")

        try:
            page = int(str(params.get("page") or 1))
            if page < 1:
                add_error("page", "页码必须从 1 开始")
                page = 1
        except (TypeError, ValueError):
            add_error("page", "页码必须是整数")
            page = 1
        try:
            size = int(str(params.get("size") or 20))
            if not 1 <= size <= 200:
                add_error("size", "每页条数需在 1 到 200 之间")
                size = min(max(size, 1), 200)
        except (TypeError, ValueError):
            add_error("size", "每页条数必须是整数")
            size = 20

        clean = {
            "keyword": str(params.get("keyword") or "").strip(),
            "bridge_type": bridge_type,
            "status": status,
            "span_min": span_min,
            "span_max": span_max,
            "year_min": year_min,
            "year_max": year_max,
            "sort_by": sort_by or "桥梁编码",
            "sort_order": sort_order or "asc",
            "page": page,
            "size": size,
        }
        return clean, errors

    @staticmethod
    def _parse_bound(
        raw: Any,
        field: str,
        label: str,
        floor: float,
        ceiling: float,
        add_error,
    ) -> float | None:
        text = str(raw or "").strip()
        if not text:
            return None
        number = _to_number(text)
        if number is None:
            add_error(field, f"{label}「{text}」不是有效数字")
            return None
        if not floor <= number <= ceiling:
            add_error(field, f"{label}需在 {floor:g} 到 {ceiling:g} 米之间")
            return None
        return number

    def _parse_year_bound(self, raw: Any, field: str, label: str, add_error) -> int | None:
        text = str(raw or "").strip()
        if not text:
            return None
        number = _to_number(text)
        if number is None or number != int(number):
            add_error(field, f"{label}「{text}」不是有效年份（4 位整数）")
            return None
        year = int(number)
        if not MIN_YEAR <= year <= MAX_YEAR:
            add_error(field, f"{label}需在 {MIN_YEAR} 到 {MAX_YEAR} 之间")
            return None
        return year

    # ---------- 列表 ----------
    def list_entries(
        self,
        *,
        clean: dict[str, Any] | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """按归一化条件筛选并排序。clean 为 None 时等价于无条件（供导出使用）。"""
        rows = [dict(row) for row in store.rows(MODULE)]
        if clean is not None:
            rows = self._apply_filters(rows, clean)
        total = len(rows)
        if clean is not None:
            rows = self._apply_sort(rows, clean["sort_by"], clean["sort_order"])
            page, size = clean["page"], clean["size"]
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def _apply_filters(self, rows: list[dict[str, Any]], clean: dict[str, Any]) -> list[dict[str, Any]]:
        result = rows
        keyword = clean.get("keyword")
        if keyword:
            result = [
                row for row in result
                if keyword in str(row.get("桥梁编码", "")) or keyword in str(row.get("桥梁名称", ""))
            ]
        bridge_type = clean.get("bridge_type")
        if bridge_type:
            result = [row for row in result if str(row.get("桥梁类型", "")).strip() == bridge_type]
        status = clean.get("status")
        if status:
            result = [row for row in result if row.get("status") == status]
        span_min, span_max = clean.get("span_min"), clean.get("span_max")
        if span_min is not None or span_max is not None:
            kept: list[dict[str, Any]] = []
            for row in result:
                span = _to_number(row.get("最大跨径"))
                if span is None:
                    continue
                if span_min is not None and span < span_min:
                    continue
                if span_max is not None and span > span_max:
                    continue
                kept.append(row)
            result = kept
        year_min, year_max = clean.get("year_min"), clean.get("year_max")
        if year_min is not None or year_max is not None:
            kept = []
            for row in result:
                year = _to_number(row.get("建成年份"))
                if year is None or year != int(year):
                    continue
                year = int(year)
                if year_min is not None and year < year_min:
                    continue
                if year_max is not None and year > year_max:
                    continue
                kept.append(row)
            result = kept
        return result

    def _apply_sort(self, rows: list[dict[str, Any]], sort_by: str, sort_order: str) -> list[dict[str, Any]]:
        numeric = sort_by in {"桥梁全长", "最大跨径", "建成年份"}

        def key(row: dict[str, Any]):
            raw = row.get(sort_by)
            if numeric:
                number = _to_number(raw)
                return (number is None, number if number is not None else 0.0)
            return (False, str(raw or ""))

        return sorted(rows, key=key, reverse=sort_order == "desc")

    # ---------- 详情 ----------
    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def detail(self, entry_id: int) -> dict[str, Any] | None:
        """详情：在原始记录基础上附段落分组，供前端锚点定位。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        sections: list[dict[str, Any]] = []
        for anchor, section in DETAIL_SECTIONS.items():
            fields = [
                {"name": name, "value": entry.get(name) if entry.get(name) not in (None, "") else "—"}
                for name in section["fields"]
            ]
            sections.append({"anchor": anchor, "title": section["title"], "fields": fields})
        result = dict(entry)
        result["sections"] = sections
        return result

    # ---------- 登记与状态流转（保持原行为） ----------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"桥梁设施 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于桥梁档案可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"桥梁设施已{action}"

    # ---------- 常用视图 ----------
    def list_views(self) -> list[dict[str, Any]]:
        return [dict(view) for view in self._views]

    def create_view(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, list[dict[str, str]]]:
        """保存常用视图：视图名必填且不得重名，筛选条件本身要合规。"""
        name = str(values.get("name") or "").strip()
        if not name:
            return None, "视图名称不能为空", []
        if any(view["name"] == name for view in self._views):
            return None, f"常用视图「{name}」已存在，请换个名称", []
        criteria = values.get("criteria") if isinstance(values.get("criteria"), dict) else {}
        _, errors = self.validate_filters(criteria)
        if errors:
            return None, None, errors
        view = {
            "id": max((int(item.get("id", 0)) for item in self._views), default=0) + 1,
            "name": name,
            "criteria": _compact(criteria),
        }
        self._views.append(view)
        return dict(view), None, []

    def delete_view(self, view_id: int) -> bool:
        before = len(self._views)
        self._views = [view for view in self._views if int(view.get("id", 0)) != view_id]
        return len(self._views) < before
