<template>
  <section class="page-block tasks">
    <h2>调试上下文（Keil 对比）</h2>

    <div class="topbar compact">
      <label class="meta-inline">
        <input type="checkbox" v-model="debugIncludeAllEnv" />
        包含更多环境变量
      </label>
      <button @click="loadDebugContext">刷新上下文</button>
    </div>
    <pre>{{ debugText }}</pre>

    <h2>进程链路</h2>
    <div class="topbar compact">
      <button @click="loadProcessTree">刷新进程链</button>
    </div>
    <pre>{{ processTreeText }}</pre>

    <h2>已加载模块（DLL）</h2>
    <div class="topbar compact">
      <label class="meta-inline">
        关键字
        <input type="text" v-model="moduleKeyword" placeholder="如 keil / arm / crypt" />
      </label>
      <label class="meta-inline">
        数量
        <input type="text" v-model="moduleLimit" placeholder="400" />
      </label>
      <button @click="loadModules">刷新模块</button>
    </div>
    <pre>{{ modulesText }}</pre>

    <h2>文件读探针</h2>
    <div class="topbar compact">
      <label class="meta-inline path-input">
        相对路径
        <input type="text" v-model="probePath" placeholder="例如 JK_SmartProduct_CanAnalysis/SRC/xxx.c" />
      </label>
      <label class="meta-inline">
        头字节
        <input type="text" v-model="probeHead" />
      </label>
      <label class="meta-inline">
        尾字节
        <input type="text" v-model="probeTail" />
      </label>
      <label class="meta-inline">
        <input type="checkbox" v-model="probeHashFull" />
        全量哈希
      </label>
      <button @click="runFileProbe">执行探针</button>
    </div>
    <pre>{{ probeText }}</pre>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { debugIncludeAllEnv, debugText, loadDebugContext } from '../state'

const processTreeText = ref('点击“刷新进程链”查看父进程链路...')
const modulesText = ref('点击“刷新模块”查看已加载模块...')
const probeText = ref('输入相对路径后执行文件读探针。')

const moduleKeyword = ref('')
const moduleLimit = ref('400')

const probePath = ref('')
const probeHead = ref('128')
const probeTail = ref('128')
const probeHashFull = ref(false)

async function loadProcessTree() {
  const res = await fetch('/api/debug/process-tree')
  const data = await res.json()
  processTreeText.value = JSON.stringify(data, null, 2)
}

async function loadModules() {
  const limit = Number.parseInt(moduleLimit.value || '400', 10)
  const params = new URLSearchParams({
    limit: String(Number.isFinite(limit) ? Math.max(1, Math.min(2000, limit)) : 400),
    keyword: moduleKeyword.value || '',
  })
  const res = await fetch(`/api/debug/modules?${params.toString()}`)
  const data = await res.json()
  modulesText.value = JSON.stringify(data, null, 2)
}

async function runFileProbe() {
  if (!probePath.value.trim()) {
    alert('请先输入相对路径')
    return
  }
  const head = Number.parseInt(probeHead.value || '128', 10)
  const tail = Number.parseInt(probeTail.value || '128', 10)
  const params = new URLSearchParams({
    path: probePath.value.trim(),
    head: String(Number.isFinite(head) ? Math.max(0, Math.min(4096, head)) : 128),
    tail: String(Number.isFinite(tail) ? Math.max(0, Math.min(4096, tail)) : 128),
    hash_mode: probeHashFull.value ? 'full' : 'sample',
  })
  const res = await fetch(`/api/debug/file-probe?${params.toString()}`)
  const data = await res.json()
  probeText.value = JSON.stringify(data, null, 2)
}

onMounted(async () => {
  await loadDebugContext()
  await loadProcessTree()
})
</script>
