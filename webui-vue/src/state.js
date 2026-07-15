import { ref } from 'vue'

export const root = ref('')
export const rootInput = ref('')
export const current = ref('')
export const items = ref([])

export const previewPath = ref('')
export const previewText = ref('点击文件名预览文本内容...')
export const previewKind = ref('text')
export const previewMime = ref('')
export const previewEncoding = ref('')
export const previewSize = ref('')
export const previewUrl = ref('')
export const vscodeOpeningPath = ref('')
export const batchDownloading = ref(false)
export const replacingPath = ref('')

export const debugText = ref('点击“刷新调试信息”查看运行上下文差异...')
export const debugIncludeAllEnv = ref(false)

export const page = ref(1)
export const pageSize = ref(200)
export const total = ref(0)
export const totalPages = ref(1)
export const sort = ref('name_asc')

export const tasks = ref([])

export async function list(path = current.value || '', forceFirstPage = false) {
  if (forceFirstPage) page.value = 1

  const params = new URLSearchParams({
    path,
    page: String(page.value),
    page_size: String(pageSize.value),
    sort: sort.value,
  })

  const res = await fetch(`/api/list?${params.toString()}`)
  const data = await res.json()
  if (!data.ok) {
    alert(`加载失败: ${data.error ?? '未知错误'}`)
    return false
  }

  root.value = data.root
  rootInput.value = data.root
  current.value = data.current
  items.value = data.items
  total.value = data.total
  totalPages.value = data.total_pages
  page.value = data.page
  return true
}

export async function setRoot() {
  const target = rootInput.value.trim()
  if (!target) {
    alert('请输入目录路径')
    return false
  }

  const res = await fetch('/api/root', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ root: target }),
  })
  const data = await res.json()
  if (!data.ok) {
    alert(`设置失败: ${data.error ?? '未知错误'}`)
    return false
  }

  return await list('', true)
}

export async function loadPreview(path) {
  previewPath.value = path
  const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`)
  const data = await res.json()
  if (!data.ok) {
    previewText.value = `预览失败: ${data.error ?? '未知错误'}`
    previewKind.value = 'text'
    previewUrl.value = ''
    return false
  }

  previewKind.value = data.kind || 'text'
  previewMime.value = data.mime || ''
  previewEncoding.value = data.encoding || ''
  previewSize.value = typeof data.size_bytes === 'number' ? `${data.size_bytes} B` : ''

  if (previewKind.value === 'image' || previewKind.value === 'pdf') {
    previewUrl.value = `${data.url}&_t=${Date.now()}`
    previewText.value = ''
    return true
  }

  previewUrl.value = ''
  previewText.value = data.content || ''
  return true
}

export async function openInVSCode(path) {
  if (vscodeOpeningPath.value) return false
  vscodeOpeningPath.value = path
  try {
    const res = await fetch('/api/open-in-vscode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
    const data = await res.json()
    if (!data.ok) {
      alert(`无法在 VS Code 中打开: ${data.error ?? '未知错误'}`)
      return false
    }
    return true
  } catch (error) {
    alert(`无法在 VS Code 中打开: ${error instanceof Error ? error.message : '请求失败'}`)
    return false
  } finally {
    vscodeOpeningPath.value = ''
  }
}

export async function downloadSelected(paths) {
  if (!paths.length || batchDownloading.value) return false
  batchDownloading.value = true
  try {
    const res = await fetch('/api/download-selected', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      alert(`下载失败: ${data.detail ?? data.error ?? '未知错误'}`)
      return false
    }

    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'selected-files.zip'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    return true
  } catch (error) {
    alert(`下载失败: ${error instanceof Error ? error.message : '请求失败'}`)
    return false
  } finally {
    batchDownloading.value = false
  }
}

export async function replaceFile(path, file) {
  if (!path || !file || replacingPath.value) return false
  replacingPath.value = path
  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`, {
      method: 'PUT',
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
        'X-Upload-Filename': encodeURIComponent(file.name),
      },
      body: file,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok || !data.ok) {
      alert(`替换失败: ${data.error ?? data.detail ?? '未知错误'}`)
      return false
    }
    return true
  } catch (error) {
    alert(`替换失败: ${error instanceof Error ? error.message : '请求失败'}`)
    return false
  } finally {
    replacingPath.value = ''
  }
}

export async function createZipTask(path) {
  const res = await fetch('/api/tasks/zip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  const data = await res.json()
  if (!data.ok) {
    alert(`创建任务失败: ${data.error ?? '未知错误'}`)
    return false
  }
  await loadTasks()
  return true
}

export async function loadTasks() {
  const res = await fetch('/api/tasks?limit=30')
  const data = await res.json()
  if (!data.ok) return false
  tasks.value = data.tasks
  return true
}

export async function removeTask(task) {
  if (task.status === 'running' || task.status === 'pending') {
    alert('任务正在进行中，暂不支持删除')
    return false
  }
  if (!confirm(`确认删除任务 ${task.id.slice(0, 8)} ?`)) return false

  const res = await fetch(`/api/tasks/${task.id}`, { method: 'DELETE' })
  const data = await res.json()
  if (!data.ok) {
    alert(`删除失败: ${data.error ?? '未知错误'}`)
    return false
  }
  await loadTasks()
  return true
}

export async function loadDebugContext() {
  const params = new URLSearchParams({
    include_all_env: String(debugIncludeAllEnv.value),
    env_limit: '300',
  })
  const res = await fetch(`/api/debug/context?${params.toString()}`)
  const data = await res.json()
  debugText.value = JSON.stringify(data, null, 2)
  return true
}

export function statusText(status) {
  if (status === 'done') return '完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '进行中'
  return '排队中'
}
