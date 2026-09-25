<template>
  <section class="page" data-module="bridge">
    <header class="page-head">
      <div>
        <h2>桥梁档案管理</h2>
        <p class="page-desc">按桥梁类型、跨径区间、建成年份多条件筛选与排序，可保存常用视图；点击行可定位到桥梁详情的对应段落。</p>
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

    <form class="filter-panel" @submit.prevent="reload">
      <div class="filter-grid">
        <label class="filter-item">
          <span>编码 / 名称</span>
          <input v-model="filters.keyword" placeholder="按桥梁编码或名称检索" />
        </label>
        <label class="filter-item">
          <span>桥梁类型</span>
          <select v-model="filters.bridge_type">
            <option value="">全部类型</option>
            <option v-for="item in options.bridge_types" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>跨径分类</span>
          <select v-model="filters.span_class">
            <option value="">全部分类</option>
            <option v-for="item in options.span_classes" :key="item" :value="item">
              {{ item }}（{{ spanClassHint(item) }}）
            </option>
          </select>
        </label>
        <div class="filter-item">
          <span>最大跨径区间（米）</span>
          <div class="range-inputs">
            <input v-model="filters.span_min" inputmode="decimal" placeholder="下限，如 20" />
            <i>至</i>
            <input v-model="filters.span_max" inputmode="decimal" placeholder="上限，如 100" />
          </div>
        </div>
        <div class="filter-item">
          <span>建成年份</span>
          <div class="range-inputs">
            <input v-model="filters.year_min" inputmode="numeric" :placeholder="`${yearRange[0]} 起`" />
            <i>至</i>
            <input v-model="filters.year_max" inputmode="numeric" :placeholder="`${yearRange[1]} 止`" />
          </div>
        </div>
        <label class="filter-item">
          <span>桥梁状态</span>
          <select v-model="filters.status">
            <option value="">全部状态</option>
            <option v-for="item in options.statuses" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <div class="filter-item">
          <span>排序</span>
          <div class="range-inputs">
            <select v-model="filters.sort_by">
              <option v-for="item in options.sortable_fields" :key="item" :value="item">{{ item }}</option>
            </select>
            <button class="btn sort-btn" type="button" :title="filters.sort_order === 'asc' ? '升序' : '降序'" @click="toggleSortOrder">
              {{ filters.sort_order === 'asc' ? '升序 ↑' : '降序 ↓' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="filterErrors.length" class="filter-alert" role="alert">
        <strong>筛选条件不合规，未执行查询，请修正后重试：</strong>
        <ul>
          <li v-for="(err, idx) in filterErrors" :key="idx">
            <em>{{ err.field }}</em>：{{ err.reason }}
          </li>
        </ul>
      </div>

      <div class="filter-actions">
        <button class="btn primary" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
        <span class="action-divider"></span>
        <input v-model="viewName" class="view-name-input" type="text" maxlength="20" placeholder="输入常用视图名称" />
        <button class="btn" type="button" @click="saveCurrentView">存为常用视图</button>
        <label class="view-picker">
          <span>常用视图</span>
          <select v-model="selectedView" @change="applyView(selectedView)">
            <option value="">选择已保存的视图…</option>
            <option v-for="view in savedViews" :key="view.name" :value="view.name">{{ view.name }}</option>
          </select>
        </label>
        <button v-if="selectedView" class="btn ghost danger" type="button" @click="removeSelectedView">删除该视图</button>
      </div>
      <p v-if="viewMessage" class="view-message" :class="{ error: !viewOk }">{{ viewMessage }}</p>
    </form>

    <table class="data-table bridge-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="String(row.id)"
          :class="{ 'row-active': String(activeId) === String(row.id) }"
          class="detail-row"
          :title="`查看 ${row['桥梁名称']} 档案详情`"
          @click="openDetail(row)"
        >
          <td v-for="column in columns" :key="column">{{ formatCell(column, row[column]) }}</td>
          <td class="row-actions" @click.stop>
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">当前条件下暂无桥梁档案数据，请调整筛选条件</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条桥梁档案记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onActivated, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'

defineOptions({ name: 'BridgeList' })

type Row = Record<string, string | number | null>
type FilterError = { field: string; reason: string }
type SavedView = { name: string; params: Record<string, string> }
type FilterOptions = {
  bridge_types: string[]
  span_classes: string[]
  span_class_ranges: Record<string, [number, number | null]>
  statuses: string[]
  sortable_fields: string[]
  year_range: [number, number]
}

const ENDPOINT = '/api/bridge'
const columns = ["桥梁编码", "桥梁名称", "桥梁类型", "最大跨径", "桥梁全长", "建成年份", "设计荷载", "桥梁状态"]
const actions = ["办理移交", "申请限载", "封闭桥梁"]
const stats = [{ label: "在养桥梁", value: 0 }, { label: "限载桥梁", value: 0 }, { label: "危旧桥梁", value: 0 }]

const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const activeId = ref<string | null>(null)
const errorMessage = ref('')
const filterErrors = ref<FilterError[]>([])
const savedViews = ref<SavedView[]>([])
const selectedView = ref('')
const viewName = ref('')
const viewMessage = ref('')
const viewOk = ref(true)
let savedScrollTop = 0

const options = reactive<FilterOptions>({
  bridge_types: [],
  span_classes: [],
  span_class_ranges: {},
  statuses: [],
  sortable_fields: [],
  year_range: [1900, new Date().getFullYear()],
})
const yearRange = options.year_range

// 面板字段与查询参数同名；空字符串不下发。
const filters = reactive<Record<string, string>>({
  keyword: '',
  bridge_type: '',
  span_class: '',
  span_min: '',
  span_max: '',
  year_min: '',
  year_max: '',
  status: '',
  sort_by: '桥梁编码',
  sort_order: 'asc',
})

function spanClassHint(name: string): string {
  const range = options.span_class_ranges[name]
  if (!range) return ''
  return range[1] === null ? `L ≥ ${range[0]}m` : `${range[0]}m ≤ L < ${range[1]}m`
}

function formatCell(column: string, value: string | number | null): string {
  if (value === null || value === undefined || value === '') return '—'
  if (column === '最大跨径') return `${value} m`
  if (column === '桥梁全长') return `${value} m`
  return String(value)
}

function toggleSortOrder() {
  filters.sort_order = filters.sort_order === 'asc' ? 'desc' : 'asc'
}

function buildQuery(): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== '' && value !== null && value !== undefined) params.set(key, value)
  }
  params.set('size', '100')
  return params.toString()
}

async function reload(options: { keepErrors?: boolean } | Event = {}) {
  const keepErrors = 'keepErrors' in options ? Boolean(options.keepErrors) : false
  errorMessage.value = ''
  viewMessage.value = ''
  if (!keepErrors) filterErrors.value = []
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (response.status === 400) {
      const payload = await response.json()
      const detail = payload.detail
      filterErrors.value = Array.isArray(detail?.errors) ? detail.errors : [{ field: '筛选条件', reason: detail?.message ?? '条件不合规' }]
      // 条件不合规：不给任何结果，并逐项说明哪一项不合规。
      rows.value = []
      total.value = 0
      return
    }
    if (!response.ok) throw new Error('桥梁设施列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '桥梁档案列表读取失败'
  }
}

function resetFilters() {
  Object.keys(filters).forEach((key) => {
    filters[key] = key === 'sort_by' ? '桥梁编码' : key === 'sort_order' ? 'asc' : ''
  })
  selectedView.value = ''
  filterErrors.value = []
  void reload()
}

async function loadOptions() {
  try {
    const response = await request(`${ENDPOINT}/filter-options`)
    if (!response.ok) return
    const payload = (await response.json()) as FilterOptions
    Object.assign(options, payload)
  } catch {
    // 候选项加载失败不阻塞列表，面板退化为手工输入。
  }
}

// ---- 常用视图 ---------------------------------------------------------

async function loadViews() {
  try {
    const response = await request(`${ENDPOINT}/views`)
    if (!response.ok) return
    const payload = await response.json()
    savedViews.value = payload.items ?? []
  } catch {
    savedViews.value = []
  }
}

async function saveCurrentView() {
  viewMessage.value = ''
  const name = viewName.value.trim()
  if (!name) {
    viewOk.value = false
    viewMessage.value = '请先填写常用视图名称'
    return
  }
  const params: Record<string, string> = {}
  for (const [key, value] of Object.entries(filters)) {
    if (value !== '') params[key] = value
  }
  try {
    const response = await request(`${ENDPOINT}/views`, {
      method: 'POST',
      body: JSON.stringify({ name, params }),
    })
    const payload = await response.json()
    viewOk.value = Boolean(payload.ok)
    viewMessage.value = payload.message
    if (payload.ok) {
      await loadViews()
      selectedView.value = name
    }
  } catch (error) {
    viewOk.value = false
    viewMessage.value = error instanceof Error ? error.message : '常用视图保存失败'
  }
}

async function applyView(name: string) {
  if (!name) return
  const view = savedViews.value.find((item) => item.name === name)
  if (!view) return
  Object.keys(filters).forEach((key) => {
    filters[key] = key === 'sort_by' ? '桥梁编码' : key === 'sort_order' ? 'asc' : ''
  })
  for (const [key, value] of Object.entries(view.params)) {
    filters[key] = String(value)
  }
  viewName.value = name
  filterErrors.value = []
  await reload()
}

async function removeSelectedView() {
  if (!selectedView.value) return
  try {
    await request(`${ENDPOINT}/views/${encodeURIComponent(selectedView.value)}`, { method: 'DELETE' })
    viewOk.value = true
    viewMessage.value = `已删除常用视图「${selectedView.value}」`
    selectedView.value = ''
    await loadViews()
  } catch (error) {
    viewOk.value = false
    viewMessage.value = error instanceof Error ? error.message : '常用视图删除失败'
  }
}

// ---- 详情定位 ---------------------------------------------------------

// 当前“主条件”决定进入详情后定位到哪个段落。
function focusSection(): string {
  if (filters.span_class || filters.span_min || filters.span_max) return 'span'
  if (filters.year_min || filters.year_max) return 'year'
  if (filters.bridge_type || filters.keyword) return 'basic'
  if (filters.status) return 'maintenance'
  return 'basic'
}

function openDetail(row: Row) {
  savedScrollTop = window.scrollY
  activeId.value = String(row.id)
  void router.push({ name: 'bridge-detail', params: { id: row.id }, query: { focus: focusSection() } })
}

// ---- 原有能力保持不变 -------------------------------------------------

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '桥梁设施登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) throw new Error('桥梁档案动作未生效，请稍后重试')
    await reload({ keepErrors: true })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '桥梁档案操作失败'
  }
}

onMounted(async () => {
  await loadOptions()
  await Promise.all([reload(), loadViews()])
})

// 从详情返回：keep-alive 激活时恢复上次的滚动位置与高亮行。
onActivated(() => {
  window.scrollTo({ top: savedScrollTop })
})
</script>
