<template>
  <section class="page bridge-detail" data-module="bridge-detail">
    <header class="page-head detail-head">
      <div>
        <h2>桥梁设施详情</h2>
        <p class="page-desc">从桥梁档案列表点单元格进入时，会自动定位到对应的信息段落。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="backToList">返回档案列表</button>
      </div>
    </header>

    <div v-if="errorMessage" class="error-banner">{{ errorMessage }}</div>

    <template v-else-if="entry">
      <div class="detail-title-row">
        <h3>{{ entry['桥梁名称'] }}</h3>
        <span class="status-tag">{{ entry['桥梁状态'] }}</span>
        <span class="code-tag">{{ entry['桥梁编码'] }}</span>
      </div>

      <nav class="anchor-nav">
        <a v-for="section in entry.sections" :key="section.anchor" :href="`#${section.anchor}`">
          {{ section.title }}
        </a>
      </nav>

      <section
        v-for="section in entry.sections"
        :id="section.anchor"
        :key="section.anchor"
        class="detail-section"
        :class="{ 'section-focus': section.anchor === activeAnchor }"
      >
        <h4>{{ section.title }}</h4>
        <dl class="detail-grid">
          <div v-for="field in section.fields" :key="field.name" class="detail-item">
            <dt>{{ field.name }}</dt>
            <dd>{{ field.value }}</dd>
          </div>
        </dl>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useBridgeFilterStore } from '@/stores/bridgeFilter'

interface DetailField {
  name: string
  value: string
}

interface DetailSection {
  anchor: string
  title: string
  fields: DetailField[]
}

interface DetailEntry {
  id: number
  sections: DetailSection[]
  [key: string]: string | number | boolean | null | DetailSection[]
}

const route = useRoute()
const router = useRouter()
const listStore = useBridgeFilterStore()

const entry = ref<DetailEntry | null>(null)
const errorMessage = ref('')
const activeAnchor = ref('')

async function loadDetail() {
  errorMessage.value = ''
  try {
    const response = await request(`/api/bridge/${route.params.id}`)
    if (response.status === 404) {
      errorMessage.value = '该桥梁设施不存在或已归档，请返回列表重新选择。'
      return
    }
    if (!response.ok) throw new Error('桥梁详情读取失败')
    entry.value = await response.json()
    locateAnchor()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '桥梁详情读取失败'
  }
}

function locateAnchor() {
  const anchor = String(route.hash ?? '').replace(/^#/, '')
  if (!anchor) return
  activeAnchor.value = anchor
  // 等段落渲染后再滚动到对应段落
  window.requestAnimationFrame(() => {
    document.getElementById(anchor)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    window.setTimeout(() => {
      if (activeAnchor.value === anchor) activeAnchor.value = ''
    }, 2600)
  })
}

function backToList() {
  void router.push({ name: 'bridge' })
}

// 详情页内部滚动不影响列表保留的位置；只有点进详情前记录的那次位置会被恢复
onBeforeRouteLeave((to) => {
  if (to.name === 'bridge') {
    listStore.persist()
  }
})

onMounted(loadDetail)
</script>

<style scoped>
.detail-head { margin-bottom: 8px; }
.detail-title-row { display: flex; align-items: center; gap: 10px; margin: 8px 0; }
.detail-title-row h3 { margin: 0; font-size: 18px; }
.status-tag {
  background: #eef4ff;
  border: 1px solid #b8d0fa;
  color: #1f4fa8;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
}
.code-tag { color: var(--muted); font-size: 13px; }
.anchor-nav {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  gap: 14px;
  background: #f6f8fb;
  padding: 8px 2px;
  font-size: 13px;
}
.anchor-nav a { color: var(--brand); text-decoration: none; }
.anchor-nav a:hover { text-decoration: underline; }
.detail-section {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
  scroll-margin-top: 46px;
  transition: box-shadow 0.3s, border-color 0.3s;
}
.detail-section h4 { margin: 0 0 10px; font-size: 15px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
.detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px 18px; margin: 0; }
.detail-item { margin: 0; }
.detail-item dt { font-size: 12px; color: var(--muted); }
.detail-item dd { margin: 2px 0 0; font-size: 14px; }
.section-focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(31, 111, 235, 0.18);
}
.error-banner {
  background: #fef3f2;
  border: 1px solid #f0a9a2;
  color: #7a271a;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
}
</style>
