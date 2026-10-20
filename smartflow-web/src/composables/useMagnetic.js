/**
 * useMagnetic — 磁吸手感
 * 鼠标靠近/悬停时，元素朝光标轻微位移（惯性跟随），离开回弹
 * 用法：const { el, onMove, onLeave } = useMagnetic(0.3)；绑到元素 ref + mousemove/mouseleave
 * 数据流：纯交互，无 API；写 CSS 变量 --mx/--my/--gx/--gy
 */
import { ref } from 'vue'

export function useMagnetic(strength = 0.35) {
  const el = ref(null)

  const onMove = (e) => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const node = el.value
    if (!node) return
    const r = node.getBoundingClientRect()
    const cx = r.left + r.width / 2
    const cy = r.top + r.height / 2
    node.style.setProperty('--mx', (e.clientX - cx) * strength + 'px')
    node.style.setProperty('--my', (e.clientY - cy) * strength + 'px')
    node.style.setProperty('--gx', ((e.clientX - r.left) / r.width) * 100 + '%')
    node.style.setProperty('--gy', ((e.clientY - r.top) / r.height) * 100 + '%')
  }

  const onLeave = () => {
    const node = el.value
    if (!node) return
    node.style.setProperty('--mx', '0px')
    node.style.setProperty('--my', '0px')
  }

  return { el, onMove, onLeave }
}
