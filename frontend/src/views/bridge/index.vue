<template>
  <section class="page" data-module="bridge">
    <header class="page-head">
      <div>
        <h2>桥梁档案管理</h2>
        <p class="page-desc">按桥梁类型、最大跨径区间、建成年份等条件组合筛选与排序，点单元格可直达详情对应段落。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记桥梁设施</button>
        <button class="btn" type="button" @click="exportRows">导出桥梁档案清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div v-if="views.length" class="views-bar">
      <span class="views-label">常用视图：</span>
      <span v-for="view in views" :key="view.id" class="view-chip">
        <button type="button" :title="viewSummary(view.criteria)" @click="useView(view)">{{ view.name }}</button>
        <button class="view-chip-x" type="button" :title="`删除常用视图「${view.name}」`" @click="removeView(view)">×</button>
      </span>
    </div>

    <div v-if="errorBanner" class="error-banner">
      <strong>{{ errorBanner }}</strong>
      <ul v-if="fieldErrors.length">
        <li v-for="(item, index) in fieldErrors" :key="index">{{ item }}</li>
      </ul>
    </div>

    <form class="filter-grid" @submit.prevent="search">
      <label class="filter-item">
        <span>桥梁编码/名称</span>
        <input v-model="store.draft.keyword" type="text" placeholder="输入编码或名称关键字" />
      </label>
      <label class="filter-item">
        <span>桥梁类型</span>
        <select v-model="store.draft.bridgeType" :class="{ invalid: invalidFields.has('bridge_type') }">
          <option value="">全部类型</option>
          <option v-for="type in meta?.types ?? []" :key="type" :value="type">{{ type }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>桥梁状态</span>
        <select v-model="store.draft.status" :class="{ invalid: invalidFields.has('status') }">
          <option value="">全部状态</option>
          <option v-for="status in meta?.statuses ?? []" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <fieldset class="filter-group" :class="{ invalid: invalidFields.has('span_min') || invalidFields.has('span_max') }">
        <legend>最大跨径（米）</legend>
        <input v-model="store.draft.spanMin" type="text" inputmode="decimal" placeholder="下限" />
        <span class="range-sep">至</span>
        <input v-model="store.draft.spanMax" type="text" inputmode="decimal" placeholder="上限" />
      </fieldset>
      <fieldset class="filter-group" :class="{ invalid: invalidFields.has('year_min') || invalidFields.has('year_max') }">
        <legend>建成年份</legend>
        <input v-model="store.draft.yearMin" type="text" inputmode="numeric" placeholder="下限，如 2000" />
        <span class="range-sep">至</span>
        <input v-model="store.draft.yearMax" type="text" inputmode="numeric" placeholder="上限，如 2020" />
      </fieldset>
      <div class="filter-actions">
        <button class="btn primary" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
        <button class="btn ghost" type="button" @click="saveView">存为常用视图</button>
      </div>
      <p v-if="meta" class="filter-hint">
        数据范围：最大跨径 {{ meta.span.min ?? '—' }}～{{ meta.span.max ?? '—' }} 米；
        建成年份 {{ meta.year.min ?? '—' }}～{{ meta.year.max ?? '—' }} 年
      </p>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column"
            :class="{ sortable: sortableColumns.has(column), sorted: appliedSort.sortBy === column }"
            @click="sortableColumns.has(column) && toggleSort(column)"
          >
            {{ column }}
            <span v-if="appliedSort.sortBy === column" class="sort-arrow">{{ appliedSort.sortOrder === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="{ 'row-focus': row.id === store.focusId }">
          <td v-for="column in columns" :key="column">
            <button class="cell-link" type="button" @click="openDetail(row, column)">
              {{ row[column] ?? '—' }}
            </button>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click.stop="runAction('办理移交', row)">办理移交</button>
            <button class="link" type="button" @click.stop="runAction('申请限载', row)">申请限载</button>
            <button class="link" type="button" @click.stop="runAction('封闭桥梁', row)">封闭桥梁</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            {{ fieldErrors.length ? '筛选条件不合规，未给出结果，请按上方提示修正' : '没有符合条件的桥梁档案，可调整条件或先登记桥梁设施' }}
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot list-foot">
      <span>共 {{ total }} 条桥梁档案记录，第 {{ store.page }} / {{ totalPages }} 页</span>
      <span class="pager">
        <button class="btn" type="button" :disabled="store.page <= 1" @click="goPage(store.page - 1)">上一页</button>
        <button class="btn" type="button" :disabled="store.page >= totalPages" @click="goPage(store.page + 1)">下一页</button>
      </span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useBridgeFilterStore, type BridgeFilterForm } from '@/stores/bridgeFilter'

type Row = Record<string, string | number | boolean | null>

interface Meta {
  types: string[]
  statuses: string[]
  sortable_fields: string[]
  span: { min: number | null; max: number | null; unit: string }
  year: { min: number | null; max: number | null }
}

interface SavedView {
  id: number
  name: string
  criteria: Record<string, string>
}

interface FieldError {
  field: string
  message: string
}

const ENDPOINT = '/api/bridge'
const columns = ['桥梁编码', '桥梁名称', '桥梁类型', '跨越对象', '桥梁全长', '最大跨径', '设计荷载', '建成年份']
const sortableColumns = new Set(['桥梁编码', '桥梁名称', '桥梁类型', '桥梁全长', '最大跨径', '建成年份'])
// 列表字段 -> 详情段落锚点：点哪一列就滚到详情的对应段落
const fieldAnchors: Record<string, string> = {
  桥梁编码: 'basic',
  桥梁名称: 'basic',
  桥梁类型: 'basic',
  跨越对象: 'basic',
  桥梁全长: 'structure',
  最大跨径: 'structure',
  设计荷载: 'structure',
  建成年份: 'build',
}

const router = useRouter()
const store = useBridgeFilterStore()

const stats = [{ label: '在养桥梁', value: 0 }, { label: '限载桥梁', value: 0 }, { label: '危旧桥梁', value: 0 }]

const rows = ref<Row[]>([])
const total = ref(0)
const meta = ref<Meta | null>(null)
const views = ref<SavedView[]>([])
const errorBanner = ref('')
const fieldErrors = ref<string[]>([])
const invalidFields = ref<Set<string>>(new Set())

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / store.size)))
const appliedSort = computed(() => store.applied ?? store.draft)

function formToParams(form: BridgeFilterForm, withPage: boolean): Record<string, string> {
  const params: Record<string, string> = {
    sort_by: form.sortBy,
    sort_order: form.sortOrder,
  }
  if (form.keyword.trim()) params.keyword = form.keyword.trim()
  if (form.bridgeType) params.bridge_type = form.bridgeType
  if (form.status) params.status = form.status
  if (form.spanMin.trim()) params.span_min = form.spanMin.trim()
  if (form.spanMax.trim()) params.span_max = form.spanMax.trim()
  if (form.yearMin.trim()) params.year_min = form.yearMin.trim()
  if (form.yearMax.trim()) params.year_max = form.yearMax.trim()
  if (withPage) {
    params.page = String(store.page)
    params.size = String(store.size)
  }
  return params
}

function paramsToForm(criteria: Record<string, string>): BridgeFilterForm {
  return {
    keyword: criteria.keyword ?? '',
    bridgeType: criteria.bridge_type ?? '',
    status: criteria.status ?? '',
    spanMin: criteria.span_min ?? '',
    spanMax: criteria.span_max ?? '',
    yearMin: criteria.year_min ?? '',
    yearMax: criteria.year_max ?? '',
    sortBy: criteria.sort_by ?? '桥梁编码',
    sortOrder: criteria.sort_order === 'desc' ? 'desc' : 'asc',
  }
}

async function reload() {
  errorBanner.value = ''
  fieldErrors.value = []
  invalidFields.value = new Set()
  const query = new URLSearchParams(formToParams(store.applied ?? store.draft, true)).toString()
  let response: Response
  try {
    response = await request(`${ENDPOINT}?${query}`)
  } catch (error) {
    errorBanner.value = error instanceof Error ? error.message : '桥梁档案列表读取失败'
    return
  }
  if (response.status === 400) {
    const detail = (await response.json())?.detail
    const errors: FieldError[] = Array.isArray(detail?.errors) ? detail.errors : []
    errorBanner.value = detail?.message ?? '筛选条件不合规，未执行查询'
    fieldErrors.value = errors.map((item) => `【${fieldLabel(item.field)}】${item.message}`)
    invalidFields.value = new Set(errors.map((item) => item.field))
    rows.value = []
    total.value = 0
    return
  }
  if (!response.ok) {
    errorBanner.value = '桥梁设施列表读取失败'
    return
  }
  const payload = await response.json()
  rows.value = payload.items ?? []
  total.value = payload.total ?? rows.value.length
  if (store.page > totalPages.value) {
    store.setPage(totalPages.value)
    await reload()
  }
}

function fieldLabel(field: string): string {
  const labels: Record<string, string> = {
    keyword: '关键字',
    bridge_type: '桥梁类型',
    status: '桥梁状态',
    span_min: '跨径下限',
    span_max: '跨径上限',
    year_min: '年份下限',
    year_max: '年份上限',
    sort_by: '排序字段',
    sort_order: '排序方向',
    page: '页码',
    size: '每页条数',
  }
  return labels[field] ?? field
}

async function loadMeta() {
  try {
    const response = await request(`${ENDPOINT}/meta`)
    if (response.ok) meta.value = await response.json()
  } catch {
    // 元数据拉不到时下拉框退化为空选项，不阻塞列表
  }
}

async function loadViews() {
  try {
    const response = await request(`${ENDPOINT}/views`)
    if (response.ok) views.value = (await response.json()).items ?? []
  } catch {
    views.value = []
  }
}

function search() {
  store.applyDraft()
  void reload()
}

function resetFilters() {
  store.reset()
  void reload()
}

async function toggleSort(column: string) {
  store.setSort(column)
  await reload()
}

async function goPage(page: number) {
  store.setPage(page)
  await reload()
  window.scrollTo({ top: 0 })
}

async function saveView() {
  const name = window.prompt('为当前筛选条件起个常用视图名称：')
  if (name === null) return
  const trimmed = name.trim()
  if (!trimmed) {
    errorBanner.value = '常用视图名称不能为空'
    return
  }
  // 视图保存的是“当前已生效”的条件；尚未点查询时先按草稿生效
  const criteria = formToParams(store.applied ?? store.draft, false)
  try {
    const response = await request(`${ENDPOINT}/views`, {
      method: 'POST',
      body: JSON.stringify({ name: trimmed, criteria }),
    })
    const payload = await response.json()
    if (!response.ok) {
      const errors: FieldError[] = Array.isArray(payload?.detail?.errors) ? payload.detail.errors : []
      errorBanner.value = errors.length ? payload.detail.message : (payload?.message ?? '常用视图保存失败')
      fieldErrors.value = errors.map((item) => `【${fieldLabel(item.field)}】${item.message}`)
      return
    }
    await loadViews()
  } catch (error) {
    errorBanner.value = error instanceof Error ? error.message : '常用视图保存失败'
  }
}

async function useView(view: SavedView) {
  store.applyView(paramsToForm(view.criteria))
  await reload()
  window.scrollTo({ top: 0 })
}

async function removeView(view: SavedView) {
  if (!window.confirm(`确定删除常用视图「${view.name}」吗？`)) return
  try {
    await request(`${ENDPOINT}/views/${view.id}`, { method: 'DELETE' })
    await loadViews()
  } catch (error) {
    errorBanner.value = error instanceof Error ? error.message : '常用视图删除失败'
  }
}

function viewSummary(criteria: Record<string, string>): string {
  return Object.entries(criteria)
    .map(([key, value]) => `${fieldLabel(key)}：${value}`)
    .join('；')
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorBanner.value = '桥梁设施登记入口尚未接入审批流'
}

function openDetail(row: Row, column: string) {
  const anchor = fieldAnchors[column]
  const entryId = Number(row.id)
  store.saveScroll(window.scrollY)
  store.setFocus(entryId)
  void router.push({ name: 'bridge-detail', params: { id: entryId }, hash: anchor ? `#${anchor}` : '' })
}

async function runAction(action: string, row: Row) {
  errorBanner.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('桥梁档案动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorBanner.value = error instanceof Error ? error.message : '桥梁档案操作失败'
  }
}

onMounted(async () => {
  if (!store.applied) store.applied = { ...store.draft }
  await Promise.all([loadMeta(), loadViews(), reload()])
  // 从详情返回时恢复上次的滚动位置与定位高亮
  window.scrollTo({ top: store.scrollY })
  if (store.focusId) {
    window.setTimeout(() => store.clearFocus(), 3000)
  }
})
</script>

<style scoped>
.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.filter-item span,
.filter-group legend {
  display: block;
  font-size: 12px;
  color: var(--muted);
  padding: 0 2px;
}
.filter-item input,
.filter-item select,
.filter-group input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  margin-top: 4px;
}
.filter-group {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 8px 8px;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}
.filter-group legend { font-size: 11px; }
.filter-group input { margin-top: 0; }
.range-sep { color: var(--muted); font-size: 12px; }
.invalid :deep(input),
.invalid :deep(select),
select.invalid {
  border-color: #b42318;
  background: #fff5f4;
}
.filter-actions {
  grid-column: 1 / -1;
  display: flex;
  gap: 8px;
}
.filter-hint {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.error-banner {
  background: #fef3f2;
  border: 1px solid #f0a9a2;
  color: #7a271a;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  margin-bottom: 12px;
}
.error-banner ul { margin: 6px 0 0; padding-left: 18px; }
.views-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
}
.views-label { color: var(--muted); }
.view-chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 999px;
  font-size: 12px;
  overflow: hidden;
}
.view-chip > button {
  border: none;
  background: none;
  padding: 3px 10px;
  cursor: pointer;
}
.view-chip > button:first-child:hover { color: var(--brand); }
.view-chip-x { color: var(--muted); }
.view-chip-x:hover { color: #b42318; }
th.sortable { cursor: pointer; user-select: none; white-space: nowrap; }
th.sortable:hover { color: var(--brand); }
th.sorted { color: var(--brand); }
.sort-arrow { font-size: 10px; margin-left: 2px; }
.cell-link {
  border: none;
  background: none;
  padding: 0;
  color: var(--brand);
  cursor: pointer;
  font-size: 13px;
  text-align: left;
}
.cell-link:hover { text-decoration: underline; }
tr.row-focus > td { background: #fff7d6; }
.list-foot { align-items: center; }
.pager { display: flex; gap: 8px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
