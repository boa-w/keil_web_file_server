<template>
  <section class="page-block tasks">
    <div class="topbar compact">
      <h2>打包任务队列</h2>
      <button @click="loadTasks">刷新任务</button>
    </div>
    <table>
      <thead>
        <tr><th>ID</th><th>目录</th><th>状态</th><th>文件数</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="t in tasks" :key="t.id">
          <td class="mono">{{ t.id.slice(0, 8) }}</td>
          <td>{{ t.name }}</td>
          <td>{{ statusText(t.status) }}</td>
          <td>{{ t.file_count || 0 }}</td>
          <td>
            <a v-if="t.status === 'done'" :href="`/api/tasks/${t.id}/download`" target="_blank">下载 ZIP</a>
            <span v-else-if="t.status === 'failed'" class="err">{{ t.error || '失败' }}</span>
            <span v-else>处理中...</span>
            <button class="mini ghost" :disabled="t.status === 'running' || t.status === 'pending'" @click="removeTask(t)">删除</button>
          </td>
        </tr>
        <tr v-if="tasks.length === 0"><td colspan="5" class="meta">暂无任务</td></tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { tasks, loadTasks, removeTask, statusText } from '../state'

let timer = null

onMounted(async () => {
  await loadTasks()
  timer = setInterval(() => {
    loadTasks()
  }, 1500)
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>
