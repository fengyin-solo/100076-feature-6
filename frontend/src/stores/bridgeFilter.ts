import { defineStore } from 'pinia'

/** 桥梁档案列表的筛选表单（草稿，点“查询”后才生效）。 */
export interface BridgeFilterForm {
  keyword: string
  bridgeType: string
  status: string
  spanMin: string
  spanMax: string
  yearMin: string
  yearMax: string
  sortBy: string
  sortOrder: 'asc' | 'desc'
}

/** 列表页状态：草稿条件、已生效条件、分页与滚动位置，整体持久化到 sessionStorage。 */
interface BridgeListState {
  draft: BridgeFilterForm
  applied: BridgeFilterForm | null
  page: number
  size: number
  scrollY: number
  focusId: number
}

const STORAGE_KEY = 'bridge-list-state'

function defaultForm(): BridgeFilterForm {
  return {
    keyword: '',
    bridgeType: '',
    status: '',
    spanMin: '',
    spanMax: '',
    yearMin: '',
    yearMax: '',
    sortBy: '桥梁编码',
    sortOrder: 'asc',
  }
}

function defaultState(): BridgeListState {
  return { draft: defaultForm(), applied: null, page: 1, size: 10, scrollY: 0, focusId: 0 }
}

function load(): BridgeListState {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultState()
    const saved = JSON.parse(raw) as Partial<BridgeListState>
    const base = defaultState()
    return {
      draft: { ...base.draft, ...(saved.draft ?? {}) },
      applied: saved.applied ? { ...defaultForm(), ...saved.applied } : null,
      page: saved.page ?? base.page,
      size: saved.size ?? base.size,
      scrollY: saved.scrollY ?? 0,
      focusId: saved.focusId ?? 0,
    }
  } catch {
    return defaultState()
  }
}

export const useBridgeFilterStore = defineStore('bridgeFilter', {
  state: (): BridgeListState => load(),
  actions: {
    persist() {
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(this.$state))
      } catch {
        // sessionStorage 不可用时退化为仅内存保留，不影响筛选本身
      }
    },
    /** 点“查询”：草稿生效并回到第一页。 */
    applyDraft() {
      this.applied = { ...this.draft }
      this.page = 1
      this.persist()
    },
    setPage(page: number) {
      this.page = page
      this.persist()
    },
    setSort(sortBy: string) {
      const base = this.applied ?? this.draft
      if (base.sortBy === sortBy) {
        base.sortOrder = base.sortOrder === 'asc' ? 'desc' : 'asc'
      } else {
        base.sortBy = sortBy
        base.sortOrder = 'asc'
      }
      this.draft = { ...base }
      this.applied = { ...base }
      this.page = 1
      this.persist()
    },
    reset() {
      this.draft = defaultForm()
      this.applied = { ...this.draft }
      this.page = 1
      this.focusId = 0
      this.persist()
    },
    /** 应用常用视图：回填表单并立即生效。 */
    applyView(form: BridgeFilterForm) {
      this.draft = { ...form }
      this.applied = { ...form }
      this.page = 1
      this.persist()
    },
    saveScroll(scrollY: number) {
      this.scrollY = scrollY
      this.persist()
    },
    setFocus(entryId: number) {
      this.focusId = entryId
      this.persist()
    },
    clearFocus() {
      this.focusId = 0
      this.persist()
    },
  },
})
