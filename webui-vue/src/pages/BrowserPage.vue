<template>
  <section>
    <div class="topbar">
      <input type="text" v-model="rootInput" placeholder="输入目录绝对路径，例如 D:\\project\\fw" @keyup.enter="onSetRoot" />
      <button @click="onSetRoot">设置路径</button>
      <button class="ghost" @click="goUp">返回上级</button>
      <button @click="refresh">刷新</button>
    </div>

    <div class="topbar compact">
      <label class="meta-inline">
        排序
        <select v-model="sort" @change="onSortChange">
          <option value="name_asc">名称 A-Z</option>
          <option value="name_desc">名称 Z-A</option>
          <option value="size_asc">大小 小-大</option>
          <option value="size_desc">大小 大-小</option>
        </select>
      </label>
      <label class="meta-inline">
        每页
        <select v-model.number="pageSize" @change="onPageSizeChange">
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="500">500</option>
        </select>
      </label>
      <span class="meta-inline">总计 {{ total }} 项</span>
    </div>

    <div class="topbar compact selection-toolbar">
      <label class="meta-inline">
        <input
          type="checkbox"
          :checked="allCurrentFilesSelected"
          :disabled="!selectableItems.length"
          @change="toggleAllCurrentFiles($event.target.checked)"
        />
        本页全选
      </label>
      <span class="meta-inline">已选 {{ selectedCount }} 个文件</span>
      <button :disabled="!selectedCount || batchDownloading" @click="downloadSelectedFiles">
        {{ batchDownloading ? '正在打包...' : '下载所选' }}
      </button>
      <button class="ghost" :disabled="!selectedCount" @click="clearSelection">取消选择</button>
    </div>

    <p class="meta">当前: /{{ current || '' }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="select-column">选择</th><th>名称</th><th>类型</th><th>大小</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in items"
            :key="item.rel || item.name"
            :class="{ selected: selectedPaths.has(item.rel) }"
          >
            <td class="select-column">
              <input
                v-if="!item.is_dir"
                type="checkbox"
                :checked="selectedPaths.has(item.rel)"
                :aria-label="`选择 ${item.name}`"
                @change="toggleFile(item.rel, $event.target.checked)"
              />
            </td>
            <td>
              <a v-if="item.is_dir" href="#" @click.prevent="openDir(item.rel)">{{ item.name }}/</a>
              <a v-else href="#" @click.prevent="openPreview(item.rel)">{{ item.name }}</a>
            </td>
            <td>{{ item.is_dir ? '目录' : '文件' }}</td>
            <td>{{ item.is_dir ? '-' : item.size }}</td>
            <td>
              <template v-if="item.is_dir">
                <button class="mini" @click="createZipTask(item.rel)">异步打包</button>
                <a :href="`/api/download-folder?path=${encodeURIComponent(item.rel)}`" target="_blank">立即打包下载</a>
              </template>
              <template v-else>
                <button class="mini" @click="openPreview(item.rel)">预览</button>
                <button
                  class="mini ghost"
                  :disabled="Boolean(vscodeOpeningPath)"
                  @click="openInVSCode(item.rel)"
                >{{ vscodeOpeningPath === item.rel ? '正在打开...' : 'VS Code' }}</button>
                <button
                  class="mini ghost"
                  :disabled="Boolean(replacingPath)"
                  @click="chooseReplacement(item.rel)"
                >{{ replacingPath === item.rel ? '正在替换...' : '替换' }}</button>
                <a :href="`/api/download?path=${encodeURIComponent(item.rel)}`" target="_blank">下载</a>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pager">
      <button class="ghost" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页</span>
      <button class="ghost" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
    </div>

    <input ref="replacementInput" class="visually-hidden" type="file" @change="onReplacementSelected" />
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  rootInput,
  current,
  items,
  page,
  pageSize,
  total,
  totalPages,
  sort,
  list,
  setRoot,
  createZipTask,
  vscodeOpeningPath,
  openInVSCode,
  batchDownloading,
  downloadSelected,
  replacingPath,
  replaceFile,
} from '../state'

const router = useRouter()
const selectedPaths = ref(new Set())
const replacementInput = ref(null)
const replacementTarget = ref('')

const selectableItems = computed(() => items.value.filter((item) => !item.is_dir))
const selectedCount = computed(() => selectedPaths.value.size)
const allCurrentFilesSelected = computed(() => (
  selectableItems.value.length > 0
  && selectableItems.value.every((item) => selectedPaths.value.has(item.rel))
))

function toggleFile(path, checked) {
  const next = new Set(selectedPaths.value)
  if (checked) next.add(path)
  else next.delete(path)
  selectedPaths.value = next
}

function toggleAllCurrentFiles(checked) {
  const next = new Set(selectedPaths.value)
  for (const item of selectableItems.value) {
    if (checked) next.add(item.rel)
    else next.delete(item.rel)
  }
  selectedPaths.value = next
}

function clearSelection() {
  selectedPaths.value = new Set()
}

async function downloadSelectedFiles() {
  await downloadSelected([...selectedPaths.value])
}

function chooseReplacement(path) {
  replacementTarget.value = path
  if (replacementInput.value) {
    replacementInput.value.value = ''
    replacementInput.value.click()
  }
}

async function onReplacementSelected(event) {
  const file = event.target.files?.[0]
  const target = replacementTarget.value
  if (!file || !target) return
  const targetName = target.split('/').pop() || target
  if (!confirm(`确认用“${file.name}”替换“${targetName}”？此操作无法撤销。`)) return
  if (await replaceFile(target, file)) {
    await list(current.value)
  }
}

async function openPreview(path) {
  await router.push({ name: 'preview', query: { path } })
}

function openDir(path) {
  list(path, true)
}

function goUp() {
  if (!current.value) return
  const parts = current.value.split('/').filter(Boolean)
  parts.pop()
  list(parts.join('/'), true)
}

function refresh() {
  list(current.value)
}

function changePage(next) {
  if (next < 1 || next > totalPages.value) return
  page.value = next
  list(current.value)
}

function onSortChange() {
  list(current.value, true)
}

function onPageSizeChange() {
  list(current.value, true)
}

async function onSetRoot() {
  await setRoot()
}

onMounted(async () => {
  if (!items.value.length) {
    await list('', true)
  }
})

watch(() => [current.value, page.value], clearSelection)
</script>
