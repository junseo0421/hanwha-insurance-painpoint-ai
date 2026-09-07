import { useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const concernsOptions = ['암', '뇌혈관', '심혈관', '질병', '입원', '수술', '상해', '사망', '간병']
const familyOptions = ['선택', '1인 가구', '부부', '자녀 있음', '부모 부양', '기타']
const budgetOptions = ['선택', '3만원 이하', '3만~5만원', '5만~8만원', '8만~12만원', '12만원 이상']
const existingOptions = ['선택', '있음', '없음', '잘 모르겠음']

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || 'API 요청에 실패했습니다.')
  return body
}

function formatNumber(value) {
  return new Intl.NumberFormat('ko-KR').format(Number(value || 0))
}

function ProductCard({ product }) {
  const score = Number(product._match_score || 0)
  const reasons = product._ai_reasons?.length ? product._ai_reasons : product._match_reasons || []
  const cautions = product._ai_cautions?.length ? product._ai_cautions : [product.caution]
  return <article className="product-card">
    <div className="score-badge">AI 추천도 {score}점</div>
    <h3>{product.name}</h3>
    <p className="muted">{product.type} · {product.target}</p>
    <dl className="product-facts">
      <div><dt>주요 보장</dt><dd>{(product.coverage || []).join(', ')}</dd></div>
      <div><dt>특징</dt><dd>{(product.strengths || []).join(', ')}</dd></div>
      <div><dt>갱신 여부</dt><dd>{product.renewal}</dd></div>
      <div><dt>보험료 예시</dt><dd>{product.premium_example}</dd></div>
    </dl>
    <div className="score-bar"><span style={{ width: `${Math.min(100, score)}%` }} /></div>
    <p className="score-detail">핵심 조건 {product._hard_score || 0}/70 · 설문 대응 {product._survey_points || 0}/10 · AI 상황 해석 {product._llm_bonus || 0}/20</p>
    <div className="reason-box"><strong>이런 점에서 고객님과 잘 맞아요</strong><ul>{reasons.slice(0, 3).map((reason, index) => <li key={index}>{reason}</li>)}</ul></div>
    <div className="caution-box"><strong>가입 전에 이것은 꼭 확인하세요</strong><ul>{cautions.filter(Boolean).slice(0, 2).map((item, index) => <li key={index}>{item}</li>)}</ul></div>
    <p className="source">근거: {product.source} / 기준일 {product.source_date}</p>
  </article>
}

function App() {
  const [form, setForm] = useState({ insurance_age: 20, family_status: '선택', concerns: [], budget: '선택', existing: '선택', additional_note: '' })
  const [result, setResult] = useState(null)
  const [products, setProducts] = useState([])
  const [compareIds, setCompareIds] = useState([])
  const [questions, setQuestions] = useState([])
  const [questionMode, setQuestionMode] = useState('대기 중')
  const [selectedQuestion, setSelectedQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [feedback, setFeedback] = useState('')
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')
  const [survey, setSurvey] = useState(null)

  const profileValid = form.concerns.length > 0 && form.family_status !== '선택' && form.budget !== '선택' && form.existing !== '선택'
  const topProducts = products.slice(0, 3)
  const extraProducts = products.slice(3)
  const selectedCompare = products.filter((product) => compareIds.includes(product.product_id))
  const comparisonProducts = selectedCompare.length ? selectedCompare : topProducts

  function update(name, value) { setForm((old) => ({ ...old, [name]: value })) }
  function toggleConcern(value) { setForm((old) => ({ ...old, concerns: old.concerns.includes(value) ? old.concerns.filter((item) => item !== value) : [...old.concerns, value] })) }

  async function runAnalysis(event) {
    event.preventDefault()
    setError('')
    if (!profileValid) { setError('관심 보장, 가족 구성, 예산, 기존 보험을 선택해 주세요.'); return }
    setLoading('analysis')
    try {
      const body = await api('/api/recommendations', { method: 'POST', body: JSON.stringify({ customer: form, use_llm: true }) })
      setResult(body)
      setProducts(body.products || [])
      setCompareIds((body.products || []).slice(0, 3).map((product) => product.product_id))
      setQuestions([]); setAnswer(null)
    } catch (err) { setError(err.message) } finally { setLoading('') }
  }

  async function loadSurvey() {
    setLoading('survey'); setError('')
    try { setSurvey(await api('/api/survey-analysis')) } catch (err) { setError(err.message) } finally { setLoading('') }
  }

  async function generateQuestions() {
    if (!result) return
    setLoading('questions'); setError('')
    try {
      const body = await api('/api/questions/recommend', { method: 'POST', body: JSON.stringify({ customer: form, product_ids: comparisonProducts.map((item) => item.product_id), use_llm: true }) })
      setQuestions(body.questions || []); setQuestionMode(body.mode || '완료'); setSelectedQuestion(body.questions?.[0] || '')
    } catch (err) { setError(err.message) } finally { setLoading('') }
  }

  async function askQuestion() {
    if (!selectedQuestion.trim()) return
    setLoading('answer'); setError('')
    try { setAnswer(await api('/api/questions/answer', { method: 'POST', body: JSON.stringify({ question: selectedQuestion, product_ids: comparisonProducts.map((item) => item.product_id), use_llm: true }) })) } catch (err) { setError(err.message) } finally { setLoading('') }
  }

  async function sendFeedback() {
    if (!answer || !feedback.trim()) return
    setLoading('feedback'); setError('')
    try {
      const body = await api('/api/questions/feedback', { method: 'POST', body: JSON.stringify({ question: selectedQuestion, previous_answer: answer.response, feedback, product_ids: comparisonProducts.map((item) => item.product_id), use_llm: true }) })
      setAnswer((old) => ({ ...old, response: body.response, mode: body.mode })); setFeedback('')
    } catch (err) { setError(err.message) } finally { setLoading('') }
  }

  const comparisonRows = useMemo(() => [
    ['상품 유형', ...comparisonProducts.map((item) => item.type)],
    ['주요 보장', ...comparisonProducts.map((item) => (item.coverage || []).join(', '))],
    ['갱신 여부', ...comparisonProducts.map((item) => item.renewal)],
    ['보험료 예시', ...comparisonProducts.map((item) => item.premium_example)],
    ['AI 추천도', ...comparisonProducts.map((item) => `${item._match_score || 0}점`)],
    ['주의사항', ...comparisonProducts.map((item) => item.caution)],
  ], [comparisonProducts])

  return <>
    <header className="site-header"><div className="header-inner"><span className="eyebrow">보험 상품 안내</span><span className="brand">HANWHA LIFE</span></div></header>
    <main className="page-shell">
      <section className="hero"><p className="hero-kicker">EASY GUIDE <span>AI</span></p><h1>한화생명 Easy Guide</h1><p>내게 필요한 보장과 상품 정보를 한눈에 확인하세요.</p></section>
      <div className="layout">
        <aside className="panel input-panel"><h2>고객 상황 입력</h2><p className="muted">핵심 조건을 입력하고 분석하기를 눌러 주세요.</p>
          <form onSubmit={runAnalysis}>
            <label>보험나이<input type="number" min="0" max="100" value={form.insurance_age} onChange={(e) => update('insurance_age', Number(e.target.value))} /></label>
            <label>가족 구성<select value={form.family_status} onChange={(e) => update('family_status', e.target.value)}>{familyOptions.map((option) => <option key={option}>{option}</option>)}</select></label>
            <fieldset><legend>관심 보장(복수 선택)</legend><div className="choice-grid">{concernsOptions.map((option) => <label className="choice" key={option}><input type="checkbox" checked={form.concerns.includes(option)} onChange={() => toggleConcern(option)} />{option}</label>)}</div></fieldset>
            <label>월 납입 예산<select value={form.budget} onChange={(e) => update('budget', e.target.value)}>{budgetOptions.map((option) => <option key={option}>{option}</option>)}</select></label>
            <label>기존 보험 가입 여부<select value={form.existing} onChange={(e) => update('existing', e.target.value)}>{existingOptions.map((option) => <option key={option}>{option}</option>)}</select></label>
            <label>추가 상황·희망 조건(선택)<textarea value={form.additional_note} onChange={(e) => update('additional_note', e.target.value)} placeholder="예: 가족력 때문에 암 보장을 꼼꼼히 확인하고 싶어요." /></label>
            <button className="primary" disabled={loading === 'analysis'}>{loading === 'analysis' ? 'AI가 분석 중입니다…' : 'AI 분석하기'}</button>
          </form>
        </aside>
        <div className="content-column">
          {error && <div className="error">{error}</div>}
          <section className="section"><div className="section-heading"><div><p className="section-kicker">PROFILE & PRODUCTS</p><h2>고객 유형 및 상품 안내</h2></div>{result && <span className="pill">{result.customer_type}</span>}</div>
            {!result ? <div className="empty">왼쪽에서 고객 상황을 입력하면 맞춤 상품 안내가 시작됩니다.</div> : <><p className="mode">{result.recommendation_mode}</p><div className="product-grid">{topProducts.map((product) => <ProductCard key={product.product_id} product={product} />)}</div></>}
          </section>
          <section className="section"><p className="section-kicker">COMPARE</p><h2>상품 비교</h2>{!result ? <div className="empty">AI 분석 후 상품을 비교할 수 있습니다.</div> : <><p className="muted">현재 고객 기준 추천 점수가 높은 상품부터 표시합니다. 추가 상품도 선택할 수 있습니다.</p><div className="compare-options">{extraProducts.map((product) => <label key={product.product_id}><input type="checkbox" checked={compareIds.includes(product.product_id)} onChange={() => setCompareIds((ids) => ids.includes(product.product_id) ? ids.filter((id) => id !== product.product_id) : [...ids, product.product_id])} />{product.name}</label>)}</div><div className="table-scroll"><table><thead><tr><th>비교 항목</th>{comparisonProducts.map((product) => <th key={product.product_id}>{product.name}</th>)}</tr></thead><tbody>{comparisonRows.map(([label, ...values]) => <tr key={label}><th>{label}</th>{values.map((value, index) => <td key={index}>{value}</td>)}</tr>)}</tbody></table></div></>}</section>
          <section className="section"><p className="section-kicker">CONVERSATION</p><h2>상담 전 질문 추천 및 AI 설명</h2>{!result ? <div className="empty">AI 분석 후 상담 질문을 생성할 수 있습니다.</div> : <><button className="secondary" onClick={generateQuestions} disabled={loading === 'questions'}>{loading === 'questions' ? '질문을 만드는 중입니다…' : 'AI 질문 추천 생성'}</button><span className="mode inline">{questionMode}</span>{questions.length > 0 && <div className="question-list">{questions.map((question) => <button key={question} className={selectedQuestion === question ? 'question selected' : 'question'} onClick={() => setSelectedQuestion(question)}>{question}</button>)}</div>}<div className="ask-row"><input value={selectedQuestion} onChange={(e) => setSelectedQuestion(e.target.value)} placeholder="질문을 직접 입력하세요." /><button className="primary" onClick={askQuestion} disabled={loading === 'answer' || !selectedQuestion.trim()}>{loading === 'answer' ? '답변 생성 중…' : 'AI에게 물어보기'}</button></div>{answer && <div className="answer-box"><p className="answer-meta">분류된 질문 유형: {answer.intent} · {answer.mode}</p><div className="answer-text">{answer.response}</div><div className="feedback-row"><input value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="답변이 아쉬운 점을 적어 주세요." /><button onClick={sendFeedback} disabled={loading === 'feedback' || !feedback.trim()}>{loading === 'feedback' ? '반영 중…' : '피드백 반영'}</button></div></div>}</>}</section>
          <section className="section"><p className="section-kicker">CUSTOMER INSIGHT</p><h2>설문 기반 고객 불편 분석</h2>{!survey ? <button className="secondary" onClick={loadSurvey} disabled={loading === 'survey'}>{loading === 'survey' ? '설문 결과를 불러오는 중…' : '설문 분석 보기'}</button> : <><div className="metric-grid"><div><span>분석 방법</span><strong>{survey.method || '저장된 분석'}</strong></div><div><span>클러스터 수</span><strong>{survey.n_clusters}</strong></div><div><span>표시 항목</span><strong>{survey.clusters?.length || 0}</strong></div></div><div className="insight-list">{(survey.clusters || []).map((cluster) => <div className="insight-row" key={cluster.label}><strong>{cluster.label}</strong><span>{formatNumber(cluster.count)}건 · 평균 심각도 {Number(cluster.avg_severity || 0).toFixed(1)}/5</span></div>)}</div></>}</section>
        </div>
      </div>
      <footer>본 서비스는 보험상품 이해를 돕는 프로토타입입니다. 실제 가입 판단은 공식 상품 설명서와 전문 상담을 통해 확인해 주세요.</footer>
    </main>
  </>
}

createRoot(document.getElementById('root')).render(<App />)
