import { createRouter, createWebHistory } from 'vue-router'
import BrowserPage from '../pages/BrowserPage.vue'
import PreviewPage from '../pages/PreviewPage.vue'
import TasksPage from '../pages/TasksPage.vue'
import DebugPage from '../pages/DebugPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/browser' },
    { path: '/browser', name: 'browser', component: BrowserPage },
    { path: '/preview', name: 'preview', component: PreviewPage },
    { path: '/tasks', name: 'tasks', component: TasksPage },
    { path: '/debug', name: 'debug', component: DebugPage },
  ],
})

export default router
