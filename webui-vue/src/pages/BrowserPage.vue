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

    <p class="meta">当前: /{{ current || '' }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>名称</th><th>类型</th><th>大小</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.rel || item.name">
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
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
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
} from '../state'

const router = useRouter()

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
</script>
