"""桥梁档案接口：维护桥梁设施，覆盖多条件筛选/排序、详情锚点、常用视图与状态流转。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.bridge import BridgeService

router = APIRouter(prefix="/api/bridge", tags=["桥梁档案"])

service = BridgeService()

STATUSES = ["待移交", "正常养护", "限载通行", "封闭施工"]


class ViewPayload(BaseModel):
    """保存常用视图时提交的名称与筛选条件。"""

    name: str = ""
    criteria: dict[str, Any] = Field(default_factory=dict)


def _raise_filter_errors(errors: list[dict[str, str]]) -> None:
    """条件不合规时统一返回 400，并逐项说明是哪一项不合规。"""
    raise HTTPException(
        status_code=400,
        detail={
            "message": "筛选条件不合规，未执行查询，请按提示修正后重试",
            "errors": errors,
        },
    )


@router.get("/meta")
def list_meta() -> dict[str, Any]:
    """筛选项元数据：桥梁类型、状态、可排序字段与跨径/年份取值范围。"""
    return service.metadata()


# 注意：/export 必须在 /{entry_id} 之前注册，否则会被当成 entry_id="export" 匹配掉
@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出桥梁档案清单：按原约定导出全量数据，不受筛选条件影响。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "bridge", "total": total, "items": items}


@router.get("/views")
def list_views() -> dict[str, Any]:
    """查看已保存的常用视图。"""
    return {"items": service.list_views()}


@router.post("/views", response_model=ActionResult)
def create_view(payload: ViewPayload) -> ActionResult:
    """把当前筛选条件存为常用视图；名称重复或条件不合规则拒绝并说明原因。"""
    view, message, errors = service.create_view({"name": payload.name, "criteria": payload.criteria})
    if errors:
        _raise_filter_errors(errors)
    if view is None:
        return ActionResult(ok=False, message=message or "常用视图保存失败")
    return ActionResult(ok=True, message=f"常用视图「{view['name']}」已保存", entry=view)


@router.delete("/views/{view_id}", response_model=ActionResult)
def delete_view(view_id: int) -> ActionResult:
    """删除一个常用视图；不存在时给出可读说明。"""
    if not service.delete_view(view_id):
        return ActionResult(ok=False, message=f"常用视图 {view_id} 不存在或已删除")
    return ActionResult(ok=True, message="常用视图已删除")


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按桥梁编码或名称检索"),
    bridge_type: str | None = Query(default=None, description="桥梁类型，取值见 /api/bridge/meta"),
    status: str | None = Query(default=None, description="待移交、正常养护、限载通行、封闭施工"),
    span_min: str | None = Query(default=None, description="最大跨径下限（米，含）"),
    span_max: str | None = Query(default=None, description="最大跨径上限（米，含）"),
    year_min: str | None = Query(default=None, description="建成年份下限（含）"),
    year_max: str | None = Query(default=None, description="建成年份上限（含）"),
    sort_by: str | None = Query(default=None, description="排序字段，可选范围见 /api/bridge/meta"),
    sort_order: str = Query(default="asc", description="asc 升序 / desc 降序"),
    page: str = "1",
    size: str = "20",
) -> PageResult[dict]:
    """多条件筛选与排序：条件矛盾或不合法时返回 400 并逐项说明，不返回静默空结果。"""
    params = {
        "keyword": keyword,
        "bridge_type": bridge_type,
        "status": status,
        "span_min": span_min,
        "span_max": span_max,
        "year_min": year_min,
        "year_max": year_max,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "page": page,
        "size": size,
    }
    clean, errors = service.validate_filters(params)
    if errors:
        _raise_filter_errors(errors)
    items, total = service.list_entries(clean=clean)
    return PageResult(items=items, total=total, page=clean["page"], size=clean["size"])


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条桥梁设施明细（含段落分组）；不存在时给出可读的错误说明。"""
    entry = service.detail(entry_id)
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
