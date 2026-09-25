"""桥梁档案接口：维护桥梁设施，覆盖多条件筛选、明细定位、常用视图与状态流转动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult, SavedViewPayload
from app.services.bridge import BridgeService, LIST_FIELDS

router = APIRouter(prefix="/api/bridge", tags=["桥梁档案"])

service = BridgeService()

STATUSES = ["待移交", "正常养护", "限载通行", "封闭施工"]


@router.get("/filter-options")
def filter_options() -> dict[str, Any]:
    """提供桥梁类型、跨径分类区间、状态与排序字段候选项，前后端口径保持一致。"""
    return service.filter_options()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按桥梁编码或名称检索"),
    bridge_type: str | None = Query(default=None, description="梁桥、拱桥、刚构桥、斜拉桥、悬索桥"),
    span_class: str | None = Query(default=None, description="特大桥、大桥、中桥、小桥、涵洞"),
    span_min: str | None = Query(default=None, description="最大跨径下限（米）"),
    span_max: str | None = Query(default=None, description="最大跨径上限（米）"),
    year_min: str | None = Query(default=None, description="建成年份下限"),
    year_max: str | None = Query(default=None, description="建成年份上限"),
    status: str | None = Query(default=None, description="待移交、正常养护、限载通行、封闭施工"),
    sort_by: str = Query(default="桥梁编码", description="最大跨径、建成年份、桥梁全长、桥梁编码"),
    sort_order: str = Query(default="asc", description="asc 或 desc"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按桥梁类型、跨径区间、建成年份等多条件过滤并排序。

    条件不合规（区间写反、类型与跨径互相矛盾等）时返回 400，并逐项说明不合规字段。
    """
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    cleaned, errors = service.validate_filters(
        bridge_type=bridge_type,
        span_class=span_class,
        span_min=span_min,
        span_max=span_max,
        year_min=year_min,
        year_max=year_max,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    if errors:
        raise HTTPException(status_code=400, detail={"message": "筛选条件不合规，未执行查询", "errors": errors})
    items, total = service.list_entries(
        keyword=keyword,
        status=cleaned["status"],
        bridge_type=cleaned["bridge_type"],
        span_class=cleaned["span_class"],
        span_min=cleaned["span_min"],
        span_max=cleaned["span_max"],
        year_min=cleaned["year_min"],
        year_max=cleaned["year_max"],
        sort_by=cleaned["sort_by"],
        sort_order=cleaned["sort_order"],
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/views")
def list_views() -> dict[str, Any]:
    """读取当前已保存的常用筛选视图。"""
    return {"items": service.list_views()}


@router.post("/views", response_model=ActionResult)
def save_view(payload: SavedViewPayload) -> ActionResult:
    """把当前筛选与排序条件存成常用视图；重名时覆盖原视图。"""
    view, message = service.save_view(payload.name, payload.params)
    if view is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=view)


@router.delete("/views/{name}", response_model=ActionResult)
def delete_view(name: str) -> ActionResult:
    """删除一个常用筛选视图。"""
    return ActionResult(ok=True, message=service.delete_view(name))


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出桥梁档案清单：返回全量数据（统计报表与导出照旧使用）。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "bridge", "fields": LIST_FIELDS, "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条桥梁设施明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"桥梁设施 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条桥梁设施，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="桥梁设施已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条桥梁设施执行办理移交、申请限载、封闭桥梁；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
