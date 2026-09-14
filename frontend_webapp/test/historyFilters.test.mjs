import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildGenreFilterItems,
  findStatItem,
  getHistoryDate,
  sortHistory,
} from '../src/utils/historyFilters.js'

test('history date prefers raw ISO date and strips time', () => {
  assert.equal(getHistoryDate({ view_date: '2026-01-02', raw_date: '2026-01-02T12:30:00Z' }), '2026-01-02')
  assert.equal(getHistoryDate({ view_date: '2026-01' }), '2026-01')
})

test('genre filter uses the same minutes order as the donut', () => {
  const genres = [
    { name: 'Small', minutes: 10, show_ids: [1] },
    { name: 'Drama', minutes: 100, show_ids: [2] },
    { name: 'Other', minutes: 5, show_ids: [3] },
  ]

  const items = buildGenreFilterItems(genres)
  assert.deepEqual(items.map((item) => item.name), ['Drama', 'Small', 'Other'])
  assert.deepEqual(findStatItem(items, 0, 'Drama').show_ids, [2])
})

test('stat filters prefer stable names over stale array indexes', () => {
  const items = [{ name: 'Drama', show_ids: [7] }, { name: 'Comedy', show_ids: [8] }]
  assert.deepEqual(findStatItem(items, 0, 'Comedy'), items[1])
})

test('history sorting works for filtered records without view_date', () => {
  const sorted = sortHistory([
    { id: 1, raw_date: '2025-01-01' },
    { id: 2, view_date: '2026-01-01' },
  ])
  assert.deepEqual(sorted.map((item) => item.id), [2, 1])
})
