<!--
  CsatModal — 工单满意度评分弹窗
  数据流：POST /csat/:id?score=&comment= → 成功后 emit('done')，父级重新拉评分初始态
  交互：星星必选（0 分不让提交）→ 评语选填 → 提交转圈，409 重复评分透出后端提示
-->
<script setup>
import { ref } from 'vue'
import api from '../../api'
import { toast } from '../../composables/useToast'
import AppModal from './AppModal.vue'
import AppButton from './AppButton.vue'
import AppTextarea from './AppTextarea.vue'
import StarRating from './StarRating.vue'

const props = defineProps({
  modelValue: Boolean,
  ticketId: { type: [Number, String], required: true },
})
const emit = defineEmits(['update:modelValue', 'done'])

const score = ref(0)
const comment = ref('')
const submitting = ref(false)

const submit = async () => {
  if (!score.value) {
    toast.error('先点星星打个分')
    return
  }
  submitting.value = true
  try {
    const res = await api.post(`/csat/${props.ticketId}`, null, {
      params: { score: score.value, comment: comment.value.trim() },
    })
    toast.success(res.data.msg)
    emit('update:modelValue', false)
    emit('done')
    score.value = 0
    comment.value = ''
  } catch (e) {
    toast.error(e.response?.data?.detail || '评分失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal
    :model-value="modelValue"
    title="服务评分"
    size="sm"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <p class="text-sm text-ink-2 leading-relaxed">
      这张工单处理得怎么样？打个分帮我们改进服务质量。
    </p>
    <div class="flex justify-center my-5">
      <StarRating v-model="score" size="lg" />
    </div>
    <AppTextarea
      v-model="comment"
      label="评语（选填）"
      placeholder="说说哪里做得好，哪里还能改进"
      :rows="3"
    />
    <template #footer>
      <AppButton variant="secondary" @click="$emit('update:modelValue', false)">取消</AppButton>
      <AppButton :loading="submitting" @click="submit">提交评分</AppButton>
    </template>
  </AppModal>
</template>
