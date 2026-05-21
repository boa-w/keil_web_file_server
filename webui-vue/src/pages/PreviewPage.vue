<template>
  <section class="page-block">
    <div class="topbar compact">
      <span class="meta-inline">文件: {{ previewPath || '未选择' }}</span>
      <button @click="reloadByRoute">刷新预览</button>
      <router-link class="link-btn" to="/browser">返回浏览</router-link>
    </div>

    <p class="meta">
      预览类型: {{ previewKind }} | MIME: {{ previewMime || '-' }} | 编码: {{ previewEncoding || '-' }} | 大小: {{ previewSize || '-' }}
    </p>
    <div class="preview-panel">
      <img v-if="previewKind === 'image'" :src="previewUrl" alt="image preview" class="media-preview" />
      <iframe v-else-if="previewKind === 'pdf'" :src="previewUrl" class="pdf-preview"></iframe>
      <pre v-else>{{ previewText }}</pre>
    </div>
  </section>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  previewPath,
  previewText,
  previewKind,
  previewMime,
  previewEncoding,
  previewSize,
  previewUrl,
  loadPreview,
} from '../state'

const route = useRoute()

async function reloadByRoute() {
  const path = String(route.query.path || '')
  if (!path) {
    previewText.value = '请从文件浏览页选择文件进行预览。'
    return
  }
  await loadPreview(path)
}

watch(() => route.query.path, () => {
  reloadByRoute()
})

onMounted(() => {
  reloadByRoute()
})
</script>
