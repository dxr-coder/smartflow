/**
 * Markdown 渲染：marked + marked-highlight + hljs + DOMPurify 消毒
 * marked@18 已移除 setOptions({ highlight })，必须走插件
 */
import { Marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import hljs from 'highlight.js/lib/common'
import DOMPurify from 'dompurify'

const marked = new Marked(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value
      }
      return hljs.highlightAuto(code).value
    },
  })
)
marked.setOptions({ gfm: true, breaks: true })

export function renderMarkdown(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text))
}
