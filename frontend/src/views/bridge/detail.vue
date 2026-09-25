<template>
  <section class="page bridge-detail">
    <header class="page-head">
      <div>
        <h2>{{ entry['桥梁名称'] || '桥梁档案详情' }}</h2>
        <p class="page-desc">桥梁编码：{{ entry['桥梁编码'] || '—' }} · 从列表带来的筛选条件与位置已保留，返回即可继续查看。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回桥梁列表</button>
      </div>
    </header>

    <div v-if="notFound" class="filter-alert" role="alert">
      <strong>未找到该桥梁档案：</strong>{{ errorMessage }}
    </div>

    <template v-else-if="loaded">
      <nav class="detail-anchors">
        <a
          v-for="section in sections"
          :key="section.key"
          :class="{ active: focus === section.key }"
          href="javascript:void(0)"
          @click="focusSection(section.key)"
        >
          {{ section.title }}
        </a>
      </nav>

      <article
        v-for="section in sections"
        :id="`section-${section.key}`"
        :key="section.key"
        class="detail-section"
        :class="{ focused: focus === section.key }"
      >
        <header class="detail-section-head">
          <h3>{{ section.title }}</h3>
          <span v-if="section.badge" class="section-badge">{{ section.badge }}</span>
        </header>
        <dl class="detail-grid">
          <div v-for="field in section.fields" :key="field.key" :class="{ 'field-hit': focus === section.key && field.key === focusField }">
            <dt>{{ field.label }}</dt>
            <dd>{{ formatValue(field.key, entry[field.key]) }}</dd>
          </div>
        </dl>
      </article>
    </template>

    <footer v-else class="page-foot">
      <span>正在读取桥梁档案…</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Entry = Record<string, string | number | null>

type SectionField = { key: string; label: string }
type Section = { key: string; title: string; badge?: string; fields: SectionField[] }

// 详情按四个段落组织：基本信息、跨径参数、建设信息、管养状态。
const sections: Section[] = [
  {
    key: 'basic',
    title: '一、基本信息',
    fields: [
      { key: '桥梁编码', label: '桥梁编码' },
      { key: '桥梁名称', label: '桥梁名称' },
      { key: '桥梁类型', label: '桥梁类型' },
      { key: '跨越对象', label: '跨越对象' },
    ],
  },
  {
    key: 'span',
    title: '二、跨径参数',
    badge: '按跨径区间筛选时定位到此段',
    fields: [
      { key: '最大跨径', label: '单孔最大跨径' },
      { key: '桥梁全长', label: '桥梁全长' },
      { key: '设计荷载', label: '设计荷载' },
    ],
  },
  {
    key: 'year',
    title: '三、建设信息',
    badge: '按建成年份筛选时定位到此段',
    fields: [
      { key: '建成年份', label: '建成年份' },
      { key: '桥梁类型', label: '结构形式' },
      { key: '跨越对象', label: '跨越地物' },
    ],
  },
  {
    key: 'maintenance',
    title: '四、管养状态',
    fields: [
      { key: '桥梁状态', label: '当前状态' },
      { key: 'id', label: '档案内部编号' },
    ],
  },
]

const FOCUS_FIELD: Record<string, string> = {
  basic: '桥梁类型',
  span: '最大跨径',
  year: '建成年份',
  maintenance: '桥梁状态',
}

const route = useRoute()
const router = useRouter()

const entry = ref<Entry>({})
const loaded = ref(false)
const notFound = ref(false)
const errorMessage = ref('')
const focus = ref<string>('basic')
const focusField = ref<string>('桥梁类型')

function formatValue(key: string, value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  if (key === '最大跨径' || key === '桥梁全长') return `${value} 米`
  return String(value)
}

function focusSection(key: string) {
  focus.value = key
  focusField.value = FOCUS_FIELD[key] ?? ''
  void nextTick(() => {
    document.getElementById(`section-${key}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function goBack() {
  // 回到列表路由；列表组件被 keep-alive 缓存，筛选条件、结果与滚动位置原样保留。
  void router.push({ name: 'bridge' })
}

onMounted(async () => {
  const rawFocus = typeof route.query.focus === 'string' ? route.query.focus : 'basic'
  if (sections.some((item) => item.key === rawFocus)) {
    focus.value = rawFocus
    focusField.value = FOCUS_FIELD[rawFocus] ?? ''
  }
  const id = String(route.params.id ?? '')
  try {
    const response = await request(`/api/bridge/${id}`)
    if (response.status === 404) {
      const payload = await response.json().catch(() => null)
      errorMessage.value = payload?.detail ?? `桥梁设施 ${id} 不存在`
      notFound.value = true
      loaded.value = true
      return
    }
    if (!response.ok) throw new Error('桥梁详情读取失败')
    entry.value = await response.json()
    loaded.value = true
    // 等段落渲染完再滚动定位到筛选条件对应的段落。
    await nextTick()
    focusSection(focus.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '桥梁详情读取失败'
    loaded.value = true
  }
})
</script>
