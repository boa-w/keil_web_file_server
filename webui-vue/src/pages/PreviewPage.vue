<template>
  <section class="page-block">
    <div class="topbar compact">
      <span class="meta-inline">文件: {{ previewPath || '未选择' }}</span>
      <button @click="reloadByRoute">刷新预览</button>
      <button
        class="ghost"
        :disabled="!previewPath || Boolean(vscodeOpeningPath)"
        @click="openInVSCode(previewPath)"
      >{{ vscodeOpeningPath ? '正在打开...' : '在 VS Code 中打开' }}</button>
      <button
        class="ghost"
        :disabled="!previewPath || Boolean(replacingPath)"
        @click="chooseReplacement"
      >{{ replacingPath ? '正在替换...' : '替换文件' }}</button>
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
    <input ref="replacementInput" class="visually-hidden" type="file" @change="onReplacementSelected" />
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
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
  vscodeOpeningPath,
  openInVSCode,
  replacingPath,
  replaceFile,
} from '../state'

const route = useRoute()
const replacementInput = ref(null)

function chooseReplacement() {
  if (!replacementInput.value) return
  replacementInput.value.value = ''
  replacementInput.value.click()
}

async function onReplacementSelected(event) {
  const file = event.target.files?.[0]
  if (!file || !previewPath.value) return
  const targetName = previewPath.value.split('/').pop() || previewPath.value
  if (!confirm(`确认用“${file.name}”替换“${targetName}”？此操作无法撤销。`)) return
  if (await replaceFile(previewPath.value, file)) {
    await reloadByRoute()
  }
}

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
