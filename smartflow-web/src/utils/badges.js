/**
 * 徽章色调映射：后端枚举 → AppBadge tone
 */
export const ticketTones = {
  pending: 'amber',
  processing: 'blue',
  resolved: 'brand',
  closed: 'gray',
  escalated: 'red',
  waiting: 'amber',
  accepted: 'brand',
}

export const roleTones = { admin: 'red', support: 'ai', user: 'gray' }

export const deptTones = {
  it: 'blue', hr: 'ai', finance: 'brand', admin: 'amber', all: 'gray',
}

export const docStatusTones = { active: 'brand', processing: 'amber', failed: 'red' }

export function toneFor(value, map, fallback = 'gray') {
  return map[value] || fallback
}
