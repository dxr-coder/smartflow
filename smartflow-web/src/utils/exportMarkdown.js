/**
 * 对话导出 Markdown：Blob 下载
 */
export function exportMarkdown(messages, agentLabelFn) {
  const now = new Date()
  const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  let md = `# SmartFlow 对话记录\n\n**日期：** ${dateStr}\n\n---\n\n`
  for (const msg of messages) {
    if (!msg.content) continue
    const role = msg.role === 'user' ? '用户' : `AI 助手（${agentLabelFn?.(msg.agent_name, msg.source) || msg.agent_name || 'AI'}）`
    md += `**${role}：**\n\n${msg.content}\n\n---\n\n`
  }
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `SmartFlow对话_${dateStr}.md`
  a.click()
  URL.revokeObjectURL(url)
}
