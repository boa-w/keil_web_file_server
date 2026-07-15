<template>
  <main class="layout">
    <section class="card">
      <div class="app-heading">
        <h1>File Manager</h1>
        <span v-if="appVersion" class="version-badge">v{{ appVersion }}</span>
      </div>
      <p class="meta">根目录: {{ root }}</p>

      <nav class="topbar nav-bar">
        <router-link class="link-btn" to="/browser">文件浏览</router-link>
        <router-link class="link-btn" to="/preview">文件预览</router-link>
        <router-link class="link-btn" to="/tasks">任务队列</router-link>
        <router-link class="link-btn" to="/debug">调试页面</router-link>
      </nav>

      <router-view />
    </section>
  </main>
</template>

<script setup>
import { onMounted } from 'vue'
import { appVersion, loadVersion, root } from './state'

onMounted(loadVersion)
</script>
