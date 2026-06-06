import { MapPin, Users } from 'lucide-react'
import { ScrollProgress, usePageReveal } from '../components/ScrollReveal.jsx'

const DATA_SOURCES = [
  { label: 'D1', name: '소상공인 상가 DB', desc: '상가 업종·위치·운영 현황', icon: '🏪' },
  { label: 'D2', name: '행정안전부 상가정보', desc: '상가 생존·폐업 이력 데이터', icon: '📊' },
  { label: 'D3', name: '건축물대장', desc: '건물 연령·용도·면적 정보', icon: '🏢' },
  { label: 'D4', name: '국토부 공시지가', desc: '토지 등급별 공시 가격', icon: '💰' },
  { label: 'D5', name: '실거래가 공개시스템', desc: '상업업무용 부동산 거래 수준', icon: '📋' },
  { label: 'D6', name: '대중교통 정류장 DB', desc: '버스 정류장 위치·노선 수', icon: '🚌' },
  { label: 'D7', name: '광주도시철도 역사 위치', desc: '지하철역 좌표 및 노선 정보', icon: '🚇' },
]

const TEAM = [
  { name: '박진한', badge: '팀장', dept: '인공지능학부', role: '웹 백엔드 개발 · AI 모델 개발', desc: '서버 설계, Gemini AI 연동, 창업 적합도 예측 모델 개발' },
  { name: '최서진', badge: '', dept: '인공지능학부', role: '웹 프론트엔드 개발', desc: '지도 시각화, 대시보드 UI 구현' },
  { name: '박시훈', badge: '', dept: '인공지능학부', role: '데이터 수집 · AI 모델 개발', desc: 'XGBoost, SHAP 기반 창업 적합도 예측 모델 구축' },
  { name: '장유민', badge: '', dept: '인공지능학부', role: '기획 · 보고서 작성', desc: '프로젝트 설계, 발표자료 구성, 결과 정리' },
  { name: '윤은지', badge: '', dept: '인공지능학부', role: '기획 · 보고서 작성', desc: '프로젝트 설계, 발표자료 구성, 결과 정리' },
]

export default function AboutPage() {
  usePageReveal()

  return (
    <div className="info-page">
      <ScrollProgress />

      <div className="info-hero reveal">
        <Users size={32} color="#8272f9" />
        <h1>소개</h1>
        <p>BizSpot AI는 감이 아닌 데이터로 소상공인 창업 입지를 분석합니다</p>
      </div>

      <section className="info-section">
        <h2 className="reveal">프로젝트 배경</h2>
        <div className="about-intent-grid">
          <div className="about-intent-card reveal reveal-delay-1">
            <div className="about-intent-tag problem">문제의식</div>
            <h3>감이 아닌 데이터</h3>
            <p>예비 창업자는 보통 유명 상권, 지인 추천, 직관에 기대어 입지를 고릅니다. BizSpot AI는 수요·경쟁·비용·접근성을 수치로 비교합니다.</p>
          </div>
          <div className="about-intent-card reveal reveal-delay-2">
            <div className="about-intent-tag direction">핵심 방향</div>
            <h3>검증 → 해석 → 웹</h3>
            <p>웹은 최종 포장지가 아닙니다. 모델이 어떤 변수를 근거로 판단했는지 보여주는 설명 인터페이스입니다.</p>
          </div>
          <div className="about-intent-card reveal reveal-delay-3">
            <div className="about-intent-tag limit">과장 금지</div>
            <h3>성공 보장 X</h3>
            <p>이 시스템은 "창업 성공 예언"이 아니라, 후보지를 1차로 거르고 위험 요인을 확인하는 의사결정 보조 도구입니다.</p>
          </div>
        </div>
      </section>

      <section className="info-section">
        <h2 className="reveal">팀 구성원</h2>
        <div className="about-team-grid">
          {TEAM.map((m, i) => (
            <div key={m.name} className={`about-team-card reveal reveal-delay-${(i % 3) + 1}`}>
              <div className="about-team-avatar">{m.name[0]}</div>
              <div>
                <div className="about-team-name">
                  {m.name}
                  {m.badge && <span className="about-team-badge">{m.badge}</span>}
                </div>
                <div className="about-team-dept">{m.dept}</div>
                <div className="about-team-role">{m.role}</div>
                <div className="about-team-desc">{m.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="info-section">
        <h2 className="reveal">활용 데이터</h2>
        <p className="info-sub reveal">광주광역시 공공데이터 7종을 결합해 입지 점수를 산출합니다</p>
        <div className="about-data-grid">
          {DATA_SOURCES.map((d, i) => (
            <div key={d.label} className={`about-data-card reveal reveal-delay-${(i % 3) + 1}`}>
              <div className="about-data-emoji">{d.icon}</div>
              <div className="about-data-tag">{d.label}</div>
              <div className="about-data-name">{d.name}</div>
              <div className="about-data-desc">{d.desc}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="info-section">
        <div className="about-scope-note reveal">
          <MapPin size={16} color="#8272f9" />
          현재 서비스 범위: <strong>광주광역시 5개 자치구</strong> — 광산구, 북구, 서구, 남구, 동구
        </div>
      </section>
    </div>
  )
}
