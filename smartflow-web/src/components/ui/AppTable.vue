<!--
  AppTable — 响应式表格
  columns: [{ key, label, align?, primary? }]；primary 列在移动端作标题
  md+ 真表格，以下降级为卡片列表；expandable + expandedId 展开行
  slots: cell-{key} 自定义单元格、expand 展开内容、header-actions 表尾
-->
<script setup>
import { ChevronRight } from 'lucide-vue-next'

const props = defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  rowKey: { type: String, default: 'id' },
  loading: Boolean,
  emptyText: { type: String, default: '暂无数据' },
  expandable: Boolean,
  expandedId: { type: [Number, String], default: null },
})
defineEmits(['toggle-expand'])

const primaryCol = () => props.columns.find((c) => c.primary) || props.columns[0]

const shimmer = {
  backgroundImage: 'linear-gradient(90deg, var(--surface-2) 25%, var(--line) 50%, var(--surface-2) 75%)',
  backgroundSize: '200% 100%',
}
</script>

<template>
  <div>
    <!-- 桌面表格 -->
    <div class="hidden md:block bg-surface border border-line rounded-card overflow-hidden shadow-[var(--shadow-card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-line bg-surface-2/50">
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3"
              :class="col.align === 'right' ? 'text-right' : ''"
            >
              {{ col.label }}
            </th>
            <th v-if="expandable" class="w-10" />
          </tr>
        </thead>
        <tbody>
          <template v-for="row in rows" :key="row[rowKey]">
            <tr class="border-b border-line/60 last:border-0 transition-colors duration-100 hover:bg-surface-2/40">
              <td
                v-for="col in columns"
                :key="col.key"
                class="px-4 py-3.5"
                :class="[col.align === 'right' ? 'text-right' : '', col.primary ? 'font-medium text-ink' : 'text-ink-2']"
              >
                <slot :name="`cell-${col.key}`" :row="row">{{ row[col.key] }}</slot>
              </td>
              <td v-if="expandable" class="px-2 text-right">
                <button
                  class="p-1.5 rounded-ctl text-ink-3 hover:text-ink hover:bg-surface-2 transition-all"
                  :aria-label="expandedId === row[rowKey] ? '收起详情' : '展开详情'"
                  :aria-expanded="expandedId === row[rowKey]"
                  @click="$emit('toggle-expand', row[rowKey])"
                >
                  <ChevronRight
                    class="w-4 h-4 transition-transform duration-200"
                    :class="expandedId === row[rowKey] ? 'rotate-90' : ''"
                  />
                </button>
              </td>
            </tr>
            <tr v-if="expandable && expandedId === row[rowKey]">
              <td :colspan="columns.length + 1" class="px-4 py-4 bg-surface-2/40 border-b border-line">
                <slot name="expand" :row="row" />
              </td>
            </tr>
          </template>
          <tr v-if="loading && !rows.length">
            <td :colspan="columns.length + 1" class="px-4 py-8">
              <div class="space-y-3">
                <div
                  v-for="i in 3"
                  :key="i"
                  class="h-4 rounded-md animate-shimmer"
                  :class="i === 3 ? 'w-2/3' : 'w-full'"
                  :style="shimmer"
                />
              </div>
            </td>
          </tr>
          <tr v-if="!loading && !rows.length">
            <td :colspan="columns.length + 1" class="px-4 py-12 text-center text-ink-3 text-sm">
              {{ emptyText }}
            </td>
          </tr>
        </tbody>
      </table>
      <slot name="header-actions" />
    </div>

    <!-- 移动端卡片 -->
    <div class="md:hidden space-y-3">
      <div v-if="loading && !rows.length" class="space-y-3">
        <div v-for="i in 3" :key="i" class="h-20 rounded-card animate-shimmer" :style="shimmer" />
      </div>
      <div
        v-for="row in rows"
        :key="row[rowKey]"
        class="bg-surface border border-line rounded-card shadow-[var(--shadow-card)] p-4"
      >
        <div class="flex items-start justify-between gap-3 mb-2">
          <div class="font-medium text-ink text-sm">
            <slot :name="`cell-${primaryCol().key}`" :row="row">{{ row[primaryCol().key] }}</slot>
          </div>
          <button
            v-if="expandable"
            class="p-1.5 -m-1 rounded-ctl text-ink-3 hover:text-ink transition-all"
            :aria-label="expandedId === row[rowKey] ? '收起详情' : '展开详情'"
            :aria-expanded="expandedId === row[rowKey]"
            @click="$emit('toggle-expand', row[rowKey])"
          >
            <ChevronRight
              class="w-4 h-4 transition-transform duration-200"
              :class="expandedId === row[rowKey] ? 'rotate-90' : ''"
            />
          </button>
        </div>
        <dl class="space-y-1.5">
          <div
            v-for="col in columns.filter((c) => !c.primary)"
            :key="col.key"
            class="flex items-center justify-between text-[13px]"
          >
            <dt class="text-ink-3">{{ col.label }}</dt>
            <dd class="text-ink-2">
              <slot :name="`cell-${col.key}`" :row="row">{{ row[col.key] }}</slot>
            </dd>
          </div>
        </dl>
        <div v-if="expandable && expandedId === row[rowKey]" class="mt-3 pt-3 border-t border-line">
          <slot name="expand" :row="row" />
        </div>
      </div>
      <div v-if="!loading && !rows.length" class="py-12 text-center text-ink-3 text-sm">
        {{ emptyText }}
      </div>
    </div>
  </div>
</template>
