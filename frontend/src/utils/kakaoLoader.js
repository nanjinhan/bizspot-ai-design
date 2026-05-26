let kakaoMapPromise = null
const SCRIPT_SELECTOR = 'script[data-kakao-map-sdk="true"]'

export function loadKakaoMap() {
  if (window.kakao?.maps) {
    return Promise.resolve(window.kakao)
  }
  if (kakaoMapPromise) return kakaoMapPromise

  kakaoMapPromise = new Promise((resolve, reject) => {
    const key = import.meta.env.VITE_KAKAO_MAP_KEY
    if (!key || key === 'YOUR_KAKAO_JAVASCRIPT_KEY') {
      kakaoMapPromise = null
      reject(new Error('Kakao JavaScript key is missing. frontend/.env 설정 후 Vite dev server를 재시작하세요.'))
      return
    }

    let loadTimer = window.setTimeout(() => {
      kakaoMapPromise = null
      reject(
        new Error(
          'Kakao SDK load timed out. Kakao Developers의 Web 플랫폼 도메인 등록을 확인하세요.',
        ),
      )
    }, 10000)

    const finishLoad = () => {
      if (!window.kakao?.maps?.load) {
        window.clearTimeout(loadTimer)
        kakaoMapPromise = null
        reject(new Error('Kakao Maps SDK is not available. JavaScript 키 종류와 도메인 등록을 확인하세요.'))
        return
      }
      const loadedScript = document.querySelector(SCRIPT_SELECTOR)
      if (loadedScript) loadedScript.dataset.loaded = 'true'
      window.kakao.maps.load(() => {
        window.clearTimeout(loadTimer)
        resolve(window.kakao)
      })
    }

    const failLoad = () => {
      window.clearTimeout(loadTimer)
      kakaoMapPromise = null
      reject(
        new Error(
          'Failed to load Kakao Maps SDK. JavaScript 키와 현재 접속 도메인이 Kakao Developers에 등록됐는지 확인하세요.',
        ),
      )
    }

    const existing = document.querySelector(SCRIPT_SELECTOR)
    if (existing) {
      if (existing.dataset.loaded === 'true') {
        finishLoad()
        return
      }
      existing.addEventListener('load', finishLoad, { once: true })
      existing.addEventListener('error', failLoad, { once: true })
      return
    }

    const script = document.createElement('script')
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(
      key,
    )}&autoload=false&libraries=services`
    script.async = true
    script.dataset.kakaoMapSdk = 'true'
    script.onload = finishLoad
    script.onerror = failLoad
    document.head.appendChild(script)
  })

  return kakaoMapPromise
}
