"""桥梁档案业务规则：多条件筛选、排序口径、筛选条件合规校验与常用视图都收在这里。"""
from __future__ import annotations

import datetime as _dt
from typing import Any

from app.store import store

MODULE = "bridge"
REQUIRED_FIELDS = ["桥梁编码", "桥梁名称", "桥梁类型"]
# 登记时允许一并落库的选填属性，原有的登记流程保持不变。
OPTIONAL_FIELDS = ["跨越对象", "桥梁全长", "最大跨径", "设计荷载", "建成年份", "桥梁状态"]
STATUS_ORDER = ["待移交", "正常养护", "限载通行", "封闭施工"]
ACTION_RULES = {"办理移交": "正常养护", "申请限载": "限载通行", "封闭桥梁": "封闭施工"}
NEGATIVE_ACTIONS = []

# 按《公路工程技术标准》JTG B01 以单孔最大跨径 L（米）划分桥涵分类。
SPAN_CLASSES: dict[str, tuple[float, float]] = {
    "特大桥": (100.0, float("inf")),
    "大桥": (40.0, 100.0),
    "中桥": (20.0, 40.0),
    "小桥": (5.0, 20.0),
    "涵洞": (0.0, 5.0),
}
BRIDGE_TYPES = ["梁桥", "拱桥", "刚构桥", "斜拉桥", "悬索桥"]
SORTABLE_FIELDS = ["最大跨径", "建成年份", "桥梁全长", "桥梁编码"]
MIN_YEAR = 1900
MAX_SPAN = 10000.0
MAX_LENGTH = 100000.0

# 列表字段顺序（供导出与登记回填使用）。
LIST_FIELDS = ["桥梁编码", "桥梁名称", "桥梁类型", "跨越对象", "桥梁全长", "最大跨径", "设计荷载", "建成年份", "桥梁状态"]


def _max_year() -> int:
    return _dt.date.today().year


def _to_number(value: Any) -> float | None:
    """把种子里以字符串存放的跨径/年份解析成数值；无法解析时返回 None，该行不参与数值条件。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class BridgeService:
    def __init__(self) -> None:
        # 常用筛选视图：{视图名: 查询参数}，随内存数据一起保存。
        self._views: dict[str, dict[str, Any]] = {}

    # ---- 列表筛选与排序 -------------------------------------------------

    def validate_filters(
        self,
        *,
        bridge_type: str | None = None,
        span_class: str | None = None,
        span_min: Any = None,
        span_max: Any = None,
        year_min: Any = None,
        year_max: Any = None,
        status: str | None = None,
        sort_by: str | None = None,
        sort_order: str = "asc",
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        """校验筛选条件，返回清洗后的参数与不合规项说明。

        跨径区间写反、年份区间写反、桥型与跨径分类互相矛盾时都会给出明确的条目。
        """
        errors: list[dict[str, str]] = []
        cleaned: dict[str, Any] = {
            "bridge_type": bridge_type,
            "span_class": span_class,
            "status": status,
            "sort_by": sort_by or "桥梁编码",
            "sort_order": "desc" if str(sort_order).lower() == "desc" else "asc",
        }

        if bridge_type and bridge_type not in BRIDGE_TYPES:
            errors.append({
                "field": "桥梁类型",
                "reason": f"「{bridge_type}」不在可选桥梁类型内，请从梁桥、拱桥、刚构桥、斜拉桥、悬索桥中选择",
            })
        if span_class and span_class not in SPAN_CLASSES:
            errors.append({
                "field": "跨径分类",
                "reason": f"「{span_class}」不是有效跨径分类，请从特大桥、大桥、中桥、小桥、涵洞 中选择",
            })
        if status and status not in STATUS_ORDER:
            errors.append({
                "field": "桥梁状态",
                "reason": f"「{status}」不在可筛选状态内，请从{'、'.join(STATUS_ORDER)}中选择",
            })
        if cleaned["sort_by"] not in SORTABLE_FIELDS:
            errors.append({
                "field": "排序字段",
                "reason": f"不支持按「{sort_by}」排序，可选：{'、'.join(SORTABLE_FIELDS)}",
            })

        span_lo = self._parse_bound("跨径下限", span_min, errors, minimum=0.0, maximum=MAX_SPAN)
        span_hi = self._parse_bound("跨径上限", span_max, errors, minimum=0.0, maximum=MAX_SPAN)
        year_lo = self._parse_bound("建成年份下限", year_min, errors, minimum=MIN_YEAR, maximum=float(_max_year()))
        year_hi = self._parse_bound("建成年份上限", year_max, errors, minimum=MIN_YEAR, maximum=float(_max_year()))

        if span_lo is not None and span_hi is not None and span_lo > span_hi:
            errors.append({
                "field": "跨径区间",
                "reason": f"跨径区间写反：下限 {span_lo:g} 米大于上限 {span_hi:g} 米，请对调后再查询",
            })
        if year_lo is not None and year_hi is not None and year_lo > year_hi:
            errors.append({
                "field": "建成年份",
                "reason": f"建成年份区间写反：起始年 {int(year_lo)} 晚于结束年 {int(year_hi)}，请对调后再查询",
            })

        # 桥型与跨径分类的常见矛盾：按 JTG B01，悬索桥、斜拉桥的主跨一般落在特大桥区间，
        # 若同时选了「中桥/小桥/涵洞」这类跨径分类，条件必然互斥，直接提示而不是静默返回空。
        if (
            not errors
            and bridge_type in {"斜拉桥", "悬索桥"}
            and span_class in {"中桥", "小桥", "涵洞"}
        ):
            errors.append({
                "field": "桥梁类型与跨径区间",
                "reason": (
                    f"条件互相矛盾：{bridge_type}主跨属于特大桥区间（单孔跨径不小于 100 米），"
                    f"不可能同时属于{span_class}，请放宽其中一项条件"
                ),
            })

        cleaned["span_min"] = span_lo
        cleaned["span_max"] = span_hi
        cleaned["year_min"] = int(year_lo) if year_lo is not None else None
        cleaned["year_max"] = int(year_hi) if year_hi is not None else None
        return cleaned, errors

    @staticmethod
    def _parse_bound(
        label: str,
        raw: Any,
        errors: list[dict[str, str]],
        *,
        minimum: float,
        maximum: float,
    ) -> float | None:
        if raw is None or str(raw).strip() == "":
            return None
        number = _to_number(raw)
        if number is None:
            errors.append({"field": label, "reason": f"「{raw}」不是有效数字，请输入数值"})
            return None
        if number < minimum or number > maximum:
            errors.append({
                "field": label,
                "reason": f"{label} {number:g} 超出允许范围（{minimum:g} ~ {maximum:g}）",
            })
        return number

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        bridge_type: str | None = None,
        span_class: str | None = None,
        span_min: float | None = None,
        span_max: float | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        sort_by: str = "桥梁编码",
        sort_order: str = "asc",
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """按多条件过滤并排序；跨径/年份缺数据的行不参与对应数值条件。"""
        rows = store.rows(MODULE)

        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("桥梁编码", "")) or keyword in str(row.get("桥梁名称", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if bridge_type:
            rows = [row for row in rows if row.get("桥梁类型") == bridge_type]

        if span_class:
            low, high = SPAN_CLASSES[span_class]
            rows = [
                row for row in rows
                if (span := _to_number(row.get("最大跨径"))) is not None
                and span >= low
                and (high == float("inf") or span < high)
            ]

        if span_min is not None:
            rows = [
                row for row in rows
                if (span := _to_number(row.get("最大跨径"))) is not None and span >= span_min
            ]
        if span_max is not None:
            rows = [
                row for row in rows
                if (span := _to_number(row.get("最大跨径"))) is not None and span <= span_max
            ]
        if year_min is not None:
            rows = [
                row for row in rows
                if (year := _to_number(row.get("建成年份"))) is not None and year >= year_min
            ]
        if year_max is not None:
            rows = [
                row for row in rows
                if (year := _to_number(row.get("建成年份"))) is not None and year <= year_max
            ]

        reverse = sort_order == "desc"
        if sort_by in {"最大跨径", "建成年份", "桥梁全长"}:
            # 数值缺失的行统一排到末尾，避免 None 参与比较。
            rows.sort(
                key=lambda row: (_to_number(row.get(sort_by)) is None, _to_number(row.get(sort_by)) or 0.0),
                reverse=reverse,
            )
        else:
            rows.sort(key=lambda row: str(row.get(sort_by, "")), reverse=reverse)

        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def filter_options(self) -> dict[str, Any]:
        """给前端的筛选面板提供候选项与跨径分类区间，避免两边各维护一份口径。"""
        return {
            "bridge_types": BRIDGE_TYPES,
            "span_classes": list(SPAN_CLASSES.keys()),
            "span_class_ranges": {
                name: (bounds[0], None if bounds[1] == float("inf") else bounds[1])
                for name, bounds in SPAN_CLASSES.items()
            },
            "statuses": STATUS_ORDER,
            "sortable_fields": SORTABLE_FIELDS,
            "year_range": [MIN_YEAR, _max_year()],
        }

    # ---- 单条明细 -------------------------------------------------------

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    # ---- 登记与状态动作（原有能力保持不变） -----------------------------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in OPTIONAL_FIELDS:
            if str(values.get(field) or "").strip():
                entry[field] = values.get(field)
        if not entry.get("桥梁状态"):
            entry["桥梁状态"] = STATUS_ORDER[0]
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
        entry["桥梁状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"桥梁设施已{action}"

    # ---- 常用筛选视图 ---------------------------------------------------

    def list_views(self) -> list[dict[str, Any]]:
        return [{"name": name, "params": dict(params)} for name, params in sorted(self._views.items())]

    def save_view(self, name: str, params: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        name = name.strip()
        if not name:
            return None, "常用视图名称不能为空"
        if len(name) > 20:
            return None, "常用视图名称最多 20 个字"
        allowed = {
            "keyword", "bridge_type", "span_class", "span_min", "span_max",
            "year_min", "year_max", "status", "sort_by", "sort_order",
        }
        clean = {key: value for key, value in params.items() if key in allowed and str(value) != ""}
        self._views[name] = clean
        return {"name": name, "params": dict(clean)}, f"已保存常用视图「{name}」"

    def delete_view(self, name: str) -> str:
        if self._views.pop(name, None) is None:
            return f"常用视图「{name}」不存在"
        return f"已删除常用视图「{name}」"
