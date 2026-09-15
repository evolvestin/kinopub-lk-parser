import assert from 'node:assert/strict'
import test from 'node:test'
import { cleanTelegramHash, parseTelegramInitDataFromUrl } from '../src/utils/telegramHash.js'

const launchData = 'user%3D%257B%2522id%2522%253D123%257D%26auth_date%3D1789502812%26hash%3Dabc'

test('cleans Telegram params when they arrive after the hash-router slash', () => {
  const hash = `#/tgWebAppData=${launchData}&tgWebAppVersion=9.6&tgWebAppPlatform=tdesktop&q=%D0%A0%D1%8B%D1%86`

  assert.equal(cleanTelegramHash(hash), '#/?q=%D0%A0%D1%8B%D1%86')
})

test('cleans Telegram params in a normal hash route without losing the route', () => {
  const hash = `#/search?tgWebAppData=${launchData}&tgWebAppVersion=9.6&q=matrix`

  assert.equal(cleanTelegramHash(hash), '#/search?q=matrix')
})

test('extracts init data from both Telegram hash formats', () => {
  assert.equal(
    parseTelegramInitDataFromUrl(`#tgWebAppData=${launchData}`),
    decodeURIComponent(launchData)
  )
  assert.equal(
    parseTelegramInitDataFromUrl(`#/tgWebAppData=${launchData}&tgWebAppVersion=9.6`),
    decodeURIComponent(launchData)
  )
})

test('keeps supporting init data exposed directly as signed hash fields', () => {
  const directData = 'user=%7B%22id%22%3A123%7D&auth_date=1789502812&hash=abc'

  assert.equal(parseTelegramInitDataFromUrl(`#${directData}`), directData)
})
