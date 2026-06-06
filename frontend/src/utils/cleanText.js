export function cleanProxyText(text) {
  if (!text) return text
  return text
    .replace(/동일 업종 과밀 부담 proxy가/g, '동일업종 과밀 부담이')
    .replace(/접근성 proxy가/g, '접근성이')
    .replace(/비용 부담 proxy가/g, '임대 비용 부담이')
    .replace(/수요 proxy가/g, '유동인구 지수가')
    .replace(/영업 유지 proxy가/g, '영업 지속 점수가')
    .replace(/업종 다양성 proxy가/g, '업종 다양성이')
    .replace(/영업 유지 proxy\s*(점수)?/g, '영업 지속 점수')
    .replace(/수요 proxy\s*(점수)?/g, '유동인구 지수')
    .replace(/접근성 proxy/g, '접근성 지수')
    .replace(/비용 부담 proxy/g, '임대 비용 부담')
    .replace(/동일 업종 과밀 부담 proxy/g, '동일업종 과밀 부담')
    .replace(/동일 업종 proxy/g, '동일업종')
    .replace(/\s+proxy가/g, '이')
    .replace(/\s+proxy이/g, '이')
    .replace(/\s+proxy를/g, '을')
    .replace(/\s+proxy는/g, '은')
    .replace(/\s+proxy의/g, '의')
    .replace(/\s+proxy\s*(점수)?/g, ' 점수')
    .replace(/\s+proxy/g, '')
}
