export const INDUSTRIES = [
  { value: 'all', label: '전체 업종' },
  { value: 'cafe', label: '카페' },
  { value: 'dessert_bakery', label: '디저트/베이커리' },
  { value: 'restaurant_general', label: '일반 음식점' },
  { value: 'bunsik', label: '분식' },
  { value: 'chicken', label: '치킨' },
  { value: 'convenience_store', label: '편의점' },
  { value: 'beauty_hair', label: '미용실' },
  { value: 'laundry', label: '세탁소' },
]

export const DISTRICTS = ['전체', '동구', '서구', '남구', '북구', '광산구']

export function industryLabel(value) {
  return INDUSTRIES.find((item) => item.value === value)?.label || value || '업종 미상'
}
