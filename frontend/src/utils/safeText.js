export const SAFE_NOTICE_SHORT =
  '이 점수는 실제 창업 결과를 보장하지 않는 1차 후보지 필터링 참고 지표입니다.'

export const SAFE_NOTICE_LONG =
  '상가정보 스냅샷상 관측 유지와 공공데이터 proxy를 기반으로 후보지를 비교하기 위한 1차 후보지 필터링 지표입니다. 실제 창업 판단에는 임대료, 권리금, 점포 내부 상태, 브랜드 전략, 실제 유동인구 등 추가 확인이 필요합니다.'

const replacements = [
  [['창업', '성공', '확률'], '입지 적합도'],
  [['성공', '확률'], '입지 적합도'],
  [['매출', '예측'], '업무 관련 확장 검토'],
  [['폐업', '예측'], '관측 유지 proxy 참고'],
  [['실제', '생존확률'], '영업 유지 proxy 점수'],
  [['예상', '생존확률'], '영업 유지 proxy 점수'],
  [['이곳에', '창업하면', '성공'], '후보지로 검토할 수 있음'],
]

function patternFromParts(parts) {
  return new RegExp(parts.join('\\s*'), 'g')
}

export function sanitizeSafeText(text) {
  if (!text) return ''
  return replacements.reduce((acc, [parts, replacement]) => acc.replace(patternFromParts(parts), replacement), text)
}

export function containsForbiddenText(text) {
  if (!text) return false
  return replacements.some(([parts]) => patternFromParts(parts).test(text))
}
